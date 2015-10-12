from coprs import exceptions

from coprs import app, db
from coprs.models import User, Group


class UsersLogic(object):

    @classmethod
    def get(cls, username):
        return User.query.filter(User.username == username)

    @classmethod
    def get_by_api_login(cls, login):
        return User.query.filter(User.api_login == login)

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

    @classmethod
    def raise_if_cant_build_in_copr(cls, user, copr, message):
        """
        Raises InsufficientRightsException if given user cant build in
        given copr. Return None otherwise.
        """

        if not user.can_build_in(copr):
            raise exceptions.InsufficientRightsException(message)

    @classmethod
    def get_group_by_alias(cls, name):
        return Group.query.filter(Group.name == name)

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
    def filter_blacklisted_groups(cls, active_map):
        """ remove from active_map blacklisted groups
            active_map is l-value so we can remove it in-place.
        """
        if "SRPM_STORAGE_DIR" in app.config:
            for group in app.config["SRPM_STORAGE_DIR"]:
                del(active_map[group])

    @classmethod
    def is_blacklisted_groups(cls, fas_group):
        if "SRPM_STORAGE_DIR" in app.config:
            return fas_group in app.config["SRPM_STORAGE_DIR"]
        else:
            return False
