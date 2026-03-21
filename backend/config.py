import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # MongoDB
    mongodb_uri: str = "mongodb+srv://user:pass@cluster0.mongodb.net/?retryWrites=true&w=majority"
    mongodb_db_name: str = "traffic_copilot"

    # LLM Providers
    groq_api_key: str = ""
    gemini_api_key: str = ""
    openrouter_api_key: str = ""
    llm_provider: str = "groq"  # groq | gemini | openrouter
    llm_model: str = "llama-3.3-70b-versatile"

    # OpenRouteService
    ors_api_key: str = ""

    # NYC Open Data
    nyc_app_token: str = ""

    # Feed Simulator
    feed_interval_seconds: float = 5.0
    active_city: str = "nyc"  # nyc | chandigarh

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
