#!/usr/bin/python3

import flask

app = flask.Flask(__name__)
@app.route('/backend/update/', methods=['POST', 'PUT'])
def backend_update():
    return flask.jsonify({})

if __name__ == '__main__':
    app.run(host='0.0.0.0')
