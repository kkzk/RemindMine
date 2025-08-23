"""Web UI configuration for RemindMine."""

import os
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class WebConfig:
    """Web UI configuration."""
    
    # Auto-advice settings
    auto_advice_enabled: bool = True
    
    # Display settings
    issues_per_page: int = 20
    max_advice_length: int = 1000
    
    # AI Provider settings
    ai_provider: str = "ollama"  # "ollama" or "openai"
    ollama_model: str = "llama3.2"
    ollama_embedding_model: str = "llama3.2"
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    
    # Redmine issue creation defaults
    default_project_id: int = 1
    default_tracker_id: int = 1
    default_priority_id: int = 2  # Normal priority
    default_status_id: int = 1    # New status
    
    @classmethod
    def from_env(cls) -> 'WebConfig':
        """Create config from environment variables."""
        return cls(
            auto_advice_enabled=os.getenv('AUTO_ADVICE_ENABLED', 'true').lower() == 'true',
            issues_per_page=int(os.getenv('ISSUES_PER_PAGE', '20')),
            max_advice_length=int(os.getenv('MAX_ADVICE_LENGTH', '1000')),
            ai_provider=os.getenv('AI_PROVIDER', 'ollama'),
            ollama_model=os.getenv('OLLAMA_MODEL', 'llama3.2'),
            ollama_embedding_model=os.getenv('OLLAMA_EMBEDDING_MODEL', 'llama3.2'),
            openai_model=os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
            openai_embedding_model=os.getenv('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small'),
            default_project_id=int(os.getenv('DEFAULT_PROJECT_ID', '1')),
            default_tracker_id=int(os.getenv('DEFAULT_TRACKER_ID', '1')),
            default_priority_id=int(os.getenv('DEFAULT_PRIORITY_ID', '2')),
            default_status_id=int(os.getenv('DEFAULT_STATUS_ID', '1')),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            'auto_advice_enabled': self.auto_advice_enabled,
            'issues_per_page': self.issues_per_page,
            'max_advice_length': self.max_advice_length,
            'ai_provider': self.ai_provider,
            'ollama_model': self.ollama_model,
            'ollama_embedding_model': self.ollama_embedding_model,
            'openai_model': self.openai_model,
            'openai_embedding_model': self.openai_embedding_model,
            'default_project_id': self.default_project_id,
            'default_tracker_id': self.default_tracker_id,
            'default_priority_id': self.default_priority_id,
            'default_status_id': self.default_status_id,
        }


# Global web config instance
web_config = WebConfig.from_env()
