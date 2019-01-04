from flask_script import Command
from coprs import models


class GetAdminsCommand(Command):

    def run(self, **kwargs):
        for u in models.User.query.filter(models.User.admin == True).all():
            print(u.username)
