import os

import yaml

from src.utils.io_utils import read_all_yaml_dir, read_yaml
from src.utils.logger import logger
from src.utils.path_finder import env_config_path


class ConfigLoader(object):
    def __init__(self):
        self._configs = self._load_configs()
        self.env_config = self._load_env_config()
        if self.env_config is not None:
            self._configs = self._extend_config(self._configs, self.env_config)
        logger.info("ConfigLoader Initialized")

    @staticmethod
    def _load_configs():
        return read_all_yaml_dir()

    def _load_env_config(self):
        env_name = os.environ.get("ENV_NAME", "dev")  # Default to "dev" if not set
        file_name = self._get_yaml_file(env_name)
        config_path = os.path.join(env_config_path, file_name)
        return read_yaml(path=config_path)

    @staticmethod
    def _extend_config(base_config, env_config):
        try:
            return {**base_config, **env_config}
        except yaml.YAMLError as e:
            logger.error(f"Error occurred while extending config: {e}")
            return base_config  # Return the base config if merging fails

    @staticmethod
    def _get_yaml_file(env_name):
        FILE_SUFFIX = ".yaml"

        env_file_mapping = {
            "stage": "stage",
            "prod": "prod",
            "local": "local",
            "dev": "dev",
        }
        return env_file_mapping.get(env_name, "dev") + FILE_SUFFIX

    def get_configs(self):
        return self._configs
