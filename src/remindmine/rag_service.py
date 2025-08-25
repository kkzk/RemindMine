"""Redmine 課題の類似検索およびアドバイス生成を行う RAG (Retrieval Augmented Generation) サービス。

注意: このモジュールは後方互換性のために残されています。
新しいコードでは rag.RAGIndexer と rag.RAGSearcher を直接使用することを推奨します。

主な役割:
1. Redmine 課題データを ChromaDB にベクトル化格納 (Issue -> 複数チャンク)
2. 新規/対象課題の説明文から類似課題チャンクを検索
3. 類似課題の文脈を元に LLM へプロンプトを組み立てアドバイスを生成

設計メモ:
- AI Provider: プロバイダパターンで Ollama/OpenAI を切り替え可能
- Vector Store: ChromaDB (PersistentClient) を利用し cosine 類似度 (hnsw:space=cosine)
- 分割: LangChain RecursiveCharacterTextSplitter で長文をチャンク (1000 文字 / 200 文字オーバーラップ)
- 冪等性: index_issues 呼び出し時はコレクションを一度削除⇒再生成で全件再構築
- 取得戦略: 除外 issue を考慮するために必要件数 * 3 を一旦取得してフィルタリング
"""

import warnings
from typing import Optional

# 新しいモジュール構造をインポート
from .rag import RAGService as NewRAGService

# 後方互換性のため、RAGService を既存の場所でも利用可能に
class RAGService(NewRAGService):
    """後方互換性のためのRAGServiceクラス。
    
    注意: このクラスは非推奨です。
    新しいコードでは rag.RAGIndexer と rag.RAGSearcher を直接使用してください。
    """
    
    def __init__(self, chromadb_path: str, provider_type: Optional[str] = None):
        warnings.warn(
            "RAGService は非推奨です。rag.RAGIndexer と rag.RAGSearcher を使用してください。",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(chromadb_path, provider_type)
