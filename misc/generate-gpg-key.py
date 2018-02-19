#!/usr/bin/python
import sys
sys.path.append("/usr/share/copr/coprs_frontend")
from coprs.logic.actions_logic import ActionsLogic
from coprs.logic.coprs_logic import CoprsLogic
from coprs import db

USER="someuser"
PROJECT="someproject"
fcopr= CoprsLogic.get(USER, PROJECT).first()
ActionsLogic.send_create_gpg_key(fcopr)
db.session.commit()
print("Done")
