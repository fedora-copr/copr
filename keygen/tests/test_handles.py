import json
import six

if six.PY3:
    from unittest import mock
else:
    import mock


from copr_keygen import app
from copr_keygen.exceptions import KeygenServiceBaseException


app.config["PHRASES_DIR"] = "/tmp"

def test_ping():
    """ Simple check for simple handle
    """
    with app.test_client() as c:

        rv = c.get('/ping')
        assert rv.status_code == 200
        assert rv.data == b"pong\n"


json_data = json.dumps({
    "name_real": "foo_bar",
    "name_email": "foo_bar@example.com"
})
json_data_missing_email = json.dumps({"name_real": "foo_bar"})
json_data_missing_name = json.dumps({"name_email": "foo_bar@example.com"})


@mock.patch("copr_keygen.create_new_key")
@mock.patch("copr_keygen.user_exists")
class TestGenKey(object):

    def test_gen_key(self, user_exists, create_new_key):
        """ Check reactions to different sets of input data
        """
        user_exists.return_value = False
        create_new_key.return_value = None

        with app.test_client() as c:
            rv = c.post('/gen_key', data=json_data)
            assert rv.status_code == 201

            rv = c.post('/gen_key', data=None)
            assert rv.status_code == 400
            #
            rv = c.post('/gen_key', data=json_data_missing_email)
            assert rv.status_code == 400
            #
            rv = c.post('/gen_key', data=json_data_missing_name)
            assert rv.status_code == 400

    def test_gen_key_user_not_exists(self, user_exists, create_new_key):
        """ Check that key is really created when user not exists
        """
        user_exists.return_value = False
        create_new_key.return_value = None

        with app.test_client() as c:
            rv = c.post('/gen_key', data=json_data)
            assert rv.status_code == 201

        assert user_exists.called
        assert create_new_key.called

    def test_gen_key_with_existing_user(self, user_exists, create_new_key):
        """ Check that key is not created when user not exists
        """
        user_exists.return_value = True

        with app.test_client() as c:
            rv = c.post('/gen_key', data=json_data)
            assert rv.status_code == 200

        assert user_exists.called
        assert not create_new_key.called

    def test_server_error_at_user_exists(self, user_exists, _):
        user_exists.side_effect = KeygenServiceBaseException()

        with app.test_client() as c:
            rv = c.post('/gen_key', data=json_data)
            assert rv.status_code == 500

    def test_server_error_at_create_new_key(self, user_exists, create_new_key):
        user_exists.return_value = False
        create_new_key.side_effect = KeygenServiceBaseException()

        with app.test_client() as c:
            rv = c.post('/gen_key', data=json_data)
            assert rv.status_code == 500
