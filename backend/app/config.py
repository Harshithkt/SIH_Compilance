from pathlib import Path

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent
RULES_DIR = Path(__file__).resolve().parent / "rules"
STORAGE_DIR = BASE_DIR / "storage"
IMAGES_DIR = STORAGE_DIR / "images"
DOCKETS_DIR = STORAGE_DIR / "dockets"


class Settings(BaseSettings):
    app_name: str = "LabelLens"
    database_url: str = f"sqlite:///{BASE_DIR / 'labellens.db'}"
    active_rule_version: str = "2011-v1"

    # Nebius Token Factory (OpenAI-compatible). Key is read from NEBIUS_API_KEY;
    # everything else is overridable with the LABELLENS_ prefix.
    nebius_base_url: str = "https://api.tokenfactory.nebius.com/v1"
    nebius_vision_model: str = "Qwen/Qwen2.5-VL-72B-Instruct"
    nebius_text_model: str = "meta-llama/Llama-3.3-70B-Instruct"
    nebius_timeout_seconds: float = 90.0
    ocr_provider: str = "auto"  # auto | nebius | tesseract | manual

    model_config = {"env_prefix": "LABELLENS_", "env_file": str(BASE_DIR / ".env"), "extra": "ignore"}


class NebiusKey(BaseSettings):
    """Read separately so the key uses its conventional un-prefixed name."""

    nebius_api_key: str | None = None

    model_config = {"env_file": str(BASE_DIR / ".env"), "extra": "ignore"}


settings = Settings()
nebius_api_key = NebiusKey().nebius_api_key

for d in (STORAGE_DIR, IMAGES_DIR, DOCKETS_DIR):
    d.mkdir(parents=True, exist_ok=True)
