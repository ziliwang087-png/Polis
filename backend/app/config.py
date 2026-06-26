"""
Polis Backend Configuration
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Optional, List, Union

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    # Database
    DATABASE_URL: str
    
    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days
    
    # API
    ENV: str = "development"
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Polis API"
    PUBLIC_BASE_URL: str = "http://localhost:8000"
    RATE_LIMIT_ENABLED: bool = True
    HEALTH_DEEP_TOKEN: Optional[str] = None
    AUTH_COOKIE_NAME: str = "polis_token"
    AUTH_COOKIE_SAMESITE: Optional[str] = None
    AUTH_COOKIE_SECURE: Optional[bool] = None
    AUTH_COOKIE_MAX_AGE_SECONDS: int = 60 * 60 * 24 * 7

    # Supabase Storage
    SUPABASE_URL: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None
    SUPABASE_STORAGE_BUCKET: str = "polis-attachments"
    SUPABASE_DELIVERABLES_BUCKET: str = "task-deliverables"
    LOCAL_UPLOAD_DIR: str = "local_uploads"
    
    # CORS — declared as Union[str, List[str]] so pydantic-settings does NOT try
    # to JSON-parse the env value before our validator runs. Validator below
    # normalises to List[str], accepting JSON list, comma-separated, or already-list.
    CORS_ORIGINS: Union[str, List[str]] = (
        "http://localhost:3000,http://localhost:3001,"
        "https://polis-frontend-three.vercel.app"
    )

    @field_validator("CORS_ORIGINS", mode="after")
    @classmethod
    def _parse_cors(cls, v):
        if isinstance(v, list):
            return v
        s = str(v).strip()
        if s.startswith("["):
            import json
            return json.loads(s)
        return [x.strip() for x in s.split(",") if x.strip()]
    
settings = Settings()
