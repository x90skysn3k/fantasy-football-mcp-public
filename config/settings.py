"""
Configuration settings for the Fantasy Football MCP server.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.api.yahoo_credentials import PROJECT_ENV_PATH, load_project_environment

load_project_environment()
ENV_FILE_PATH = PROJECT_ENV_PATH


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Yahoo API Configuration
    yahoo_client_id: str = Field(..., validation_alias="YAHOO_CONSUMER_KEY")
    yahoo_client_secret: str = Field(..., validation_alias="YAHOO_CONSUMER_SECRET")

    # Cache Configuration
    cache_dir: Path = Field(default=Path("./.cache"), validation_alias="CACHE_DIR")
    cache_ttl_seconds: int = Field(default=3600, validation_alias="CACHE_TTL_SECONDS")

    # API Rate Limiting
    yahoo_api_rate_limit: int = Field(default=100, validation_alias="YAHOO_API_RATE_LIMIT")
    yahoo_api_rate_window_seconds: int = Field(
        default=3600, validation_alias="YAHOO_API_RATE_WINDOW_SECONDS"
    )

    # Logging
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    log_file: Path = Field(
        default=Path("./logs/yahoo_fantasy_football.log"), validation_alias="LOG_FILE"
    )

    # MCP Server Configuration
    mcp_server_name: str = Field(
        default="yahoo-fantasy-football", validation_alias="MCP_SERVER_NAME"
    )
    mcp_server_version: str = Field(default="1.0.0", validation_alias="MCP_SERVER_VERSION")

    # Parallel Processing
    max_workers: int = Field(default=10, validation_alias="MAX_WORKERS")
    async_timeout_seconds: int = Field(default=30, validation_alias="ASYNC_TIMEOUT_SECONDS")

    # Feature Flags
    enable_advanced_stats: bool = Field(default=True, validation_alias="ENABLE_ADVANCED_STATS")
    enable_weather_data: bool = Field(default=True, validation_alias="ENABLE_WEATHER_DATA")
    enable_injury_reports: bool = Field(default=True, validation_alias="ENABLE_INJURY_REPORTS")

    # Yahoo OAuth Configuration
    yahoo_redirect_uri: str = Field(
        default="https://localhost:8090", validation_alias="YAHOO_REDIRECT_URI"
    )
    yahoo_callback_port: int = Field(default=8090, validation_alias="YAHOO_CALLBACK_PORT")
    yahoo_callback_host: str = Field(default="localhost", validation_alias="YAHOO_CALLBACK_HOST")

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_file_encoding="utf-8",
        case_sensitive=False,
        populate_by_name=True,
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # Ensure log directory exists
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
