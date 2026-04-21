from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── Direct API keys (기존 방식) ──────────────────────────────
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""

    # Expert models (direct API 방식의 기본값)
    claude_model: str = "claude-sonnet-4-6"
    gpt_model: str = "gpt-4o"
    gemini_model: str = "gemini-2.0-flash"

    # ── Expert 1 (범용 provider 방식) ────────────────────────────
    # provider: direct_anthropic | direct_openai | direct_gemini |
    #           openrouter | copilot | kilo | ollama | lm_studio | custom
    # 비어 있으면 위 direct API 기본값(claude/gpt/gemini) 사용
    expert1_provider: str = ""
    expert1_model: str = ""
    expert1_api_key: str = ""
    expert1_base_url: str = ""     # provider 기본 URL 재정의 시 사용
    expert1_name: str = ""         # 표시 이름 (비어 있으면 자동)

    # ── Expert 2 ─────────────────────────────────────────────────
    expert2_provider: str = ""
    expert2_model: str = ""
    expert2_api_key: str = ""
    expert2_base_url: str = ""
    expert2_name: str = ""

    # ── Expert 3 ─────────────────────────────────────────────────
    expert3_provider: str = ""
    expert3_model: str = ""
    expert3_api_key: str = ""
    expert3_base_url: str = ""
    expert3_name: str = ""

    # ── OpenRouter (공유 키) ──────────────────────────────────────
    openrouter_api_key: str = ""

    # ── Kilo Gateway (공유 키) ───────────────────────────────────
    kilo_api_key: str = ""

    # ── Judge ────────────────────────────────────────────────────
    judge_provider: str = "anthropic"  # anthropic | openai | google | openrouter | copilot
    judge_model: str = "claude-opus-4-7"
    judge_api_key: str = ""            # 비어 있으면 provider에 맞는 기본 키 사용
    judge_base_url: str = ""

    # ── Debate settings ──────────────────────────────────────────
    max_rounds: int = 3
    max_tokens_per_turn: int = 1500
    session_token_budget: int = 50_000

    # ── CORS ─────────────────────────────────────────────────────
    allowed_origins: str = "http://localhost:3000"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    def expert_provider(self, num: int) -> str:
        return getattr(self, f"expert{num}_provider", "")

    def expert_model(self, num: int) -> str:
        return getattr(self, f"expert{num}_model", "")

    def expert_api_key(self, num: int) -> str:
        return getattr(self, f"expert{num}_api_key", "")

    def expert_base_url(self, num: int) -> str:
        return getattr(self, f"expert{num}_base_url", "")

    def expert_name(self, num: int) -> str:
        return getattr(self, f"expert{num}_name", "")


settings = Settings()
