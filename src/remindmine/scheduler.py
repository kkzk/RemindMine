"""Scheduler for periodic RAG database updates."""

import logging
import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .redmine_client import RedmineClient
    from .rag_service import RAGService

logger = logging.getLogger(__name__)


class UpdateScheduler:
    """Scheduler for periodic RAG updates."""
    
    def __init__(self, redmine_client: "RedmineClient", rag_service: "RAGService", interval_minutes: int):
        """Initialize scheduler.
        
        Args:
            redmine_client: Redmine client instance
            rag_service: RAG service instance
            interval_minutes: Update interval in minutes
        """
        self.redmine_client = redmine_client
        self.rag_service = rag_service
        self.interval_minutes = interval_minutes
        self.interval_seconds = interval_minutes * 60
        
        self._stop_event = threading.Event()
        self._thread = None
    
    def start(self):
        """Start the scheduler."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("Scheduler is already running")
            return
        
        logger.info(f"Starting scheduler with {self.interval_minutes} minute intervals")
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
    
    def stop(self):
        """Stop the scheduler."""
        if self._thread is None:
            return
        
        logger.info("Stopping scheduler...")
        self._stop_event.set()
        self._thread.join(timeout=10)
        
        if self._thread.is_alive():
            logger.warning("Scheduler thread did not stop gracefully")
        else:
            logger.info("Scheduler stopped successfully")
    
    def _run(self):
        """Main scheduler loop."""
        # Initial update
        self._update_rag()
        
        while not self._stop_event.is_set():
            # Wait for interval or stop event
            if self._stop_event.wait(timeout=self.interval_seconds):
                break
            
            # Perform update
            self._update_rag()
    
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
