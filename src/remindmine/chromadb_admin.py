"""ChromaDB管理サービス。

ChromaDBの内容を確認・管理するための機能を提供します。
"""

import logging
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from .config import config

logger = logging.getLogger(__name__)


class ChromaDBAdminService:
    """ChromaDBの管理機能を提供するサービスクラス。"""
    
    def __init__(self, chromadb_path: str):
        """初期化。
        
        Args:
            chromadb_path: ChromaDB永続化ディレクトリパス
        """
        self.chromadb_path = chromadb_path
        self.chroma_client = chromadb.PersistentClient(
            path=chromadb_path,
            settings=Settings(anonymized_telemetry=False)
        )
    
    def get_collections(self) -> List[Dict[str, Any]]:
        """すべてのコレクション情報を取得。
        
        Returns:
            コレクション情報のリスト
        """
        try:
            collections = self.chroma_client.list_collections()
            result = []
            
            for collection in collections:
                # コレクションの詳細情報を取得
                col_info = {
                    "name": collection.name,
                    "id": collection.id,
                    "metadata": collection.metadata or {},
                    "count": collection.count()
                }
                result.append(col_info)
            
            return result
        except Exception as e:
            logger.error(f"Failed to get collections: {e}")
            raise
    
    def get_collection_documents(self, collection_name: str, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """指定されたコレクション内のドキュメントを取得。
        
        Args:
            collection_name: コレクション名
            limit: 取得件数制限
            offset: オフセット
            
        Returns:
            ドキュメント情報
        """
        try:
            collection = self.chroma_client.get_collection(collection_name)
            
            # すべてのドキュメントを取得（ページング対応）
            results = collection.get(
                limit=limit,
                offset=offset,
                include=["documents", "metadatas", "embeddings"]
            )
            
            # 結果を整形
            documents = []
            for i in range(len(results["ids"])):
                # NumPy配列の安全なチェック
                embedding_dim = 0
                if results["embeddings"] is not None and i < len(results["embeddings"]):
                    embedding = results["embeddings"][i]
                    if embedding is not None:
                        try:
                            embedding_dim = len(embedding)
                        except (TypeError, AttributeError):
                            embedding_dim = 0
                
                doc = {
                    "id": results["ids"][i],
                    "document": results["documents"][i] if results["documents"] else None,
                    "metadata": results["metadatas"][i] if results["metadatas"] else {},
                    "embedding_dimension": embedding_dim
                }
                documents.append(doc)
            
            return {
                "collection_name": collection_name,
                "total_count": collection.count(),
                "documents": documents,
                "limit": limit,
                "offset": offset
            }
        except Exception as e:
            logger.error(f"Failed to get collection documents: {e}")
            raise
    
    def get_document_detail(self, collection_name: str, document_id: str) -> Optional[Dict[str, Any]]:
        """指定されたドキュメントの詳細情報を取得。
        
        Args:
            collection_name: コレクション名
            document_id: ドキュメントID
            
        Returns:
            ドキュメント詳細情報（見つからない場合はNone）
        """
        try:
            collection = self.chroma_client.get_collection(collection_name)
            
            results = collection.get(
                ids=[document_id],
                include=["documents", "metadatas", "embeddings"]
            )
            
            if not results["ids"]:
                return None
            
            # NumPy配列の安全なチェックとシリアライズ可能な形式への変換
            embedding = []
            embedding_dimension = 0
            if results["embeddings"] is not None and len(results["embeddings"]) > 0:
                if results["embeddings"][0] is not None:
                    try:
                        raw_embedding = results["embeddings"][0]
                        # NumPy配列をPythonリストに変換
                        if hasattr(raw_embedding, 'tolist'):
                            embedding = raw_embedding.tolist()
                        elif isinstance(raw_embedding, (list, tuple)):
                            embedding = list(raw_embedding)
                        else:
                            embedding = []
                        embedding_dimension = len(embedding)
                    except (TypeError, AttributeError):
                        embedding = []
                        embedding_dimension = 0

            return {
                "id": results["ids"][0],
                "document": results["documents"][0] if results["documents"] else None,
                "metadata": results["metadatas"][0] if results["metadatas"] else {},
                "embedding": embedding,
                "embedding_dimension": embedding_dimension
            }
        except Exception as e:
            logger.error(f"Failed to get document detail: {e}")
            raise
    
    def search_documents(self, collection_name: str, query: str, n_results: int = 10) -> Dict[str, Any]:
        """指定されたコレクション内でドキュメントを検索。
        
        Args:
            collection_name: コレクション名
            query: 検索クエリ
            n_results: 返す結果数
            
        Returns:
            検索結果
        """
        try:
            from .rag_service import RAGService
            
            # RAGServiceを使って埋め込みを生成
            rag_service = RAGService(self.chromadb_path)
            query_embedding = rag_service.ai_provider.embed_query(query)
            
            collection = self.chroma_client.get_collection(collection_name)
            
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                include=["documents", "metadatas", "distances"]
            )
            
            # 結果を整形
            documents = []
            for i in range(len(results["ids"][0])):
                doc = {
                    "id": results["ids"][0][i],
                    "document": results["documents"][0][i] if results["documents"] else None,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else None,
                    "similarity": 1 - results["distances"][0][i] if results["distances"] else None
                }
                documents.append(doc)
            
            return {
                "collection_name": collection_name,
                "query": query,
                "documents": documents,
                "n_results": n_results
            }
        except Exception as e:
            logger.error(f"Failed to search documents: {e}")
            raise
    
    def get_collection_stats(self, collection_name: str) -> Dict[str, Any]:
        """コレクションの統計情報を取得。
        
        Args:
            collection_name: コレクション名
            
        Returns:
            統計情報
        """
        try:
            collection = self.chroma_client.get_collection(collection_name)
            
            # ドキュメント数
            total_count = collection.count()
            
            # メタデータの統計
            if total_count > 0:
                # 最初の100件のメタデータを取得してサンプル統計を作成
                sample_results = collection.get(
                    limit=min(100, total_count),
                    include=["metadatas", "embeddings"]
                )
                
                # メタデータのキー統計
                metadata_keys = set()
                for metadata in (sample_results["metadatas"] or []):
                    if metadata:
                        metadata_keys.update(metadata.keys())
                
                # 埋め込み次元
                embedding_dimension = 0
                if sample_results["embeddings"] is not None and len(sample_results["embeddings"]) > 0:
                    first_embedding = sample_results["embeddings"][0]
                    if first_embedding is not None:
                        try:
                            embedding_dimension = len(first_embedding)
                        except (TypeError, AttributeError):
                            embedding_dimension = 0
                
                return {
                    "collection_name": collection_name,
                    "total_documents": total_count,
                    "metadata_keys": list(metadata_keys),
                    "embedding_dimension": embedding_dimension,
                    "collection_metadata": collection.metadata or {}
                }
            else:
                return {
                    "collection_name": collection_name,
                    "total_documents": 0,
                    "metadata_keys": [],
                    "embedding_dimension": 0,
                    "collection_metadata": collection.metadata or {}
                }
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            raise
    
    def delete_document(self, collection_name: str, document_id: str) -> bool:
        """指定されたドキュメントを削除。
        
        Args:
            collection_name: コレクション名
            document_id: ドキュメントID
            
        Returns:
            削除成功の場合True
        """
        try:
            collection = self.chroma_client.get_collection(collection_name)
            collection.delete(ids=[document_id])
            return True
        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
            raise
    
    def delete_collection(self, collection_name: str) -> bool:
        """指定されたコレクションを削除。
        
        Args:
            collection_name: コレクション名
            
        Returns:
            削除成功の場合True
        """
        try:
            self.chroma_client.delete_collection(collection_name)
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")
            raise
