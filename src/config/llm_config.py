from typing import Dict, Optional

import yaml
from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    name: str
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    timeout: int = 30


class ProviderConfig(BaseModel):
    name: str
    base_url: Optional[str] = None
    api_version: Optional[str] = None
    models: Dict[str, ModelConfig]
    default_model: str
    rate_limits: Dict[str, int] = Field(default_factory=dict)


class LLMSettings(BaseModel):
    providers: Dict[str, ProviderConfig]
    default_provider: str

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "LLMSettings":
        """Load LLM config from YAML file"""
        try:
          with open(yaml_path, "r") as f:
              data = yaml.safe_load(f)
          return cls(**data)
        except FileNotFoundError:
            raise FileNotFoundError(f"LLM config file not found: {yaml_path}")
