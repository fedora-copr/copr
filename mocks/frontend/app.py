#!/usr/bin/env python3

import flask
import json

app = flask.Flask(__name__)

task_dict = {}
with open('data/import-tasks.json', 'r') as f:
    task_queue = json.loads(f.read())
    for task in task_queue:
        task_dict[task['task_id']] = task


@app.route('/backend/importing/')
def dist_git_importing_queue():
    response = {'builds': list(task_dict.values())}
    return flask.jsonify(response)


@app.route('/backend/import-completed/', methods=['POST', 'PUT'])
def dist_git_upload_completed():
    task_dict.pop(flask.request.json['task_id'])
    return flask.jsonify({'updated': True})


if __name__ == '__main__':
    app.run()
