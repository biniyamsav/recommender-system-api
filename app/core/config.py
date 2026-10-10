from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_EXPIRATION_SECONDS: int = 300
    APP_ENV: str = "development"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()