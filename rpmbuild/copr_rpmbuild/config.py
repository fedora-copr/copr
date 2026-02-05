"""
Configuration class for copr-rpmbuild
"""

import yaml


CONFIG_PATH = "/etc/copr-rpmbuild/copr-rpmbuild.yml"


class Config:
    """
    Configuration class for copr-rpmbuild
    """

    def __init__(self):
        self.tags_to_mock_snippet = []
        self.rhsm = []

    def _set_default(self, loaded_data, config_option, default):
        value = loaded_data.get(config_option, default)
        setattr(self, config_option, value)

    def load_config(self):
        """
        Load configuration from the config file
        """
        config_data = {}
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as file:
                config_data = yaml.safe_load(file) or {}
        except FileNotFoundError:
            pass

        self.tags_to_mock_snippet = config_data.get("tags_to_mock_snippet", [])
        self.rhsm = config_data.get("rhsm", [])
        self._set_default(config_data, "macro_override_db_url", (
            "https://raw.githubusercontent.com/praiskup/"
            "norpm-macro-overrides/refs/heads/main/distro-arch-specific.json"
        ))
