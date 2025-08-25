from typing import Optional

from .indexer import RAGIndexer
from .searcher import RAGSearcher
from .shared import RAGBase
from ..config import config

__all__ = ['RAGIndexer', 'RAGSearcher', 'RAGBase', 'RAGService']


class RAGService:
    """RAGサービスの統合クラス（後方互換性のため）。
    
    内部でRAGIndexerとRAGSearcherを使用し、既存のAPIを維持。
    """
    
    def __init__(self, chromadb_path: str, provider_type: Optional[str] = None):
        """初期化。
        
        Args:
            chromadb_path: ChromaDB 永続化ディレクトリパス
            provider_type: AIプロバイダタイプ
        """
        self.indexer = RAGIndexer(chromadb_path, provider_type)
        self.searcher = RAGSearcher(chromadb_path, provider_type)
        
        # 後方互換性のため、既存のAPIを転送
        self.ai_provider = self.searcher.ai_provider
        self.chromadb_path = chromadb_path
        self.collection = self.searcher.collection
        
        # 後方互換性のため、設定値を属性として公開
        self.ollama_base_url = config.ollama_base_url
        self.ollama_model = config.ollama_model
    
    def index_issues(self, issues, full_rebuild=False):
        """課題一覧をインデックス（indexerに転送）。"""
        return self.indexer.index_issues(issues, full_rebuild)
    
    def search_similar_issues(self, query, n_results=5, exclude_issue_id=None):
        """類似課題検索（searcherに転送）。"""
        return self.searcher.search_similar_issues(query, n_results, exclude_issue_id)
    
    def generate_advice(self, issue_description, similar_issues):
        """アドバイス生成（searcherに転送）。"""
        return self.searcher.generate_advice(issue_description, similar_issues)
    
    def generate_advice_for_issue(self, issue):
        """課題に対するアドバイス生成（searcherに転送）。"""
        return self.searcher.generate_advice_for_issue(issue)
    
    def get_index_stats(self):
        """インデックス統計情報（indexerに転送）。"""
        return self.indexer.get_index_stats()
