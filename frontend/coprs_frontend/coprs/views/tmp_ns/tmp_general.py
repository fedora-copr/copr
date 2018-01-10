import flask
import os
from coprs.views.tmp_ns import tmp_ns
from coprs import app

@tmp_ns.route("/<directory>/<file_path>")
def give_srpm(directory, file_path):
    path = os.path.join(app.config["STORAGE_DIR"], directory)
    return flask.send_from_directory(path, file_path)
