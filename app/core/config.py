from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    #AI
    OPENAI_API_KEY: str
    FRIENDLI_TOKEN: str

    FRIENDLI_BASE_URL: str = "https://api.friendli.ai/serverless/v1"
    FRIENDLI_MODEL_ID: str = "LGAI-EXAONE/EXAONE-4.0.1-32B"


    #DB
    DB_HOST: str
    DB_PORT: int
    DB_USER: str = "root" 
    DB_PASSWORD: str
    DB_NAME: str = "consultation_db"

    #Elasticsearch
    ES_URL: str
    EMBEDDING_DIMS: int = 512

    #Kafka
    KAFKA_BOOTSTRAP_SERVERS: str
    KAFKA_CONSUMER_GROUP_ID: str
    KAFKA_AUTO_OFFSET_RESET: str
    KAFKA_TOPIC: str = "processing-consultation"
    KAFKA_SESSION_TIMEOUT_MS: int = 30000

    @property
    def DATABASE_URL(self) -> str:
        return f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()