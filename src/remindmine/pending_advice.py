"""Pending advice management for RemindMine."""

import logging
import json
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class PendingAdvice:
    """Represents a pending AI advice waiting for user approval."""
    
    id: str  # Unique identifier
    issue_id: int
    issue_subject: str
    issue_description: str
    advice_content: str
    created_at: str  # ISO format
    issue_url: str
    project_name: str
    tracker_name: str
    priority_name: str
    status_name: str
    
    @classmethod
    def from_issue_and_advice(cls, issue: Dict[str, Any], advice: str) -> 'PendingAdvice':
        """Create PendingAdvice from issue data and advice content."""
        issue_id = issue['id']
        timestamp = datetime.now(timezone.utc).isoformat()
        
        return cls(
            id=str(issue_id),  # Use issue_id as the unique identifier
            issue_id=issue_id,
            issue_subject=issue.get('subject', 'No subject'),
            issue_description=issue.get('description', 'No description'),
            advice_content=advice,
            created_at=timestamp,
            issue_url=f"{issue.get('id')}/",  # Will be completed with base URL
            project_name=issue.get('project', {}).get('name', 'Unknown'),
            tracker_name=issue.get('tracker', {}).get('name', 'Unknown'),
            priority_name=issue.get('priority', {}).get('name', 'Unknown'),
            status_name=issue.get('status', {}).get('name', 'Unknown'),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class PendingAdviceManager:
    """Manages pending AI advice that awaits user approval."""
    
    def __init__(self, storage_file: str = "data/pending_advice.json"):
        """Initialize the manager.
        
        Args:
            storage_file: Path to JSON file for storing pending advice
        """
        self.storage_file = storage_file
        self._pending_advice: Dict[str, PendingAdvice] = {}
        self._load_from_storage()
    
    def add_pending_advice(self, issue: Dict[str, Any], advice: str) -> str:
        """Add new pending advice.
        
        Args:
            issue: Issue dictionary from Redmine API
            advice: Generated AI advice content
            
        Returns:
            ID of the created pending advice
        """
        try:
            pending = PendingAdvice.from_issue_and_advice(issue, advice)
            
            # Check if there's already pending advice for this issue
            if pending.id in self._pending_advice:
                logger.info(f"Replacing existing pending advice for issue #{pending.issue_id}")
            
            self._pending_advice[pending.id] = pending
            self._save_to_storage()
            
            logger.info(f"Added pending advice for issue #{pending.issue_id} with ID {pending.id}")
            return pending.id
            
        except Exception as e:
            logger.error(f"Failed to add pending advice: {e}")
            raise
    
    def get_all_pending(self) -> List[PendingAdvice]:
        """Get all pending advice."""
        return list(self._pending_advice.values())
    
    def get_pending_by_id(self, advice_id: str) -> Optional[PendingAdvice]:
        """Get pending advice by ID.
        
        Args:
            advice_id: ID of the pending advice
            
        Returns:
            PendingAdvice object or None if not found
        """
        return self._pending_advice.get(advice_id)
    
    def get_pending_by_issue_id(self, issue_id: int) -> Optional[PendingAdvice]:
        """Get pending advice by issue ID.
        
        Args:
            issue_id: ID of the issue
            
        Returns:
            PendingAdvice object or None if not found
        """
        return self._pending_advice.get(str(issue_id))
    
    def approve_advice(self, advice_id: str) -> Optional[PendingAdvice]:
        """Approve and remove pending advice.
        
        Args:
            advice_id: ID of the pending advice to approve
            
        Returns:
            Removed PendingAdvice object or None if not found
        """
        try:
            pending = self._pending_advice.pop(advice_id, None)
            if pending:
                self._save_to_storage()
                logger.info(f"Approved pending advice {advice_id} for issue #{pending.issue_id}")
            return pending
            
        except Exception as e:
            logger.error(f"Failed to approve pending advice {advice_id}: {e}")
            raise
    
    def reject_advice(self, advice_id: str) -> Optional[PendingAdvice]:
        """Reject and remove pending advice.
        
        Args:
            advice_id: ID of the pending advice to reject
            
        Returns:
            Removed PendingAdvice object or None if not found
        """
        try:
            pending = self._pending_advice.pop(advice_id, None)
            if pending:
                self._save_to_storage()
                logger.info(f"Rejected pending advice {advice_id} for issue #{pending.issue_id}")
            return pending
            
        except Exception as e:
            logger.error(f"Failed to reject pending advice {advice_id}: {e}")
            raise
    
    def get_pending_count(self) -> int:
        """Get count of pending advice."""
        return len(self._pending_advice)
    
    def clear_all_pending(self) -> int:
        """Clear all pending advice.
        
        Returns:
            Number of advice items cleared
        """
        try:
            count = len(self._pending_advice)
            self._pending_advice.clear()
            self._save_to_storage()
            logger.info(f"Cleared {count} pending advice items")
            return count
            
        except Exception as e:
            logger.error(f"Failed to clear pending advice: {e}")
            raise
    
    def _load_from_storage(self):
        """Load pending advice from storage file."""
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                for advice_id, advice_data in data.items():
                    self._pending_advice[advice_id] = PendingAdvice(**advice_data)
                    
                logger.info(f"Loaded {len(self._pending_advice)} pending advice items from storage")
            else:
                logger.info("No pending advice storage file found, starting fresh")
                
        except Exception as e:
            logger.error(f"Failed to load pending advice from storage: {e}")
            # Continue with empty storage
            self._pending_advice = {}
    
    def _save_to_storage(self):
        """Save pending advice to storage file."""
        try:
            # Ensure data directory exists
            os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
            
            # Convert to dict for JSON serialization
            data = {
                advice_id: pending.to_dict() 
                for advice_id, pending in self._pending_advice.items()
            }
            
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save pending advice to storage: {e}")
            raise


# Global instance
pending_advice_manager = PendingAdviceManager()
