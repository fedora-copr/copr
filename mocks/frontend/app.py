#!/usr/bin/python3

import flask
import json
import sys
import os

########################### constants & vars ###########################

data_dir = './data'
static_dir = './static'

if len(sys.argv) > 1:
    data_dir = os.path.abspath(sys.argv[1])

if len(sys.argv) > 2:
    static_dir = os.path.abspath(sys.argv[2])

app = flask.Flask(__name__, static_folder=static_dir)

import_task_dict = {}
build_task_dict = {}
action_task_dict = {}

import_results = []
build_results = []
action_results = []

started_build_task_dict = {}

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
    response = list(import_task_dict.values())
    debug_output(response, 'SENDING:')
    return flask.jsonify(response)


@app.route('/backend/import-completed/', methods=['POST', 'PUT'])
def distgit_upload_completed():
    debug_output(flask.request.json, 'RECEIVED:')
    import_results.append(flask.request.json)
    import_task_dict.pop(flask.request.json['build_id'])
    test_for_server_end()
    return flask.jsonify({'updated': True})

########################### backend interface ###########################

@app.route('/api/coprs/<path:path>/detail/')
def backend_auto_createrepo_status(path):
    return flask.jsonify({
        'detail': { 'auto_createrepo': True }
    })


@app.route('/backend/pending-action/', methods=['GET'])
def backend_pending_action():
    sorted_action_tasks = sorted(action_task_dict.values(), key=lambda x: x['id'])
    action = sorted_action_tasks[0] if sorted_action_tasks else None
    debug_output(action, 'SENDING:')
    return flask.jsonify(action)

@app.route('/backend/pending-jobs/', methods=['GET'])
def backend_pending_jobs():
    sorted_build_tasks = sorted(build_task_dict.values(), key=lambda x: x['task_id'])
    debug_output(sorted_build_tasks, 'SENDING:')
    return flask.jsonify(sorted_build_tasks)

@app.route('/backend/starting_build/', methods=['POST', 'PUT'])
def backend_starting_build():
    debug_output(flask.request.json, 'RECEIVED:')
    update = flask.request.json
    task_id = '{0}-{1}'.format(update['build_id'], update['chroot'])

    build_task = build_task_dict.pop(task_id, None)
    if build_task:
        started_build_task_dict[task_id] = build_task

    response = {'can_start': True}
    debug_output(response, 'SENDING BACK:', delim=False)
    return flask.jsonify(response)


@app.route('/backend/update/', methods=['POST', 'PUT'])
def backend_update():
    debug_output(flask.request.json, 'RECEIVED:')
    update = flask.request.json

    for build in update.get('builds', []):
        if build['status'] == 0 or build['status'] == 1: # if build is finished
            build_results.append(build)
            started_build_task_dict.pop(build['task_id'], None)
            test_for_server_end()

        if build['status'] == 3: # running (e.g. from pending)
            build_task_dict.pop(build['task_id'], None)
            started_build_task_dict[build['task_id']] = build

    for action in update.get('actions', []):
        action_task_dict.pop(action['id'], None)
        action_results.append(action)
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


@app.route("/backend/get-build-task/<task_id>")
def get_build_task(task_id):
    try:
        return flask.jsonify(started_build_task_dict[task_id])
    except KeyError:
        try: # useful when testing copr-rpmbuild by directly invoking it
            return flask.jsonify(build_task_dict[task_id])
        except KeyError:
            return flask.jsonify({'msg': 'Specified task ID not found'})

########################### helpers ###########################

def load_data_dict(filename, task_id_key='task_id'):
    filepath = '{0}/{1}'.format(data_dir, filename)
    task_dict = {}
    try:
        with open(filepath, 'r') as f:
            task_queue = json.loads(f.read())
            for task in task_queue:
                task_dict[task[task_id_key]] = task
        debug_output(task_dict, filename.upper()+':', delim=False)
    except Exception as e:
        print('Could not load {0} from data directory {1}'.format(filename, data_dir))
        print(str(e))
        print('---------------')
    return task_dict


def dump_responses():
    output = {
        'import-results.out.json': import_results,
        'build-results.out.json': build_results,
        'action-results.out.json': action_results,
    }

    for filename, data in output.items():
        if not data:
            continue
        with open(os.path.join(data_dir, filename), 'w') as f:
            f.write(json.dumps(data, indent=2, sort_keys=True))


def test_for_server_end():
    if not import_task_dict and not build_task_dict and not action_task_dict and not started_build_task_dict:
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
    import_task_dict = load_data_dict('import-tasks.json', 'build_id')
    build_task_dict = load_data_dict('build-tasks.json', 'task_id')
    action_task_dict = load_data_dict('action-tasks.json', 'id')

    if import_task_dict or build_task_dict or action_task_dict:
        app.run(host='0.0.0.0')
