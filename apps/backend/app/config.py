from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://hilpo:hilpo@localhost:5433/hilpo"
    gcs_sign_urls: bool = False
    gcs_signing_sa_email: str = ""

    model_config = {"env_prefix": "HILPO_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
