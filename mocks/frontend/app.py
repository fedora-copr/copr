#!/usr/bin/env python3

import flask
import json
import sys
import os

########################### constants & vars ###########################

data_dir = './data'
static_dir = './static'
static_path = '/static'

if len(sys.argv) > 1:
    data_dir = os.path.abspath(sys.argv[1])

if len(sys.argv) > 2:
    static_dir = os.path.abspath(sys.argv[2])

app = flask.Flask(__name__, static_path=static_path, static_folder=static_dir)

import_task_dict = {}
waiting_task_dict = {}

distgit_responses = []
backend_builds = []

# from in backend/constants.py
class BuildStatus(object):
    FAILURE = 0
    SUCCEEDED = 1
    RUNNING = 3
    PENDING = 4
    SKIPPED = 5

########################### error handling ###########################

@app.errorhandler(500)
def internal_server_error(error):
    print('Server Error: %s' % str(error))
    return 'NOT OK', 500


@app.errorhandler(Exception)
def unhandled_exception(e):
    print('Unhandled Exception: %s' % str(e))
    return 'NOT OK', 500

########################### file server interface ###########################

@app.route('/tmp/<path:path>')
def serve_uploaded_file(path):
    return app.send_static_file(path)

########################### distgit interface ###########################

@app.route('/backend/importing/')
def distgit_importing_queue():
    response = {'builds': list(import_task_dict.values())}
    debug_output(response, 'SENDING:')
    return flask.jsonify(response)


@app.route('/backend/import-completed/', methods=['POST', 'PUT'])
def distgit_upload_completed():
    distgit_responses.append(flask.request.json)
    import_task_dict.pop(flask.request.json['task_id'])
    test_for_server_end()
    return flask.jsonify({'updated': True})

########################### backend interface ###########################

@app.route('/api/coprs/<path:path>/detail/')
def backend_auto_createrepo_status(path):
    return flask.jsonify({
        'detail': { 'auto_createrepo': True }
    })


@app.route('/backend/waiting/', methods=['GET'])
def backend_waiting_queue():
    response = {'actions': [], 'builds': list(waiting_task_dict.values())}
    debug_output(response, 'SENDING:')
    return flask.jsonify(response)


@app.route('/backend/starting_build/', methods=['POST', 'PUT'])
def backend_starting_build():
    debug_output(flask.request.json, 'RECEIVED:')
    update = flask.request.json
    task_id = '{0}-{1}'.format(update['build_id'], update['chroot'])

    waiting_task_dict.pop(task_id, None)

    response = {'can_start': True}
    debug_output(response, 'SENDING BACK:', delim=False)
    return flask.jsonify(response)


@app.route('/backend/update/', methods=['POST', 'PUT'])
def backend_update():
    debug_output(flask.request.json, 'RECEIVED:')
    update = flask.request.json

    for build in update['builds']:
        if build['status'] == BuildStatus.FAILURE or build['status'] == BuildStatus.SUCCEEDED: # if build is finished
            backend_builds.append(build)
            test_for_server_end()

    response = {}
    debug_output(response, 'SENDING BACK:', delim=False)
    return flask.jsonify(response)


@app.route('/backend/reschedule_all_running/', methods=['POST'])
def backend_reschedule_all_running():
    return 'OK', 200


@app.route('/backend/reschedule_build_chroot/', methods=['POST', 'PUT'])
def backend_reschedule_build_chroot():
    return flask.jsonify({})

########################### helpers ###########################

def load_import_tasks():
    inputfile = '{0}/in/import-tasks.json'.format(data_dir)
    try:
        with open(inputfile, 'r') as f:
            task_queue = json.loads(f.read())
            for task in task_queue:
                import_task_dict[task['task_id']] = task
        debug_output(import_task_dict, 'LOADED IMPORT TASKS:', delim=False)
    except Exception as e:
        print('Could not load in/import-tasks.json from data directory {0}'.format(data_dir))
        print(str(e))
        print('---------------')


def load_waiting_tasks():
    inputfile = '{0}/in/waiting-tasks.json'.format(data_dir)
    try:
        with open(inputfile, 'r') as f:
            task_queue = json.loads(f.read())
            for task in task_queue:
                waiting_task_dict[task['task_id']] = task
        debug_output(waiting_task_dict, 'LOADED WAITING TASKS:', delim=False)
    except Exception as e:
        print('Could not load in/waiting-tasks.json from data directory {0}'.format(data_dir))
        print(str(e))
        print('---------------')


def dump_responses():
    outputdir = '{0}/out'.format(data_dir)
    os.makedirs(outputdir, exist_ok=True)

    output = {
        'distgit-responses': distgit_responses,
        'backend-builds': backend_builds,
    }

    for filename, data in output.items():
        if not data:
            continue
        with open(os.path.join(outputdir, filename), 'w') as f:
            f.write(json.dumps(data))


def test_for_server_end():
    if not import_task_dict and not waiting_task_dict:
        dump_responses()
        shutdown_server()


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

########################### main ###########################

if __name__ == '__main__':
    load_import_tasks()
    load_waiting_tasks()
    if import_task_dict or waiting_task_dict:
        app.run()
