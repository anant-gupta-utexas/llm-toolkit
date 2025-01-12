from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Defining path variables for most commonly used directories
base_path = Path(__file__).parent.parent.parent
src_path = base_path / "src"
configs_path = src_path / "config"
env_config_path = configs_path / "env_configs"
