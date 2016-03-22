#!/usr/bin/env python3

import flask
import json
import sys
import os

app = flask.Flask(__name__)

import_task_dict = {}
waiting_task_dict = {}

distgit_responses = []
backend_failed_posts = []
backend_succeeded_posts = []
backend_starting_posts = []
backend_running_posts = []
backend_other_posts = [] # should be empty

# from in backend/constants.py
class BuildStatus(object):
    FAILURE = 0
    SUCCEEDED = 1
    RUNNING = 3
    PENDING = 4
    SKIPPED = 5


# http://flask.pocoo.org/snippets/67/
def shutdown_server():
    func = flask.request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()


@app.route('/tmp/<path:path>')
def serve_uploaded_file(path):
    return app.send_static_file(path)


@app.route('/backend/importing/')
def dist_git_importing_queue():
    response = {'builds': list(import_task_dict.values())}
    return flask.jsonify(response)


@app.route('/backend/import-completed/', methods=['POST', 'PUT'])
def dist_git_upload_completed():
    distgit_responses.append(flask.request.json)
    import_task_dict.pop(flask.request.json['task_id'])
    test_for_server_end()
    return flask.jsonify({'updated': True})


@app.route('/backend/waiting/', methods=['GET'])
def backend_waiting_queue():
    response = {'actions': [], 'builds': list(waiting_task_dict.values())}
    return flask.jsonify(response)


@app.route("/backend/starting_build/", methods=["POST", "PUT"])
def starting_build():
    print(flask.request.json)
    response = flask.request.json
    task_id = '{0}-{1}'.format(response['build_id'], response['chroot'])

    backend_starting_posts.append(response)
    waiting_task_dict.pop(task_id)

    return flask.jsonify({ "can_start": True })


@app.route("/backend/update/", methods=["POST", "PUT"])
def update():
    print(flask.request.json)
    response = flask.request.json
    build = response['builds'][0]

    if build['status'] == BuildStatus.RUNNING:
        backend_running_posts.append(build)
    elif build['status'] == BuildStatus.SUCEEDED:
        backend_succeeded_posts.append(build)
        test_for_server_end()
    elif build['status'] == BuildStatus.FAILED:
        backend_failed_posts.append(build)
        test_for_server_end()
    else:
        backend_other_posts.append(build) # should stay empty

    return flask.jsonify({})


@app.route("/backend/reschedule_all_running/", methods=["POST"])
def reschedule_all_running():
    return "OK", 200


@app.route("/backend/reschedule_build_chroot/", methods=["POST", "PUT"])
def reschedule_build_chroot():
    return flask.jsonify({})


def load_import_tasks():
    with open('data/import-tasks.json', 'r') as f:
        task_queue = json.loads(f.read())
        for task in task_queue:
            import_task_dict[task['task_id']] = task
    print(import_task_dict)
    print('--------------')


def load_waiting_tasks():
    with open('data/waiting-tasks.json', 'r') as f:
        task_queue = json.loads(f.read())
        for task in task_queue:
            waiting_task_dict[task['task_id']] = task
    print(waiting_task_dict)
    print('---------------')


def dump_responses():
    if len(sys.argv) > 1:
        ouput_dir = sys.argv[1]
    else:
        output_dir = 'data'

    output = {
        'distgit_responses': distgit_responses,
        'backend_failed_posts': backend_failed_posts,
        'backend_succeeded_posts': backend_succeeded_posts,
        'backend_starting_posts': backend_starting_posts,
        'backend_running_posts': backend_running_posts,
        'backend_other_posts': backend_other_posts,
    }

    for filename, data in output.items():
        with open(os.path.join(outputdir, filename), 'w') as f:
            f.write(json.dumps(data))


def test_for_server_end():
    if not import_task_dict or not waiting_task_dict:
        dump_responses()
        shutdown_server()


if __name__ == '__main__':
    load_import_tasks()
    load_waiting_tasks()
    app.run()
