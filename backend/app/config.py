from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    anthropic_api_key: str
    langsmith_api_key: str = ""
    langsmith_tracing: bool = False
    langsmith_project: str = "mitra"

    claude_model: str = "claude-sonnet-4-6"
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384

    jwt_secret_key: str = "mitra-dev-secret-change-in-production-use-32-chars"
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 30

    # Adzuna Jobs API — free tier at developer.adzuna.com
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""

    @property
    def async_database_url(self) -> str:
        url = self.database_url
        # Normalize to psycopg async driver
        for prefix in ("postgresql://", "postgres://"):
            if url.startswith(prefix):
                url = "postgresql+psycopg://" + url[len(prefix):]
                break
        return url


settings = Settings()
