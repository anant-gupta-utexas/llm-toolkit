import os

from .base import Settings
from .environments import DevSettings, ProdSettings, StageSettings


def get_settings() -> Settings:
    """Load settings based on environment"""
    env = os.getenv("ENVIRONMENT", "dev").lower()

    config_map = {"dev": DevSettings, "stage": StageSettings, "prod": ProdSettings}

    config_class = config_map.get(env, DevSettings)
    return config_class()


# Global settings instance
settings = get_settings()
