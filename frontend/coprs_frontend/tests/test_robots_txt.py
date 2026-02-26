from unittest import mock
from tests.coprs_test_case import CoprsTestCase

class TestRobotsTxt(CoprsTestCase):
    def test_robots_txt_success(self):
        """
        Test that /robots.txt is served correctly from the static directory.
        """
        response = self.tc.get("/robots.txt")

        # Verify response metadata
        assert response.status_code == 200
        assert response.mimetype == "text/plain"

        # Verify key contents from the actual robots.txt file
        content = response.data.decode("utf-8")
        assert "User-Agent: GPTBot" in content
        assert "Disallow: /admin" in content
        assert "DisallowAITraining: /api" in content
        assert "Allow: /" in content

    @mock.patch("flask.current_app.open_resource")
    def test_robots_txt_file_error(self, mock_open):
        """
        Test the error handling when the robots.txt file cannot be opened.
        """
        # Simulate an exception when opening the file
        error_message = "File not found"
        mock_open.side_effect = Exception(error_message)

        # We need to mock the logger to check if the error was logged
        with mock.patch("coprs.app.logger.error") as mock_log:
            response = self.tc.get("/robots.txt")

            # Verify the function handled the exception and returned the error string
            assert response.status_code == 200
            assert error_message in response.data.decode("utf-8")

            # Verify the error was logged
            mock_log.assert_any_call(msg=error_message, exc_info=True)
