import sys
from pathlib import Path

import yaml

from src.utils.logger import logger
from src.utils.path_finder import configs_path


def read_yaml(path: Path) -> dict:
    """Function to read a single YAML file

    Parameters
    ----------
    path : Path
        Input path for the yaml file

    Returns
    -------
    config: dict
        Dictionary containing contents of a single YAML file
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


def read_all_yaml_dir(dir_path: Path = configs_path, exclude_list: list = None) -> dict:
    """Function to read all the YAML files in a particular directory.
    Can exclude specific files from output if required using a parameter

    Parameters
    ----------
    dir_path : Path, optional
        Input path for the yaml files, by default configs_path
    exclude_list : list, optional
        list of filenames with extension to be excluded from loading , by default None

    Returns
    -------
    config_dict: dict
        Dictionary containing all the configs in the provided config_path
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
