"""Redmine API client for fetching issues and posting comments."""

import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class RedmineClient:
    """Redmine API client."""
    
    def __init__(self, base_url: str, api_key: str):
        """Initialize Redmine client.
        
        Args:
            base_url: Redmine base URL
            api_key: Redmine API key
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'X-Redmine-API-Key': api_key,
            'Content-Type': 'application/json'
        })
    
    def get_issues(self, 
                   project_id: Optional[int] = None,
                   status_id: Optional[str] = None,
                   limit: int = 100,
                   offset: int = 0) -> List[Dict[str, Any]]:
        """Get issues from Redmine.
        
        Args:
            project_id: Project ID to filter by
            status_id: Status ID to filter by ('*' for all)
            limit: Number of issues to fetch
            offset: Offset for pagination
            
        Returns:
            List of issue dictionaries
        """
        url = f"{self.base_url}/issues.json"
        params = {
            'limit': limit,
            'offset': offset,
            'include': 'journals'
        }
        
        if project_id:
            params['project_id'] = project_id
        if status_id:
            params['status_id'] = status_id
            
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get('issues', [])
        except requests.RequestException as e:
            logger.error(f"Failed to fetch issues: {e}")
            return []
    
    def get_issue(self, issue_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific issue.
        
        Args:
            issue_id: Issue ID
            
        Returns:
            Issue dictionary or None if not found
        """
        url = f"{self.base_url}/issues/{issue_id}.json"
        params = {'include': 'journals'}
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get('issue')
        except requests.RequestException as e:
            logger.error(f"Failed to fetch issue {issue_id}: {e}")
            return None
    
    def add_comment(self, issue_id: int, notes: str) -> bool:
        """Add a comment to an issue.
        
        Args:
            issue_id: Issue ID
            notes: Comment text
            
        Returns:
            True if successful, False otherwise
        """
        url = f"{self.base_url}/issues/{issue_id}.json"
        data = {
            'issue': {
                'notes': notes
            }
        }
        
        try:
            response = self.session.put(url, json=data)
            response.raise_for_status()
            logger.info(f"Successfully added comment to issue {issue_id}")
            return True
        except requests.RequestException as e:
            logger.error(f"Failed to add comment to issue {issue_id}: {e}")
            return False
    
    def get_all_issues_with_journals(self) -> List[Dict[str, Any]]:
        """Get all issues with their journals for RAG indexing.
        
        Returns:
            List of issues with journals
        """
        all_issues = []
        offset = 0
        limit = 100
        
        while True:
            issues = self.get_issues(status_id='*', limit=limit, offset=offset)
            if not issues:
                break
                
            all_issues.extend(issues)
            
            if len(issues) < limit:
                break
                
            offset += limit
            
        logger.info(f"Fetched {len(all_issues)} issues total")
        return all_issues
