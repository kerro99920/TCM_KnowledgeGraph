"""Configuration management using Pydantic Settings v2."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    # LLM 配置（环境变量名与 .env.example 对齐）
    llm_api_key: SecretStr = Field(
        description="API key for LLM service",
        validation_alias="MODEL_API_KEY",
    )
    llm_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        description="Base URL for LLM API",
        validation_alias="MODEL_BASE_URL",
    )
    llm_model: str = Field(
        default="qwen3-max",
        description="LLM model name",
        validation_alias="MODEL_NAME",
    )
    llm_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="LLM temperature for generation",
    )
    llm_max_tokens: int = Field(
        default=4096,
        ge=1,
        description="Maximum tokens for LLM response",
    )

    # Neo4j Configuration
    neo4j_uri: str = Field(
        default="bolt://localhost:7687",
        description="Neo4j connection URI",
    )
    neo4j_user: str = Field(
        default="neo4j",
        description="Neo4j username",
    )
    neo4j_password: SecretStr = Field(description="Neo4j password")
    neo4j_database: str = Field(
        default="neo4j",
        description="Neo4j database name",
    )

    # Crawler Configuration
    crawler_timeout: float = Field(
        default=15.0,
        ge=1.0,
        description="HTTP request timeout in seconds",
    )
    crawler_max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum retry attempts for failed requests",
    )
    crawler_delay: float = Field(
        default=1.0,
        ge=0.0,
        description="Delay between requests in seconds",
    )
    crawler_concurrent_limit: int = Field(
        default=5,
        ge=1,
        description="Maximum concurrent requests",
    )

    # Application Configuration
    history_turns: int = Field(
        default=5,
        ge=1,
        description="Number of conversation history turns to keep",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level",
    )
    log_format: Literal["json", "text"] = Field(
        default="text",
        description="Log output format",
    )

    # Data Paths
    data_dir: Path = Field(
        default=Path("data"),
        description="Base data directory",
    )

    @field_validator("data_dir", mode="before")
    @classmethod
    def convert_to_path(cls, v: str | Path) -> Path:
        """Convert string paths to Path objects."""
        return Path(v) if isinstance(v, str) else v

    @property
    def raw_data_dir(self) -> Path:
        """Directory for raw crawled data."""
        return self.data_dir / "raw"

    @property
    def medicines_dir(self) -> Path:
        """Directory for medicine detail files."""
        return self.raw_data_dir / "medicines"

    @property
    def prescriptions_dir(self) -> Path:
        """Directory for prescription detail files."""
        return self.raw_data_dir / "prescriptions"

    @property
    def exports_dir(self) -> Path:
        """Directory for exported files."""
        return self.data_dir / "exports"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
