"""RAGサービスの共通機能モジュール。

ChromaDB接続管理、AI Provider初期化、設定管理などの共通機能を提供。
"""

import logging
from typing import Optional
import chromadb
from chromadb.config import Settings
from langchain.text_splitter import RecursiveCharacterTextSplitter
import os

from ..config import config
from ..ai_providers import create_ai_provider

logger = logging.getLogger(__name__)


class RAGBase:
    """RAG関連クラスの基底クラス。共通機能を提供。"""
    
    def __init__(self, chromadb_path: str, provider_type: Optional[str] = None):
        """初期化。
        
        Args:
            chromadb_path: ChromaDB 永続化ディレクトリパス
            provider_type: AIプロバイダタイプ ("ollama" or "openai")
        """
        self.chromadb_path = chromadb_path
        
        # AI プロバイダを初期化
        if provider_type is None:
            provider_type = config.ai_provider
        
        try:
            self.ai_provider = create_ai_provider(provider_type, config)
            logger.info(f"Initialized AI provider: {provider_type}")
        except Exception as e:
            logger.error(f"Failed to initialize AI provider {provider_type}: {e}")
            raise RuntimeError(f"Failed to initialize AI provider: {e}")
        
        # 埋め込み次元をプローブ
        try:
            probe_vec = self.ai_provider.embed_query("__dimension_probe__")
            if probe_vec and hasattr(self.ai_provider, 'default_dimension'):
                logger.info(f"Probed embedding dimension: {len(probe_vec)}")
        except Exception:
            logger.debug("Embedding dimension probe failed; fallback to provider default.")

        # ChromaDB クライアント初期化
        self.chroma_client = chromadb.PersistentClient(
            path=chromadb_path,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # コレクション取得（無ければ作成）
        self._setup_collection()
        
        # 長文分割
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        
        # プロンプトテンプレート格納ディレクトリ
        self.prompts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'prompts')
        
        # 差分インデックス状態ファイル
        data_dir = os.path.dirname(chromadb_path)
        self.index_state_path = os.path.join(data_dir, 'rag_index_state.json')
    
    def _setup_collection(self):
        """コレクションのセットアップ。"""
        expected_dim = getattr(self.ai_provider, 'default_dimension', None)
        embedding_model = getattr(self.ai_provider, 'embedding_model', 'unknown')
        
        self.collection = self.chroma_client.get_or_create_collection(
            name="redmine_issues",
            metadata={
                "hnsw:space": "cosine",
                "embedding_model": embedding_model,
                "embedding_dimension": expected_dim
            }
        )
        
        # 埋め込み次元の互換性チェック
        try:
            col_meta = self.collection.metadata or {}
            stored_dim = col_meta.get('embedding_dimension')
            if stored_dim and expected_dim and stored_dim != expected_dim:
                logger.warning(
                    f"Embedding dimension mismatch detected (stored={stored_dim}, current={expected_dim}). Rebuilding empty collection now."
                )
                try:
                    self.chroma_client.delete_collection("redmine_issues")
                except Exception:
                    pass
                self.collection = self.chroma_client.get_or_create_collection(
                    name="redmine_issues",
                    metadata={
                        "hnsw:space": "cosine",
                        "embedding_model": embedding_model,
                        "embedding_dimension": expected_dim
                    }
                )
        except Exception:
            pass
    
    def _load_prompt_template(self, filename: str) -> Optional[str]:
        """プロンプトテンプレートを読み込み。"""
        path = os.path.join(self.prompts_dir, filename)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to load prompt template {filename}: {e}")
            return None
