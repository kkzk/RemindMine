"""Scheduler for periodic RAG database updates and new issue monitoring."""

import logging
import threading
import time
from typing import TYPE_CHECKING, Optional
from datetime import datetime, timezone

if TYPE_CHECKING:
    from .redmine_client import RedmineClient
    from .rag_service import RAGService

logger = logging.getLogger(__name__)


class UpdateScheduler:
    """Scheduler for periodic RAG updates and new issue monitoring."""
    
    def __init__(self, redmine_client: "RedmineClient", rag_service: "RAGService", 
                 interval_minutes: int, polling_interval_minutes: int = 5):
        """Initialize scheduler.
        
        Args:
            redmine_client: Redmine client instance
            rag_service: RAG service instance
            interval_minutes: RAG update interval in minutes
            polling_interval_minutes: New issue polling interval in minutes
        """
        self.redmine_client = redmine_client
        self.rag_service = rag_service
        self.interval_minutes = interval_minutes
        self.interval_seconds = interval_minutes * 60
        self.polling_interval_minutes = polling_interval_minutes
        self.polling_interval_seconds = polling_interval_minutes * 60
        
        self._stop_event = threading.Event()
        self._rag_thread = None
        self._polling_thread = None
        self._last_check_time: Optional[datetime] = None
    
    def start(self):
        """Start the scheduler."""
        if (self._rag_thread is not None and self._rag_thread.is_alive()) or \
           (self._polling_thread is not None and self._polling_thread.is_alive()):
            logger.warning("Scheduler is already running")
            return
        
        logger.info(f"Starting scheduler with {self.interval_minutes} minute RAG intervals and {self.polling_interval_minutes} minute polling intervals")
        self._stop_event.clear()
        
        # Initialize last check time to current time
        self._last_check_time = datetime.now(timezone.utc)
        
        # Start RAG update thread
        self._rag_thread = threading.Thread(target=self._run_rag_updates, daemon=True)
        self._rag_thread.start()
        
        # Start new issue polling thread
        self._polling_thread = threading.Thread(target=self._run_issue_polling, daemon=True)
        self._polling_thread.start()
    
    def stop(self):
        """Stop the scheduler."""
        if self._rag_thread is None and self._polling_thread is None:
            return
        
        logger.info("Stopping scheduler...")
        self._stop_event.set()
        
        if self._rag_thread:
            self._rag_thread.join(timeout=10)
            if self._rag_thread.is_alive():
                logger.warning("RAG update thread did not stop gracefully")
        
        if self._polling_thread:
            self._polling_thread.join(timeout=10)
            if self._polling_thread.is_alive():
                logger.warning("Issue polling thread did not stop gracefully")
        
        if (self._rag_thread is None or not self._rag_thread.is_alive()) and \
           (self._polling_thread is None or not self._polling_thread.is_alive()):
            logger.info("Scheduler stopped successfully")
    
    def _run_rag_updates(self):
        """Main RAG update loop."""
        # Initial update
        self._update_rag()
        
        while not self._stop_event.is_set():
            # Wait for interval or stop event
            if self._stop_event.wait(timeout=self.interval_seconds):
                break
            
            # Perform update
            self._update_rag()
    
    def _run_issue_polling(self):
        """Main issue polling loop."""
        while not self._stop_event.is_set():
            # Wait for polling interval or stop event
            if self._stop_event.wait(timeout=self.polling_interval_seconds):
                break
            
            # Check for new issues
            self._check_new_issues()
    
    def _update_rag(self):
        """Update RAG database with latest issues."""
        try:
            logger.info("Starting scheduled RAG update...")
            
            # Fetch all issues with journals
            issues = self.redmine_client.get_all_issues_with_journals()
            
            # Index issues in RAG
            self.rag_service.index_issues(issues)
            
            logger.info("Scheduled RAG update completed successfully")
            
        except Exception as e:
            logger.error(f"Scheduled RAG update failed: {e}")
    
    def _check_new_issues(self):
        """Check for new issues and process them."""
        try:
            if self._last_check_time is None:
                # Initialize with current time if not set
                self._last_check_time = datetime.now(timezone.utc)
                return
            
            # Get new issues since last check
            new_issues = self.redmine_client.get_issues_since(self._last_check_time)
            
            if new_issues:
                logger.info(f"Found {len(new_issues)} new issues")
                
                # Process each new issue
                for issue in new_issues:
                    self._process_new_issue(issue)
                
                # Update last check time to the creation time of the newest issue
                # or current time if no issues found
                latest_time = max(
                    datetime.fromisoformat(issue['created_on'].replace('Z', '+00:00'))
                    for issue in new_issues
                )
                self._last_check_time = latest_time
            else:
                # Update last check time to current time
                self._last_check_time = datetime.now(timezone.utc)
                
        except Exception as e:
            logger.error(f"Failed to check for new issues: {e}")
    
    def _process_new_issue(self, issue: dict):
        """Process a newly created issue.
        
        Args:
            issue: Issue dictionary from Redmine API
        """
        try:
            issue_id = issue['id']
            issue_subject = issue.get('subject', 'No subject')
            
            logger.info(f"Processing new issue #{issue_id}: {issue_subject}")
            
            # Generate AI advice for the new issue
            advice = self.rag_service.generate_advice_for_issue(issue)
            
            if advice:
                # Post the advice as a comment
                success = self.redmine_client.add_comment(issue_id, advice)
                if success:
                    logger.info(f"Successfully posted AI advice to issue #{issue_id}")
                else:
                    logger.error(f"Failed to post AI advice to issue #{issue_id}")
            else:
                logger.warning(f"No AI advice generated for issue #{issue_id}")
                
        except Exception as e:
            logger.error(f"Failed to process new issue #{issue.get('id', 'unknown')}: {e}")
