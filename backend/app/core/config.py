import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Stock Selection System"
    VERSION: str = "1.0.0"
    
    DATABASE_URL: str = "sqlite:///./data/stock.db"
    
    API_V1_PREFIX: str = "/api/v1"
    
    HOST: str = "127.0.0.1"
    PORT: int = 8001
    
    class Config:
        env_file = ".env"


settings = Settings()
