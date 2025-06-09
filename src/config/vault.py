import os
from typing import Optional

try:
    import hvac
    VAULT_AVAILABLE = True
except ImportError:
    VAULT_AVAILABLE = False


class VaultLoader:
    def __init__(self):
        self.client = None
        if VAULT_AVAILABLE and (vault_url := os.getenv("VAULT_URL")):
            self.client = hvac.Client(url=vault_url)
            if token := os.getenv("VAULT_TOKEN"):
                self.client.token = token

    def get_secret(self, path: str, key: str) -> Optional[str]:
        """Fetch secret from Vault, fallback to env var"""
        if self.client and self.client.is_authenticated():
            try:
                response = self.client.secrets.kv.v2.read_secret_version(path=path)
                return response["data"]["data"].get(key)
            except Exception:
                pass

        # Fallback to environment variable
        return os.getenv(key.upper())


class VaultSettings:
    def __init__(self, **kwargs):
        vault = VaultLoader()

        # Load secrets from vault if available
        if not kwargs.get("GEMINI_API_KEY"):
            kwargs["GEMINI_API_KEY"] = vault.get_secret(
                "myapp/secrets", "GEMINI_API_KEY"
            )

        super().__init__(**kwargs)
