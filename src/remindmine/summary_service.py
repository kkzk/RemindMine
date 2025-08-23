"""Issue and journal summary service using LLM.

変更点:
 - 要約保存時の強制トランケートを廃止し、LLM出力(=フル要約)をそのままキャッシュへ保存。
 - プロンプト内の目安文字数 (LIMIT) をテンプレート側で固定 (200) 指定する方式へ変更。
 - 以前使用していた CONTENT_SUMMARY_PROMPT_LIMIT / JOURNAL_SUMMARY_PROMPT_LIMIT 環境変数は廃止。
 - SUMMARY_ENFORCE_TRUNCATE のみ継続 (true/false 既定: false)。true の場合はテンプレートの想定(=200)を上限とみなし末尾を ... で切り詰め。
"""

import logging
import os
from typing import Dict, Any, Optional
import requests
from .summary_cache import SummaryCacheService

logger = logging.getLogger(__name__)


class SummaryService:
    """Service for generating a unified current-state summary of an issue (content + journals)."""
    
    def __init__(self, ollama_base_url: str, ollama_model: str, cache_file_path: Optional[str] = None):
        self.ollama_base_url = ollama_base_url
        self.ollama_model = ollama_model
        # 設定: 文字数目安はテンプレート固定 (200)。環境変数による変更は廃止。
        self.PROMPT_LIMIT = 200
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
    
    def summarize_issue_current_state(self, issue: Dict[str, Any]) -> Optional[str]:
        """Issue 本文 (件名/説明) とユーザーコメント(ジャーナル) を統合し「現在の状態」を要約する。

        既存の content_summary / journal_summary を統合する新仕様。
        互換性のため呼び出し元では 'content_summary' フィールドに格納し、
        'journal_summary' は今後 None を返す。
        """
        try:
            subject = issue.get("subject", "").strip()
            description = issue.get("description", "").strip()
            journals = issue.get("journals", []) or []
            prompt_limit = self.PROMPT_LIMIT

            if not subject and not description and not journals:
                return None

            parts = []
            if subject:
                parts.append(f"[件名]\n{subject}")
            if description:
                parts.append(f"[説明]\n{description}")

            # 有効ジャーナル（AIアドバイス除外）
            meaningful = []
            for j in journals:
                notes = (j.get("notes") or "").strip()
                if not notes:
                    continue
                if "🤖 AI自動アドバイス" in notes:
                    continue
                user = j.get("user", {}).get("name", "Unknown")
                created_on = j.get("created_on", "")
                meaningful.append(f"[{user}] {notes}")

            if meaningful:
                parts.append("[コメント]" + "\n" + "\n".join(meaningful))

            combined = "\n\n".join(parts)

            template = self._load_template('unified_issue_summary.txt')
            if not template:
                return None
            prompt = template.replace('{{ISSUE_AND_JOURNALS}}', combined)

            summary = self._chat_with_ollama(prompt)
            if summary:
                summary = summary.strip()
                if self.enforce_truncate and prompt_limit and len(summary) > prompt_limit:
                    summary = summary[:prompt_limit - 3] + '...'
                return summary
            return None
        except Exception as e:
            logger.error(f"Failed to create unified issue summary: {e}")
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
                    # 旧フォーマット (journal_summary が存在し値あり) は再生成対象
                    if cached_summary.get("journal_summary"):
                        logger.debug("Legacy separate summaries detected; regenerating unified summary")
                    else:
                        logger.debug(f"Using cached summary for issue {issue.get('id')}")
                        return cached_summary
            
            # Generate new summaries
            logger.debug(f"Generating new summary for issue {issue.get('id')}")
            unified = self.summarize_issue_current_state(issue)
            summary_data = {
                # 新仕様: content_summary に統合サマリを格納。journal_summary は互換のため残すが None。
                "content_summary": unified,
                "journal_summary": None,
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
