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
    active_rule_version: str = "2022-v2"

    # Nebius Token Factory (OpenAI-compatible). Key is read from NEBIUS_API_KEY;
    # everything else is overridable with the LABELLENS_ prefix.
    nebius_base_url: str = "https://api.tokenfactory.nebius.com/v1"
    # Chosen by benchmarking every image-capable model on this account against real
    # labels (see docs/vision-model-benchmark.md): MiniMax-M3 read both the English and
    # the Devanagari label exactly, and was the fastest. Kimi-K2.7-Code and Gemma 3 are
    # the closest alternatives if it is unavailable.
    nebius_vision_model: str = "MiniMaxAI/MiniMax-M3"
    nebius_text_model: str = "meta-llama/Llama-3.3-70B-Instruct"
    nebius_timeout_seconds: float = 90.0
    ocr_provider: str = "auto"  # auto | nebius | tesseract | manual
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # A platform like Vercel gives every preview deploy its own subdomain, which a fixed
    # origin list can't enumerate in advance — set e.g.
    # LABELLENS_CORS_ORIGIN_REGEX=https://.*\.vercel\.app to allow all of them alongside
    # the exact origins above. Left unset, only cors_origins applies.
    cors_origin_regex: str | None = None

    # Case-management response windows (calendar days from officer confirmation).
    # A minor (FIX) finding gets a correction notice; a serious (REVIEW) finding opens
    # a formal case with a longer window, matching the severity of what is being asked
    # of the seller. Chosen as reasonable defaults, not derived from a specific rule.
    correction_notice_response_days: int = 15
    formal_case_response_days: int = 30
    # There is no user/role system in this build, so an escalated case is assigned to a
    # named role rather than a specific account — surfaced in the UI and the docket's
    # countersignature line.
    supervisor_role_name: str = "Superintendent, Legal Metrology"

    model_config = {"env_prefix": "LABELLENS_", "env_file": str(BASE_DIR / ".env"), "extra": "ignore"}


class NebiusKey(BaseSettings):
    """Read separately so the key uses its conventional un-prefixed name."""

    nebius_api_key: str | None = None

    model_config = {"env_file": str(BASE_DIR / ".env"), "extra": "ignore"}


settings = Settings()
nebius_api_key = NebiusKey().nebius_api_key

for d in (STORAGE_DIR, IMAGES_DIR, DOCKETS_DIR):
    d.mkdir(parents=True, exist_ok=True)
