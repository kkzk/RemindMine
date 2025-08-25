"""RAG検索・アドバイス生成モジュール。

類似課題検索、アドバイス生成、プロンプト組み立てを担当。
"""

import logging
from typing import List, Dict, Any, Optional

from .shared import RAGBase
from ..config import config

logger = logging.getLogger(__name__)


class RAGSearcher(RAGBase):
    """RAG検索・アドバイス生成クラス。"""
    
    def search_similar_issues(self, query: str, n_results: int = 5, exclude_issue_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """類似課題チャンクを検索。"""
        try:
            fetch_n = n_results * 3 if exclude_issue_id is not None else n_results
            query_embedding = self.ai_provider.embed_query(query)

            # 次元チェック
            try:
                col_meta = self.collection.metadata or {}
                stored_dim = col_meta.get('embedding_dimension')
                if stored_dim and len(query_embedding) != stored_dim:
                    logger.error(f"Embedding dimension mismatch (stored={stored_dim}, query={len(query_embedding)})")
                    return []
            except Exception:
                pass
            
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=fetch_n
            )

            similar_issues: List[Dict[str, Any]] = []
            documents_list = results.get('documents') or []
            metadatas_list = results.get('metadatas') or []
            distances_list = results.get('distances') or []

            if documents_list and documents_list[0]:
                for i, doc in enumerate(documents_list[0]):
                    metadata = metadatas_list[0][i] if metadatas_list and metadatas_list[0] and i < len(metadatas_list[0]) else {}
                    if exclude_issue_id is not None and metadata.get('issue_id') == exclude_issue_id:
                        continue
                    distance = distances_list[0][i] if distances_list and distances_list[0] and i < len(distances_list[0]) else 1.0
                    similar_issues.append({
                        'content': doc,
                        'metadata': metadata,
                        'similarity': 1 - distance
                    })

            return similar_issues[:n_results]

        except Exception as e:
            logger.error(f"Failed to search similar issues: {e}")
            return []
    
    def generate_advice(self, issue_description: str, similar_issues: List[Dict[str, Any]]) -> str:
        """類似課題を踏まえてアドバイステキストを生成。"""
        context = self._create_context(similar_issues)
        prompt = self._create_advice_prompt(issue_description, context)
        
        try:
            advice = self.ai_provider.generate_completion(prompt)
            return advice.strip() if advice and advice.strip() else "申し訳ございませんが、アドバイスの生成に失敗しました。"
        except Exception as e:
            logger.error(f"Failed to generate advice: {e}")
            return "申し訳ございませんが、AIアドバイスの生成中にエラーが発生しました。"
    
    def generate_advice_for_issue(self, issue: Dict[str, Any]) -> Optional[str]:
        """特定の課題に対してAIアドバイスを生成。"""
        try:
            issue_description = self._create_issue_content(issue)
            similar_issues = self.search_similar_issues(issue_description, n_results=5, exclude_issue_id=issue.get('id'))
            advice = self.generate_advice(issue_description, similar_issues)
            
            if advice and advice.strip() and not advice.startswith("申し訳ございません"):
                return f"AI自動アドバイス:\n\n{advice}"
            return None
        except Exception as e:
            logger.error(f"Failed to generate advice for issue {issue.get('id', 'unknown')}: {e}")
            return None
    
    def _create_issue_content(self, issue: Dict[str, Any]) -> str:
        """課題辞書から検索対象テキストを生成。"""
        content_parts = []
        
        if issue.get('subject'):
            content_parts.append(f"件名: {issue['subject']}")
        if issue.get('description'):
            content_parts.append(f"説明: {issue['description']}")
        if issue.get('status'):
            content_parts.append(f"ステータス: {issue['status'].get('name', '')}")
        if issue.get('priority'):
            content_parts.append(f"優先度: {issue['priority'].get('name', '')}")
        if issue.get('tracker'):
            content_parts.append(f"トラッカー: {issue['tracker'].get('name', '')}")
        if issue.get('journals'):
            for journal in issue['journals']:
                if journal.get('notes'):
                    content_parts.append(f"コメント: {journal['notes']}")
        
        return "\n".join(content_parts)
    
    def _create_context(self, similar_issues: List[Dict[str, Any]]) -> str:
        """類似課題リストからコンテキスト文字列を生成。"""
        if not similar_issues:
            return "関連する過去の事例は見つかりませんでした。"
        
        context_parts = ["関連する過去の事例:"]
        for i, issue in enumerate(similar_issues[:3]):
            metadata = issue.get('metadata', {})
            content = issue.get('content', '')
            similarity = issue.get('similarity', 0)
            
            context_parts.append(f"\n事例 {i+1} (類似度: {similarity:.2f}):")
            context_parts.append(f"Issue ID: {metadata.get('issue_id')}")
            context_parts.append(f"件名: {metadata.get('subject')}")
            context_parts.append(f"内容: {content[:500]}...")
        
        return "\n".join(context_parts)
    
    def _create_advice_prompt(self, issue_description: str, context: str) -> str:
        """アドバイス生成用プロンプトを組み立て。"""
        template = self._load_prompt_template('advice.txt')
        if not template:
            return f"課題:\n{issue_description}\n\n{context}\n\nアドバイス:"
        return (template
                .replace('{{ISSUE_DESCRIPTION}}', issue_description)
                .replace('{{CONTEXT}}', context)
                .replace('{{REDMINE_URL}}', config.redmine_url))
