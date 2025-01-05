import sys
from pathlib import Path

import yaml

from src.utils.logger import logger


def read_yaml(path: Path) -> dict:
    """_summary_

    Parameters
    ----------
    path : Path
        _description_, by default configs_path

    Returns
    -------
    dict
        _description_
    """
    if not (path or path.exists()):
        logger.error("Invalid YAML path provided.")
        sys.exit(0)

    # Reading the contents from provided filepath
    with open(path, "r", encoding="utf-8") as stream:
        try:
            config = yaml.safe_load(stream)
            logger.debug(f"Config from {path}: \n {config}")
            return config
        except yaml.YAMLError as E:
            logger.error(f"Error reading YAML file: {E}")


def read_yaml_all_dir(dir_path: Path = configs_path, exclude_list: list = None) -> dict:
    """_summary_

    Parameters
    ----------
    dir_path : Path, optional
        Input path for the yaml files, by default configs_path
    exclude_list : list, optional
        list of filenames with extension to be excluded from loading , by default None

    Returns
    -------
    config_dict: dict
        Dictionary containing all the config in the provided config_path
    """

    # Create a list of yaml files in the given directory path
    paths = list(Path(dir_path).glob("*.yaml")) + list(Path(dir_path).glob("*.yml"))

    # Append dir_path for exclude files
    if exclude_list:
        exclude_list = [configs_path / fname for fname in exclude_list]

    # Initialize an empty dictionary
    config_dict = {}

    # Loop through all files except the ones in exclude_list
    for path in paths:
        if exclude_list and path in exclude_list:
            continue
        temp_config = read_yaml(path)
        config_dict.update(temp_config)

    return config_dict
