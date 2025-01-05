import os

import yaml

from src.utils.logger import logger


class ConfigLoader(object):
    __instance = None
    __configs = None

    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = super(ConfigLoader, cls).__new__(cls)
            cls.__configs = cls._load_configs()
            cls._load_env_config()
            if cls.env_config is not None:
                cls.__configs = cls._extend_config(cls)
            logger.info("ConfigLoader Created")
        return cls.__instance

    @staticmethod
    def _load_configs():
        return read_all_yaml_dir()

    @classmethod
    def _load_env_config(cls):
        env_name = os.environ.get("ENV_NAME") or "dev"
        file_name = cls._get_yaml_file(env_name)
        config_path = os.path.join(env_config_path, file_name)
        cls.env_config = read_yaml(path=config_path)

    @staticmethod
    def _extend_config(self):
        try:
            return {**self.__configs, **self.env_config}
        except yaml.YAMLError as E:
            logger.error(f"Following error occurred while extending config: {E}")

    def get_configs(self):
        return self.__configs

    @staticmethod
    def _get_yaml_file(env_name):
        FILE_SUFFIX = ".yaml"
        if env_name == "stage":
            return "stage" + FILE_SUFFIX
        elif env_name == "prod":
            return "prod" + FILE_SUFFIX
        elif env_name == "local":
            return "local" + FILE_SUFFIX
        else:
            return "dev" + FILE_SUFFIX
