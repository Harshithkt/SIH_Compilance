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
    # Plain-language explanation of a finding, English or Hindi. Chosen by testing the
    # account's live catalogue: it answered correctly in Devanagari and was the fastest
    # of the candidates, which matters because an officer waits on this call.
    nebius_text_model: str = "google/gemma-3-27b-it"
    nebius_timeout_seconds: float = 90.0
    ocr_provider: str = "auto"  # auto | nebius | paddleocr | tesseract | manual

    # Offline OCR engine. PP-OCRv6 is the current generation; a Hindi capture pins
    # PP-OCRv5 regardless, since the Devanagari recognition model ships only there.
    paddle_ocr_version: str = "PP-OCRv6"
    paddle_device: str = "cpu"  # "cpu" | "gpu:0" | "npu:0"
    # Officers photograph packs at an angle often enough to be worth the extra model.
    paddle_use_textline_orientation: bool = True
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    seed_secret: str | None = None
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
    # An escalated case is assigned to the supervising role rather than to one named
    # account, so the assignment survives staff changes — surfaced in the UI and on the
    # docket's countersignature line.
    supervisor_role_name: str = "Superintendent, Legal Metrology"

    # Authentication. Left unset, tokens are signed with a secret generated per process,
    # so every officer is signed out when the server restarts — set this in deployment.
    jwt_secret: str | None = None
    jwt_expiry_minutes: int = 12 * 60  # a full field shift
    # Password given to the starting accounts created on an empty database. Only ever
    # used for that bootstrap; change it immediately in any real deployment.
    bootstrap_password: str = "labellens-demo"

    model_config = {"env_prefix": "LABELLENS_", "env_file": str(BASE_DIR / ".env"), "extra": "ignore"}


class NebiusKey(BaseSettings):
    """Read separately so the key uses its conventional un-prefixed name."""

    nebius_api_key: str | None = None

    model_config = {"env_file": str(BASE_DIR / ".env"), "extra": "ignore"}


settings = Settings()
nebius_api_key = NebiusKey().nebius_api_key

for d in (STORAGE_DIR, IMAGES_DIR, DOCKETS_DIR):
    d.mkdir(parents=True, exist_ok=True)
