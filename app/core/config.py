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

    # DB (SSM: db_host, db_port, db_user, db_password, db_name → DATABASE_URL 구성)
    DB_HOST: Optional[str] = None
    DB_PORT: int = 3306
    DB_USER: str = ""  # SSM db_user (운영에서 필수)
    DB_PASSWORD: str = ""  # SSM db_password
    DB_NAME: str = "consultation_db"  # SSM db_name (선택)

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
        if not self.DB_HOST or not self.DB_PASSWORD or not self.DB_USER:
            raise ValueError(
                "DB_HOST, DB_USER, DB_PASSWORD must be set (e.g. from SSM: db_host, db_user, db_password)"
            )
        return self

    @property
    def DATABASE_URL(self) -> str:
        from urllib.parse import quote_plus

        user = quote_plus(self.DB_USER)
        password = quote_plus(self.DB_PASSWORD)
        return (
            f"mysql+aiomysql://{user}:{password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()