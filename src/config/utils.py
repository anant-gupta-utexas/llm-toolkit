from typing import Any, Dict, Optional


def get_database_url(settings) -> str:
    """Construct the database URL from the settings"""
    db_config = settings.database
    return f"postgresql://{db_config.host}:{db_config.port}/{db_config.name}"

def get_llm_client_config(settings, provider_name: Optional[str] = None, model_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Get the LLM client configuration for a specific provider.
    If model_name is provided, it fetches that specific model's config; otherwise, it uses the provider's default model.
    """
    try:
        llm_config = settings.llm_config
        provider_name = provider_name or llm_config.default_provider

        if provider_name not in llm_config.providers:
            raise ValueError(f"Provider '{provider_name}' not found in LLM config")

        provider = llm_config.providers[provider_name]

        # Determine which model to load
        selected_model_name = model_name or provider.default_model

        if selected_model_name not in provider.models:
            raise ValueError(f"Model '{selected_model_name}' not found for provider '{provider_name}'")

        model_config_data = provider.models[selected_model_name]

        return {
            "provider": provider.name,
            "base_url": provider.base_url,
            "api_version": getattr(provider, 'api_version', None),
            "model": selected_model_name,
            "model_config": model_config_data.dict() if hasattr(model_config_data, 'dict') else model_config_data,
            "rate_limits": getattr(provider, 'rate_limits', None),
        }
    except Exception as e:
        raise RuntimeError(f"Failed to load LLM client config for provider '{provider_name}' and model '{model_name or 'default'}': {e}")
