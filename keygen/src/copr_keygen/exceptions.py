class KeygenServiceBaseException(Exception):
    status_code = 500

    @property
    def msg(self):
        return str(self)

    def __init__(self, *args, **kwargs):
        super(KeygenServiceBaseException, self).__init__(*args)
        self.kwargs = kwargs

    def __str__(self):
        out = "Keygen service error\n"
        out += "args: {}\n".format(repr(self.args))
        out += "kwargs: {}\n".format(repr(self.kwargs))
        return out


class BadRequestException(KeygenServiceBaseException):
    status_code = 400


class GpgErrorException(KeygenServiceBaseException):
    status_code = 500
