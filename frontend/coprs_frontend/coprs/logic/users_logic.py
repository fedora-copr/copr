import base64
import json
import datetime
from coprs import exceptions
from flask import url_for

from coprs import app, db
from coprs.logic import coprs_logic
from coprs.models import User, Group
from coprs.helpers import copr_url, generate_api_token
from sqlalchemy import update


class UsersLogic(object):

    @classmethod
    def get(cls, username):
        app.logger.info("Querying user '%s' by username", username)
        return User.query.filter(User.username == username)

    @classmethod
    def get_by_api_login(cls, login):
        return User.query.filter(User.api_login == login)

    @classmethod
    def get_multiple_with_projects(cls):
        """
        Return all users that have at least one project (deleted projects
        counts as well)
        """
        return User.query.filter(~User.coprs.any())

    @classmethod
    def raise_if_cant_update_copr(cls, user, copr, message):
        """
        Raise InsufficientRightsException if given user cant update
        given copr. Return None otherwise.
        """

        # TODO: this is a bit inconsistent - shouldn't the user method be
        # called can_update?
        if not user.can_edit(copr):
            raise exceptions.InsufficientRightsException(message)

        app.logger.info("User '%s' allowed to update project '%s'",
                        user.name, copr.full_name)

    @classmethod
    def raise_if_cant_build_in_copr(cls, user, copr, message):
        """
        Raises InsufficientRightsException if given user cant build in
        given copr. Return None otherwise.
        """

        if not user.can_build_in(copr):
            raise exceptions.InsufficientRightsException(message)

        app.logger.info("User '%s' allowed to build in project '%s'",
                        user.name, copr.full_name)

    @classmethod
    def raise_if_not_in_group(cls, user, group):
        if not user.admin and group.fas_name not in user.user_teams:
            raise exceptions.InsufficientRightsException(
                "User '{}' doesn't have access to the copr group '{}' (fas_name='{}')"
                .format(user.username, group.name, group.fas_name))

        app.logger.info("User '%s' allowed to access group '%s' (fas_name='%s')",
                        user.name, group.name, group.fas_name)

    @classmethod
    def get_group_by_alias(cls, name):
        return Group.query.filter(Group.name == name)

    @classmethod
    def group_alias_exists(cls, name):
        query = cls.get_group_by_alias(name)
        return query.count() != 0

    @classmethod
    def get_group_by_fas_name(cls, fas_name):
        return Group.query.filter(Group.fas_name == fas_name)

    @classmethod
    def get_groups_by_fas_names_list(cls, fas_name_list):
        return Group.query.filter(Group.fas_name.in_(fas_name_list))

    @classmethod
    def get_groups_by_names_list(cls, name_list):
        return Group.query.filter(Group.name.in_(name_list))

    @classmethod
    def create_group_by_fas_name(cls, fas_name, alias=None):
        if alias is None:
            alias = fas_name

        group = Group(
            fas_name=fas_name,
            name=alias,
        )
        db.session.add(group)
        return group

    @classmethod
    def get_group_by_fas_name_or_create(cls, fas_name, alias=None):
        mb_group = cls.get_group_by_fas_name(fas_name).first()
        if mb_group is not None:
            return mb_group

        group = cls.create_group_by_fas_name(fas_name, alias)
        db.session.flush()
        return group

    @classmethod
    def filter_denylisted_teams(cls, teams):
        """ removes denylisted groups from teams list
            :type teams: list of str
            :return: filtered teams
            :rtype: list of str
        """
        denylist = set(app.config.get("GROUP_DENYLIST", []))
        return filter(lambda t: t not in denylist, teams)

    @classmethod
    def is_denylisted_group(cls, fas_group):
        """
        Return true if FAS_GROUP is on GROUP_DENYLIST in copr configuration.
        """
        if "GROUP_DENYLIST" in app.config:
            return fas_group in app.config["GROUP_DENYLIST"]
        return False

    @classmethod
    def delete_user_data(cls, user):
        null = {"timezone": None,
                "proven": False,
                "admin": False,
                "api_login": "",
                "api_token": "",
                "api_token_expiration": datetime.date(1970, 1, 1),
                "openid_groups": None}
        for k, v in null.items():
            setattr(user, k, v)
        app.logger.info("Deleting user '%s' data", user.name)

    @classmethod
    def create_user_wrapper(cls, username, email=None, timezone=None):
        """
        Initial creation of Copr user (creates the API token, too).
        Create user + token configuration.
        """
        expiration_date_token = datetime.date.today() + \
            datetime.timedelta(
                days=app.config["API_TOKEN_EXPIRATION"])

        copr64 = base64.b64encode(b"copr") + b"##"
        user = User(username=username, mail=email,
                    timezone=timezone,
                    api_login=copr64.decode("utf-8") + generate_api_token(
                        app.config["API_TOKEN_LENGTH"] - len(copr64)),
                    api_token=generate_api_token(
                        app.config["API_TOKEN_LENGTH"]),
                    api_token_expiration=expiration_date_token)
        app.logger.info("Creating user '%s <%s>'", user.name, user.mail)
        return user


class UserDataDumper(object):
    def __init__(self, user):
        self.user = user

    def dumps(self, pretty=False):
        app.logger.info("Dumping all user data for '%s'", self.user.name)
        if pretty:
            return json.dumps(self.data, indent=2)
        return json.dumps(self.data)

    @property
    def data(self):
        data = self.user_information
        data["groups"] = self.groups
        data["projects"] = self.projects
        data["builds"] = self.builds
        return data

    @property
    def user_information(self):
        return {
            "username": self.user.name,
            "email": self.user.mail,
            "timezone": self.user.timezone,
            "api_login": self.user.api_login,
            "api_token": self.user.api_token,
            "api_token_expiration": self.user.api_token_expiration.strftime("%b %d %Y %H:%M:%S"),
            "gravatar": self.user.gravatar_url,
        }

    @property
    def groups(self):
        return [{"name": g.name,
                 "url": url_for("groups_ns.list_projects_by_group", group_name=g.name, _external=True)}
                for g in self.user.user_groups]

    @property
    def projects(self):
        return [{"full_name": p.full_name,
                 "url": copr_url("coprs_ns.copr_detail", p, _external=True)}
                for p in coprs_logic.CoprsLogic.filter_by_user_name(
                        coprs_logic.CoprsLogic.get_multiple(), self.user.name)]

    @property
    def builds(self):
        return [{"id": b.id,
                 "project": b.copr.full_name,
                 "url": copr_url("coprs_ns.copr_build", b.copr, build_id=b.id, _external=True)}
                for b in self.user.builds]
