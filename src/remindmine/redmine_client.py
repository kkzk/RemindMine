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

    def get_issues_since(self, since_datetime: datetime) -> List[Dict[str, Any]]:
        """Get issues created since the specified datetime.
        
        Args:
            since_datetime: Datetime to filter issues from
            
        Returns:
            List of new issues
        """
        # Format datetime for Redmine API (ISO format)
        since_str = since_datetime.strftime('%Y-%m-%dT%H:%M:%SZ')
        
        url = f"{self.base_url}/issues.json"
        params = {
            'created_on': f">={since_str}",
            'sort': 'created_on:desc',
            'limit': 100,
            'include': 'journals'
        }
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            issues = data.get('issues', [])
            logger.info(f"Found {len(issues)} issues created since {since_str}")
            return issues
        except requests.RequestException as e:
            logger.error(f"Failed to fetch issues since {since_str}: {e}")
            return []

    def get_latest_issue_creation_time(self) -> Optional[datetime]:
        """Get the creation time of the most recently created issue.
        
        Returns:
            Datetime of the latest issue creation, or None if no issues exist
        """
        url = f"{self.base_url}/issues.json"
        params = {
            'sort': 'created_on:desc',
            'limit': 1
        }
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            issues = data.get('issues', [])
            
            if issues:
                created_on_str = issues[0]['created_on']
                # Parse Redmine datetime format
                return datetime.fromisoformat(created_on_str.replace('Z', '+00:00'))
            return None
        except requests.RequestException as e:
            logger.error(f"Failed to fetch latest issue creation time: {e}")
            return None

    def has_ai_comment(self, issue_id: int, ai_signature: str = "AI自動アドバイス") -> bool:
        """Check if an issue already has an AI comment.
        
        Args:
            issue_id: Issue ID
            ai_signature: Signature to identify AI comments
            
        Returns:
            True if AI comment exists, False otherwise
        """
        try:
            issue = self.get_issue(issue_id)
            if not issue or 'journals' not in issue:
                return False
            
            # Check all journals (comments) for AI signature
            for journal in issue['journals']:
                notes = journal.get('notes', '')
                if ai_signature in notes:
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Failed to check AI comment for issue {issue_id}: {e}")
            return False
