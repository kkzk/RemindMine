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
            'default_project_id': self.default_project_id,
            'default_tracker_id': self.default_tracker_id,
            'default_priority_id': self.default_priority_id,
            'default_status_id': self.default_status_id,
        }


# Global web config instance
web_config = WebConfig.from_env()
