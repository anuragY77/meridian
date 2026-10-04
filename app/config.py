# app/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_transactions: str = "transactions_raw"
    redis_host: str = "localhost"
    redis_port: int = 6379
    postgres_url: str
    simulator_tps: float = 2.0
    exploration_epsilon: float = 0.15
    rolling_window_size: int = 50          # how many recent outcomes per gateway to track
    routing_strategy: str = "ml"           # "ml" or "rule" — feature flag to switch routing logic
    sla_resolution_days: float = 7.0

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
