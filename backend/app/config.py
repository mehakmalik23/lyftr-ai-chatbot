import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    @property
    def llm_api_keys(self) -> list[str]:
        raw = os.getenv("LLM_API_KEYS", "")
        return [k.strip() for k in raw.split(",") if k.strip()]

    @property
    def llm_model(self) -> str:
        return os.getenv("LLM_MODEL", "gemini/gemini-2.0-flash")

    @property
    def database_url(self) -> str:
        return os.getenv("DATABASE_URL", "sqlite:////data/app.db")

    @property
    def sqlite_path(self) -> str:
        url = self.database_url
        if url.startswith("sqlite:////"):
            return "/" + url[len("sqlite:////"):]
        elif url.startswith("sqlite:///"):
            return url[len("sqlite:///"):]
        return url

    @property
    def allowed_origins(self) -> list[str]:
        raw = os.getenv("ALLOWED_ORIGINS", "*")
        if raw.strip() == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    @property
    def enable_failure_simulation(self) -> bool:
        return os.getenv("ENABLE_FAILURE_SIMULATION", "true").lower() == "true"

    @property
    def default_system_prompt(self) -> str:
        return os.getenv("DEFAULT_SYSTEM_PROMPT", "You are a helpful, concise AI assistant.")

settings = Settings()
