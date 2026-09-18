import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "FIXYRON"
    API_V1_STR: str = "/api"
    
    # Database
    DATABASE_URL: str
    
    # CORS
    FRONTEND_URL: str = "http://localhost:3000"

    # GitHub Integration
    GITHUB_TOKEN: str = ""

    @property
    def BACKEND_CORS_ORIGINS(self) -> List[str]:
        return [self.FRONTEND_URL]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
