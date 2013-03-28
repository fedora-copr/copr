import exceptions

class UsersLogic(object):
    @classmethod
    def raise_if_cant_update_copr(cls, user, copr, message):
        """This method raises InsufficientRightsException if given user cant update
        given copr. Returns None otherwise.
        """
        # TODO: this is a bit inconsistent - shouldn't the user method be called can_update?
        if not user.can_edit(copr):
            raise exceptions.InsufficientRightsException(message)
