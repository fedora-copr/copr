#!/usr/bin/env python3

import flask
import json
import sys
import os

datadir = './data'

app = flask.Flask(__name__)

import_task_dict = {}
waiting_task_dict = {}

distgit_responses = []
backend_failed_posts = []
backend_succeeded_posts = []
backend_starting_posts = []
backend_running_posts = []
backend_other_posts = [] # should stay empty


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


def debug_output(data, label='RECEIVED:', delim=True):
    if delim:
        print('---------------')
    print(label)
    print(data)


@app.errorhandler(500)
def internal_server_error(error):
    print('Server Error: %s', str(error))
    return 'NOT OK', 500


@app.errorhandler(Exception)
def unhandled_exception(e):
    print('Unhandled Exception: %s', str(e))
    return 'NOT OK', 500


@app.route('/tmp/<path:path>')
def serve_uploaded_file(path):
    return app.send_static_file(path)


@app.route('/api/coprs/<path:path>/detail/')
def backend_auto_createrepo_status(path):
    return flask.jsonify({
        'detail': { 'auto_createrepo': True }
    })


@app.route('/backend/importing/')
def dist_git_importing_queue():
    response = {'builds': list(import_task_dict.values())}
    debug_output(response, 'SENDING:')
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
    debug_output(response, 'SENDING:')
    return flask.jsonify(response)


@app.route('/backend/starting_build/', methods=['POST', 'PUT'])
def starting_build():
    debug_output(flask.request.json, 'RECEIVED:')
    update = flask.request.json
    task_id = '{0}-{1}'.format(update['build_id'], update['chroot'])

    backend_starting_posts.append(update)
    waiting_task_dict.pop(task_id)

    response = {'can_start': True}
    debug_output(response, 'SENDING BACK:', delim=False)
    return flask.jsonify(response)


@app.route('/backend/update/', methods=['POST', 'PUT'])
def backend_update():
    debug_output(flask.request.json, 'RECEIVED:')
    update = flask.request.json
    build = update['builds'][0]

    if build['status'] == BuildStatus.RUNNING:
        backend_running_posts.append(update)
    elif build['status'] == BuildStatus.SUCCEEDED:
        backend_succeeded_posts.append(update)
        test_for_server_end()
    elif build['status'] == BuildStatus.FAILURE:
        backend_failed_posts.append(update)
        test_for_server_end()
    else:
        backend_other_posts.append(update) # should stay empty

    response = {}
    debug_output(response, 'SENDING BACK:', delim=False)
    return flask.jsonify(response)


@app.route('/backend/reschedule_all_running/', methods=['POST'])
def backend_reschedule_all_running():
    return 'OK', 200


@app.route('/backend/reschedule_build_chroot/', methods=['POST', 'PUT'])
def backend_reschedule_build_chroot():
    return flask.jsonify({})


def load_import_tasks():
    inputfile = '{0}/in/import-tasks.json'.format(datadir)
    with open(inputfile, 'r') as f:
        task_queue = json.loads(f.read())
        for task in task_queue:
            import_task_dict[task['task_id']] = task
    debug_output(import_task_dict, 'LOADED IMPORT TASKS:', delim=False)


def load_waiting_tasks():
    inputfile = '{0}/in/waiting-tasks.json'.format(datadir)
    with open(inputfile, 'r') as f:
        task_queue = json.loads(f.read())
        for task in task_queue:
            waiting_task_dict[task['task_id']] = task
    debug_output(waiting_task_dict, 'LOADED WAITING TASKS:', delim=False)


def dump_responses():
    outputdir = '{0}/out'.format(datadir)

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
    if len(sys.argv) > 1:
        datadir = sys.argv[1]
    load_import_tasks()
    load_waiting_tasks()
    app.run()
