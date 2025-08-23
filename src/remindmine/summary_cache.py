"""Issue summary cache service for managing cached summaries."""

import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional
from hashlib import md5

logger = logging.getLogger(__name__)


class SummaryCacheService:
    """Service for caching and managing issue summaries."""
    
    def __init__(self, cache_file_path: str):
        """Initialize cache service.
        
        Args:
            cache_file_path: Path to the cache file
        """
        self.cache_file_path = cache_file_path
        self._cache = {}
        self._load_cache()
    
    def _load_cache(self):
        """Load cache from file."""
        try:
            if os.path.exists(self.cache_file_path):
                with open(self.cache_file_path, 'r', encoding='utf-8') as f:
                    self._cache = json.load(f)
                logger.info(f"Loaded {len(self._cache)} cached summaries")
            else:
                self._cache = {}
                logger.info("No existing cache file, starting fresh")
        except Exception as e:
            logger.error(f"Failed to load cache: {e}")
            self._cache = {}
    
    def _save_cache(self):
        """Save cache to file."""
        try:
            # Ensure cache directory exists
            os.makedirs(os.path.dirname(self.cache_file_path), exist_ok=True)
            
            with open(self.cache_file_path, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
    
    def _get_issue_hash(self, issue: Dict[str, Any]) -> str:
        """Generate hash for issue content to detect changes.
        
        Args:
            issue: Issue dictionary
            
        Returns:
            Hash string for the issue content
        """
        # Create a hash based on subject, description, and journals
        content_parts = []
        
        content_parts.append(issue.get("subject", ""))
        content_parts.append(issue.get("description", ""))
        
        # Include journal content in hash
        if issue.get("journals"):
            for journal in issue["journals"]:
                notes = journal.get("notes", "")
                if notes and "🤖 AI自動アドバイス" not in notes:
                    content_parts.append(notes)
        
        content = "|".join(content_parts)
        return md5(content.encode('utf-8')).hexdigest()
    
    def _get_cache_key(self, issue_id: int) -> str:
        """Get cache key for an issue.
        
        Args:
            issue_id: Issue ID
            
        Returns:
            Cache key string
        """
        return str(issue_id)
    
    def get_cached_summary(self, issue: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get cached summary for an issue if it's still valid.
        
        Args:
            issue: Issue dictionary
            
        Returns:
            Cached summary data or None if not cached or outdated
        """
        try:
            issue_id = issue.get("id")
            if not issue_id:
                return None
            
            cache_key = self._get_cache_key(issue_id)
            cached_data = self._cache.get(cache_key)
            
            if not cached_data:
                return None
            
            # Check if content has changed by comparing hash
            current_hash = self._get_issue_hash(issue)
            cached_hash = cached_data.get("content_hash")
            
            if current_hash != cached_hash:
                logger.debug(f"Content changed for issue {issue_id}, cache invalid")
                return None
            
            # Check if cache is too old (optional: add expiry time check here)
            # For now, we only check content changes
            
            logger.debug(f"Using cached summary for issue {issue_id}")
            return cached_data.get("summaries")
            
        except Exception as e:
            logger.error(f"Failed to get cached summary for issue {issue.get('id', 'unknown')}: {e}")
            return None
    
    def cache_summary(self, issue: Dict[str, Any], summaries: Dict[str, Any]):
        """Cache summary for an issue.
        
        Args:
            issue: Issue dictionary
            summaries: Summary data to cache
        """
        try:
            issue_id = issue.get("id")
            if not issue_id:
                return
            
            cache_key = self._get_cache_key(issue_id)
            content_hash = self._get_issue_hash(issue)
            
            self._cache[cache_key] = {
                "issue_id": issue_id,
                "content_hash": content_hash,
                "cached_at": datetime.now().isoformat(),
                "updated_on": issue.get("updated_on"),
                "summaries": summaries
            }
            
            # Save to file
            self._save_cache()
            logger.debug(f"Cached summary for issue {issue_id}")
            
        except Exception as e:
            logger.error(f"Failed to cache summary for issue {issue.get('id', 'unknown')}: {e}")
    
    def invalidate_cache(self, issue_id: int):
        """Invalidate cache for a specific issue.
        
        Args:
            issue_id: Issue ID to invalidate
        """
        try:
            cache_key = self._get_cache_key(issue_id)
            if cache_key in self._cache:
                del self._cache[cache_key]
                self._save_cache()
                logger.debug(f"Invalidated cache for issue {issue_id}")
        except Exception as e:
            logger.error(f"Failed to invalidate cache for issue {issue_id}: {e}")
    
    def clear_cache(self):
        """Clear all cached data."""
        try:
            self._cache = {}
            self._save_cache()
            logger.info("Cleared all cached summaries")
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        try:
            return {
                "total_cached_issues": len(self._cache),
                "cache_file_path": self.cache_file_path,
                "cache_file_exists": os.path.exists(self.cache_file_path)
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {
                "total_cached_issues": 0,
                "cache_file_path": self.cache_file_path,
                "cache_file_exists": False
            }
