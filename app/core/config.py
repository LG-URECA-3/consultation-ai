import os
from typing import Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Spring Boot application-prod.yml 처럼 환경별 파일 로드 (ENVIRONMENT=production 이면 .env.prod 사용)
_ENV = os.getenv("ENVIRONMENT", "development")
_ENV_FILE = ".env.prod" if _ENV == "production" else ".env"

# SSM Parameter Store 주입 (USE_SSM=true 또는 ENVIRONMENT=production 일 때)
if os.getenv("USE_SSM", "").lower() in ("true", "1", "yes") or _ENV == "production":
    from app.core.ssm import load_ssm_into_env

    load_ssm_into_env()


class Settings(BaseSettings):
    # AI
    OPENAI_API_KEY: str
    FRIENDLI_TOKEN: str

    FRIENDLI_BASE_URL: str = "https://api.friendli.ai/serverless/v1"
    FRIENDLI_MODEL_ID: str = "LGAI-EXAONE/EXAONE-4.0.1-32B"

    # DB (SSM db_url 사용 시 DB_URL만 설정, 아니면 DB_HOST 등 개별 필드 사용)
    DB_URL: Optional[str] = None
    DB_HOST: Optional[str] = None
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "consultation_db"

    # Elasticsearch (SSM elasticsearch_uris → ES_URL)
    ES_URL: str = ""

    # Kafka (SSM kafka_bootstrap_servers)
    KAFKA_BOOTSTRAP_SERVERS: str = ""
    KAFKA_CONSUMER_GROUP_ID: str = "consultation-group"
    KAFKA_AUTO_OFFSET_RESET: str = "earliest"

    # Redis (SSM redis_host, redis_password, 선택)
    REDIS_HOST: Optional[str] = None
    REDIS_PASSWORD: Optional[str] = None

    @model_validator(mode="after")
    def check_db_config(self) -> "Settings":
        if not self.DB_URL and not self.DB_HOST:
            raise ValueError(
                "Either DB_URL (e.g. from SSM) or DB_HOST (and DB_PASSWORD) must be set"
            )
        return self

    @property
    def DATABASE_URL(self) -> str:
        if self.DB_URL:
            return self.DB_URL
        return (
            f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()