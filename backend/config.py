import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # MongoDB
    mongodb_uri: str = ""  # empty default — validated at startup
    mongodb_db_name: str = "traffic_copilot"

    # API Auth
    api_key: str = ""      # X-API-Key for write endpoints

    # Services
    ml_service_url: str = "http://localhost:8001"

    # Circuit breaker thresholds
    cb_failure_threshold: int = 3  # failures before open
    cb_recovery_sec: float = 30.0  # seconds before half-open retry

    # Timeouts (seconds)
    llm_timeout_sec: float = 45.0
    vlm_timeout_sec: float = 30.0
    routing_timeout_sec: float = 15.0
    ors_timeout_sec: float = 5.5
    ml_timeout_sec: float = 30.0
    collision_timeout_sec: float = 2.5

    # LLM Providers
    groq_api_key: str = ""
    gemini_api_key: str = ""
    openrouter_api_key: str = ""
    huggingface_api_token: str = ""
    llm_provider: str = "groq"  # groq | gemini | openrouter
    llm_model: str = "openai/gpt-oss-120b"
    groq_model: str = "llama-3.1-8b-instant"  # Separate Groq-specific model

    # OpenRouteService
    ors_api_key: str = ""
    local_ors_chandigarh_url: str = "http://localhost:8081/ors/v2/directions/driving-car/geojson"
    local_ors_nyc_url: str = "http://localhost:8082/ors/v2/directions/driving-car/geojson"
    
    # Mapbox (for Directions API with traffic)
    mapbox_token: str = ""

    # NYC Open Data
    nyc_app_token: str = ""

    # Feed Simulator
    feed_interval_seconds: float = 5.0
    active_city: str = "nyc"  # nyc | chandigarh

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = [
        "http://localhost:5173", 
        "http://localhost:3000",
        "http://localhost:8000",
        "*"
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra env vars like VITE_MAPBOX_TOKEN


@lru_cache()
def get_settings() -> Settings:
    return Settings()
