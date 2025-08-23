"""Redmine 課題の類似検索およびアドバイス生成を行う RAG (Retrieval Augmented Generation) サービス。

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


import logging
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
import os
from .config import config
from .ai_providers import create_ai_provider, AIProvider

logger = logging.getLogger(__name__)


# 後方互換性のため OllamaEmbeddings クラスを残す（deprecated）
class OllamaEmbeddings:
    """Ollama Embeddings 取得用の極めてシンプルなラッパークラス。
    
    注意: このクラスは非推奨です。新しい ai_providers モジュールを使用してください。
    """
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2"):
        logger.warning("OllamaEmbeddings is deprecated. Use ai_providers module instead.")
        from .ai_providers import OllamaProvider
        self._provider = OllamaProvider(base_url, model, model)
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """複数テキストを埋め込みベクトルへ変換。"""
        return self._provider.embed_documents(texts)
    
    def embed_query(self, text: str) -> List[float]:
        """検索クエリ 1 件を埋め込みベクトルへ変換。"""
        return self._provider.embed_query(text)
    
    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """内部利用のため、プロバイダ経由で取得。"""
        embedding = self._provider.embed_query(text)
        return embedding if any(embedding) else None


class RAGService:
    """Redmine 課題を対象にした検索 (Retrieval) + 生成 (Generation) サービス本体。"""
    
    def __init__(self, chromadb_path: str, provider_type: Optional[str] = None, 
                 ollama_base_url: Optional[str] = None, ollama_model: Optional[str] = None):
        """初期化。

        Args:
            chromadb_path: ChromaDB 永続化ディレクトリパス
            provider_type: AIプロバイダタイプ ("ollama" or "openai")
            ollama_base_url: Ollama のベース URL (後方互換性のため)
            ollama_model: 利用する Ollama モデル名 (後方互換性のため)
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
            # フォールバックとして Ollama プロバイダを試す
            try:
                self.ai_provider = create_ai_provider("ollama", config)
                logger.warning("Falling back to Ollama provider")
            except Exception as fallback_e:
                logger.error(f"Fallback to Ollama also failed: {fallback_e}")
                raise RuntimeError(f"Failed to initialize any AI provider: {e}")
        
        # 後方互換性のため、古いパラメータも保存
        self.ollama_base_url = ollama_base_url or config.ollama_base_url
        self.ollama_model = ollama_model or config.ollama_model
        
        # ChromaDB クライアント初期化 (永続モード)
        self.chroma_client = chromadb.PersistentClient(
            path=chromadb_path,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # コレクション取得 (無ければ作成)。距離空間は cosine
        self.collection = self.chroma_client.get_or_create_collection(
            name="redmine_issues",
            metadata={"hnsw:space": "cosine"}
        )
        
        # 長文分割: 再利用コストを避けるためインスタンス保持
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        
        # プロンプトテンプレート格納ディレクトリ
        self.prompts_dir = os.path.join(os.path.dirname(__file__), 'prompts')

    def _load_prompt_template(self, filename: str) -> Optional[str]:
        """プロンプトテンプレート (プレーンテキスト) を読み込み。存在しない/失敗時は None。"""
        path = os.path.join(self.prompts_dir, filename)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to load prompt template {filename}: {e}")
            return None
    
    def index_issues(self, issues: List[Dict[str, Any]]) -> None:
        """課題一覧を ChromaDB に再構築インデックス。

        全再構築 (破壊的) ポリシー: 既存コレクションを削除→再作成→全件投入。
        差分更新が必要になった場合はここを変更する。

        Args:
            issues: Redmine API から取得した課題辞書のリスト
        """
        logger.info(f"Indexing {len(issues)} issues...")
        
        # 既存コレクションを削除 (存在しない場合は例外を握り潰す)
        try:
            self.chroma_client.delete_collection("redmine_issues")
        except Exception as e:
            logger.debug(f"Collection deletion failed (may not exist): {e}")
        
        # コレクション再生成
        self.collection = self.chroma_client.get_or_create_collection(
            name="redmine_issues",
            metadata={"hnsw:space": "cosine"}
        )
        
        documents = []
        metadatas = []
        ids = []
        
        for issue in issues:
            # 課題データから全文 (検索対象テキスト) を組み立て
            content = self._create_issue_content(issue)
            
            # 長文はチャンク分割
            chunks = self.text_splitter.split_text(content)
            
            for i, chunk in enumerate(chunks):
                doc_id = f"issue_{issue['id']}_chunk_{i}"
                documents.append(chunk)
                metadatas.append({
                    "issue_id": issue['id'],
                    "subject": issue.get('subject', ''),
                    "status": issue.get('status', {}).get('name', ''),
                    "priority": issue.get('priority', {}).get('name', ''),
                    "tracker": issue.get('tracker', {}).get('name', ''),
                    "chunk_index": i
                })
                ids.append(doc_id)
        
        if documents:
            # コレクション追加（エンベディングは後でクエリ時に行う）
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            
        logger.info(f"Indexed {len(documents)} document chunks")
    
    def search_similar_issues(self, query: str, n_results: int = 5, exclude_issue_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """類似課題チャンクを検索。

        Args:
            query: 検索クエリ (通常は課題説明全文)
            n_results: フィルタ後に返したい件数
            exclude_issue_id: 除外したい既存課題 ID (自身を除外する用途)

        Returns:
            類似課題チャンク (content, metadata, similarity を含む) のリスト
        """
        try:
            # 除外フィルタ後にも所望件数を確保するためオーバーフェッチ
            fetch_n = n_results * 3 if exclude_issue_id is not None else n_results
            
            # AIプロバイダ経由でクエリエンベディング生成
            query_embedding = self.ai_provider.embed_query(query)
            
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
                    # 除外対象 issue のチャンクはスキップ
                    if exclude_issue_id is not None and metadata.get('issue_id') == exclude_issue_id:
                        continue
                    distance = distances_list[0][i] if distances_list and distances_list[0] and i < len(distances_list[0]) else 1.0
                    similar_issues.append({
                        'content': doc,
                        'metadata': metadata,
                        'similarity': 1 - distance  # cosine 距離 -> 類似度へ変換 (暫定)
                    })

            # 希望件数へ丸め
            return similar_issues[:n_results]

        except Exception as e:
            logger.error(f"Failed to search similar issues: {e}")
            return []
    
    def generate_advice(self, issue_description: str, similar_issues: List[Dict[str, Any]]) -> str:
        """類似課題を踏まえてアドバイステキストを生成。"""
        # 類似課題からコンテキスト文字列生成
        context = self._create_context(similar_issues)
        
        # プロンプト生成
        prompt = self._create_advice_prompt(issue_description, context)
        
        # AIプロバイダでアドバイス生成
        try:
            advice = self.ai_provider.generate_completion(prompt)
            
            if advice and advice.strip():
                return advice.strip()
            else:
                return "申し訳ございませんが、アドバイスの生成に失敗しました。"
            
        except Exception as e:
            logger.error(f"Failed to generate advice: {e}")
            return "申し訳ございませんが、AIアドバイスの生成中にエラーが発生しました。"
    
    def generate_advice_for_issue(self, issue: Dict[str, Any]) -> Optional[str]:
        """特定の課題 (辞書形式) に対して AI アドバイスを生成。失敗時は None。"""
        try:
            # 検索用に課題説明全文を構築
            issue_description = self._create_issue_content(issue)
            
            # 類似課題検索 (自身の issue_id を除外)
            similar_issues = self.search_similar_issues(issue_description, n_results=5, exclude_issue_id=issue.get('id'))
            
            # アドバイス生成
            advice = self.generate_advice(issue_description, similar_issues)
            
            if advice and advice.strip() and advice != "申し訳ございませんが、AIアドバイスの生成中にエラーが発生しました。":
                return f"AI自動アドバイス:\n\n{advice}"
            else:
                return None
                
        except Exception as e:
            logger.error(f"Failed to generate advice for issue {issue.get('id', 'unknown')}: {e}")
            return None
    
    def _create_issue_content(self, issue: Dict[str, Any]) -> str:
        """課題辞書から検索対象となる統合テキストを生成。"""
        content_parts = []
        
        # Subject
        if issue.get('subject'):
            content_parts.append(f"件名: {issue['subject']}")
        
        # Description
        if issue.get('description'):
            content_parts.append(f"説明: {issue['description']}")
        
        # Status, Priority, Tracker
        if issue.get('status'):
            content_parts.append(f"ステータス: {issue['status'].get('name', '')}")
        if issue.get('priority'):
            content_parts.append(f"優先度: {issue['priority'].get('name', '')}")
        if issue.get('tracker'):
            content_parts.append(f"トラッカー: {issue['tracker'].get('name', '')}")
        
        # Journals (comments)
        if issue.get('journals'):
            for journal in issue['journals']:
                if journal.get('notes'):
                    content_parts.append(f"コメント: {journal['notes']}")
        
        return "\n".join(content_parts)
    
    def _create_context(self, similar_issues: List[Dict[str, Any]]) -> str:
        """類似課題リストからコンテキスト文字列を生成。件数 0 の場合は既定文。"""
        if not similar_issues:
            return "関連する過去の事例は見つかりませんでした。"
        
        context_parts = []
        context_parts.append("関連する過去の事例:")
        
        for i, issue in enumerate(similar_issues[:3]):  # Top 3 results
            metadata = issue.get('metadata', {})
            content = issue.get('content', '')
            similarity = issue.get('similarity', 0)
            
            context_parts.append(f"\n事例 {i+1} (類似度: {similarity:.2f}):")
            context_parts.append(f"Issue ID: {metadata.get('issue_id')}")
            context_parts.append(f"件名: {metadata.get('subject')}")
            context_parts.append(f"内容: {content[:500]}...")  # Truncate long content
        
        return "\n".join(context_parts)
    
    def _create_advice_prompt(self, issue_description: str, context: str) -> str:
        """アドバイス生成用プロンプトをテンプレート (advice.txt) から組み立て。テンプレート無い場合は簡易版。"""
        template = self._load_prompt_template('advice.txt')
        if not template:
            # Fallback to minimal prompt if template missing
            return f"課題:\n{issue_description}\n\n{context}\n\nアドバイス:"
        return (template
                .replace('{{ISSUE_DESCRIPTION}}', issue_description)
                .replace('{{CONTEXT}}', context)
                .replace('{{REDMINE_URL}}', config.redmine_url))
