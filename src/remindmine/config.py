"""Configuration module for RemindMine."""

import os
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config(BaseModel):
    """Application configuration."""
    
    # Redmine settings
    redmine_url: str = os.getenv("REDMINE_URL", "http://localhost:3000")
    redmine_api_key: str = os.getenv("REDMINE_API_KEY", "")
    
    # Ollama settings
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.2")
    
    # ChromaDB settings
    chromadb_path: str = os.getenv("CHROMADB_PATH", "./data/chromadb")
    
    # FastAPI settings
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    
    # Update settings
    update_interval_minutes: int = int(os.getenv("UPDATE_INTERVAL_MINUTES", "60"))
    polling_interval_minutes: int = int(os.getenv("POLLING_INTERVAL_MINUTES", "5"))
    
    # AI comment settings
    ai_comment_signature: str = os.getenv("AI_COMMENT_SIGNATURE", "AI自動アドバイス")
    
    # Legacy webhook settings (deprecated)
    webhook_secret: Optional[str] = os.getenv("WEBHOOK_SECRET")


# Global config instance
config = Config()
