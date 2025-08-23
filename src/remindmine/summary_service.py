"""Issue and journal summary service using LLM.

変更点:
 - 要約保存時の強制トランケートを廃止し、LLM出力(=フル要約)をそのままキャッシュへ保存。
 - 環境変数でプロンプト上の目安文字数・トランケート有無を制御可能に。
     * CONTENT_SUMMARY_PROMPT_LIMIT (既定: 500)
     * JOURNAL_SUMMARY_PROMPT_LIMIT (既定: 800)
     * SUMMARY_ENFORCE_TRUNCATE (true/false 既定: false) -> true の場合のみ末尾を ... で切り詰め
"""

import logging
import os
from typing import Dict, Any, Optional
import requests
from .summary_cache import SummaryCacheService

logger = logging.getLogger(__name__)


class SummaryService:
    """Service for generating summaries of issues and journals using LLM."""
    
    def __init__(self, ollama_base_url: str, ollama_model: str, cache_file_path: Optional[str] = None):
        self.ollama_base_url = ollama_base_url
        self.ollama_model = ollama_model

        # 設定 (環境変数)
        self.content_summary_prompt_limit = int(os.getenv('CONTENT_SUMMARY_PROMPT_LIMIT', '500'))
        self.journal_summary_prompt_limit = int(os.getenv('JOURNAL_SUMMARY_PROMPT_LIMIT', '800'))
        self.enforce_truncate = os.getenv('SUMMARY_ENFORCE_TRUNCATE', 'false').lower() in ('1', 'true', 'yes')

        # Prompt templates directory (same package /prompts)
        self.prompts_dir = os.path.join(os.path.dirname(__file__), 'prompts')
        # Initialize cache service
        if cache_file_path:
            self.cache_service = SummaryCacheService(cache_file_path)
        else:
            self.cache_service = None

    def _load_template(self, name: str) -> Optional[str]:
        """Load prompt template text by filename (without path)."""
        try:
            path = os.path.join(self.prompts_dir, name)
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to load prompt template {name}: {e}")
            return None
    
    def _chat_with_ollama(self, prompt: str) -> Optional[str]:
        """Chat with Ollama LLM.
        
        Args:
            prompt: Prompt to send to LLM
            
        Returns:
            Response from LLM or None if failed
        """
        try:
            url = f"{self.ollama_base_url}/api/generate"
            data = {
                "model": self.ollama_model,
                "prompt": prompt,
                "stream": False
            }
            
            response = requests.post(url, json=data, timeout=60)
            response.raise_for_status()
            result = response.json()
            
            return result.get("response", "").strip()
            
        except Exception as e:
            logger.error(f"Failed to chat with Ollama: {e}")
            return None
    
    def summarize_issue_content(self, issue: Dict[str, Any], max_length: Optional[int] = None) -> Optional[str]:
        """
        Summarize issue title and description.
        
        Args:
            issue: Issue data from Redmine
            max_length: (任意) プロンプトへ渡す目安文字数。None の場合は content_summary_prompt_limit を使用。
            
        Returns:
            Summarized content or None if failed
        """
        try:
            subject = issue.get("subject", "")
            description = issue.get("description", "")

            prompt_limit = max_length if max_length is not None else self.content_summary_prompt_limit
            
            if not subject and not description:
                return None
            
            # Prepare content to summarize
            content_parts = []
            if subject:
                content_parts.append(f"件名: {subject}")
            if description:
                content_parts.append(f"説明: {description}")
            
            content = "\n".join(content_parts)
            
            template = self._load_template('content_summary.txt')
            if not template:
                return None
            prompt = (template
                      .replace('{{LIMIT}}', str(prompt_limit))
                      .replace('{{CONTENT}}', content))
            
            summary = self._chat_with_ollama(prompt)
            if summary:
                summary = summary.strip()
                # 任意で強制トランケート
                if self.enforce_truncate and prompt_limit and len(summary) > prompt_limit:
                    summary = summary[:prompt_limit - 3] + '...'
                return summary
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to summarize issue content: {e}")
            return None
    
    def summarize_journals(self, issue: Dict[str, Any], max_length: Optional[int] = None) -> Optional[str]:
        """
        Summarize issue journals/comments.
        
        Args:
            issue: Issue data from Redmine with journals
            max_length: (任意) プロンプトへ渡す目安文字数。None の場合は journal_summary_prompt_limit を使用。
            
        Returns:
            Summarized journal content or None if no journals or failed
        """
        try:
            journals = issue.get("journals", [])
            prompt_limit = max_length if max_length is not None else self.journal_summary_prompt_limit
            if not journals:
                return None
            
            # Filter out AI advice comments and collect meaningful journal entries
            meaningful_journals = []
            for journal in journals:
                notes = journal.get("notes", "").strip()
                if not notes:
                    continue
                
                # Skip AI advice comments
                if "🤖 AI自動アドバイス" in notes:
                    continue
                
                # Add user and timestamp info
                user = journal.get("user", {}).get("name", "Unknown")
                created_on = journal.get("created_on", "")
                
                journal_entry = f"[{user}] {notes}"
                meaningful_journals.append(journal_entry)
            
            if not meaningful_journals:
                return None
            
            # Combine all journal entries
            all_journals = "\n\n".join(meaningful_journals)
            
            template = self._load_template('journal_summary.txt')
            if not template:
                return None
            prompt = (template
                      .replace('{{LIMIT}}', str(prompt_limit))
                      .replace('{{JOURNALS}}', all_journals))
            
            summary = self._chat_with_ollama(prompt)
            if summary:
                summary = summary.strip()
                if self.enforce_truncate and prompt_limit and len(summary) > prompt_limit:
                    summary = summary[:prompt_limit - 3] + '...'
                return summary
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to summarize journals: {e}")
            return None
    
    def get_issue_summary_data(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get comprehensive summary data for an issue.
        Uses cache to avoid regenerating summaries for unchanged issues.
        
        Args:
            issue: Issue data from Redmine
            
        Returns:
            Dictionary containing various summaries
        """
        try:
            # Try to get cached summary first
            if self.cache_service:
                cached_summary = self.cache_service.get_cached_summary(issue)
                if cached_summary:
                    logger.debug(f"Using cached summary for issue {issue.get('id')}")
                    return cached_summary
            
            # Generate new summaries
            logger.debug(f"Generating new summary for issue {issue.get('id')}")
            summary_data = {
                # フル要約を保存（強制トランケートは設定で制御）
                "content_summary": self.summarize_issue_content(issue),
                "journal_summary": self.summarize_journals(issue),
                "has_journals": bool(issue.get("journals")),
                "journal_count": len(issue.get("journals", []))
            }
            
            # Cache the new summaries
            if self.cache_service:
                self.cache_service.cache_summary(issue, summary_data)
            
            return summary_data
            
        except Exception as e:
            logger.error(f"Failed to get issue summary data: {e}")
            return {
                "content_summary": None,
                "journal_summary": None,
                "has_journals": False,
                "journal_count": 0
            }
    
    def clear_cache(self):
        """Clear all cached summaries."""
        if self.cache_service:
            self.cache_service.clear_cache()
    
    def invalidate_issue_cache(self, issue_id: int):
        """Invalidate cache for a specific issue."""
        if self.cache_service:
            self.cache_service.invalidate_cache(issue_id)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if self.cache_service:
            return self.cache_service.get_cache_stats()
        return {
            "total_cached_issues": 0,
            "cache_file_path": "N/A (cache disabled)",
            "cache_file_exists": False
        }
