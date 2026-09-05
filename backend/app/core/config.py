from pydantic_settings import BaseSettings
from typing import List, Optional
import os


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Monad Mate Trust API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = "postgresql://monadmate:monadmate@localhost:5432/monadmate"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10

    # Auth
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Monad (EVM)
    MONAD_RPC_URL: str = "https://testnet-rpc.monad.xyz"
    MONAD_NETWORK: str = "testnet"
    MONAD_CHAIN_ID: int = 10143
    MONAD_ESCROW_ADDRESS: Optional[str] = None
    MONAD_EVENT_LOG_ADDRESS: Optional[str] = None
    MONAD_PRIVATE_KEY: Optional[str] = None
    MONAD_KEYSTORE_PATH: str = "~/.monad/backend.key"

    # Hedera (HCS anchoring + reputation)
    HEDERA_ACCOUNT_ID: Optional[str] = None
    HEDERA_PRIVATE_KEY: Optional[str] = None
    HEDERA_NETWORK: str = "testnet"

    # ZeroDB (memory + vectors)
    ZERODB_API_URL: str = "https://api.ainative.studio"
    ZERODB_PROJECT_ID: Optional[str] = None
    ZERODB_USERNAME: Optional[str] = None
    ZERODB_PASSWORD: Optional[str] = None

    # AINative Studio — LLM gateway + ZeroDB embeddings
    # Enables: claude-sonnet-4.5 intro generation, 768-dim BAAI/bge embeddings,
    #          ZeroDB vector search for cross-user preference matching
    AINATIVE_API_URL: str = "https://api.ainative.studio"
    AINATIVE_API_KEY: Optional[str] = None  # sk_... from ainative.studio

    # Legacy / direct keys (unused — routed through AINative gateway instead)
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None

    # Coinbase x402 payment protocol (Base)
    X402_ENABLED: bool = False
    COINBASE_PAYMENT_ADDRESS: str = ""

    # Safety
    MIN_STAKE_DM_MON: float = 1.0
    MIN_STAKE_MEETUP_MON: float = 5.0
    MIN_STAKE_ROOM_MON: float = 0.5
    SLASH_AMOUNT_NO_SHOW: float = 5.0

    # CORS
    ALLOWED_ORIGINS: List[str] = ["*"]

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
