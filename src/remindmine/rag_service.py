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
import hashlib
import json
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
        
        # 可能なら事前に埋め込み次元をプローブ（Ollama など動的次元検出用）
        try:
            probe_vec = self.ai_provider.embed_query("__dimension_probe__")
            if probe_vec and hasattr(self.ai_provider, 'default_dimension'):
                # embed_query 内で provider 側の default_dimension が更新される設計
                logger.info(f"Probed embedding dimension: {len(probe_vec)}")
        except Exception:
            logger.debug("Embedding dimension probe failed; fallback to provider default.")

        # ChromaDB クライアント初期化 (永続モード)
        self.chroma_client = chromadb.PersistentClient(
            path=chromadb_path,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # コレクション取得 (無ければ作成)。距離空間 + 埋め込みモデル情報をメタデータへ保持
        # 既存コレクションの埋め込み次元と現在プロバイダの次元が異なる場合は再構築が必要。
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
        except Exception:  # メタデータ未対応バージョン等は無視
            pass
        
        # 長文分割: 再利用コストを避けるためインスタンス保持
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        # プロンプトテンプレート格納ディレクトリ (インデックス再構築関連の前処理)
        self.prompts_dir = os.path.join(os.path.dirname(__file__), 'prompts')
        # 差分インデックス状態ファイル (issue_id -> hash 等)
        data_dir = os.path.dirname(chromadb_path)
        self.index_state_path = os.path.join(data_dir, 'rag_index_state.json')

    def _load_prompt_template(self, filename: str) -> Optional[str]:
        """プロンプトテンプレート (プレーンテキスト) を読み込み。存在しない/失敗時は None。"""
        path = os.path.join(self.prompts_dir, filename)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to load prompt template {filename}: {e}")
            return None
    
    def _load_index_state(self) -> Dict[str, Any]:
        """前回インデックス状態 (JSON) を読み込み。存在しなければ初期状態。"""
        try:
            with open(self.index_state_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {"issues": {}, "embedding_model": getattr(self.ai_provider, 'embedding_model', 'unknown'), "embedding_dimension": getattr(self.ai_provider, 'default_dimension', None), "version": 1}

    def _save_index_state(self, state: Dict[str, Any]) -> None:
        try:
            with open(self.index_state_path, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save index state: {e}")

    def _hash_issue(self, issue: Dict[str, Any]) -> str:
        """issue 全体の内容ハッシュ (件名+説明+コメント) を生成。"""
        content = self._create_issue_content(issue)
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def index_issues(self, issues: List[Dict[str, Any]], full_rebuild: bool = False) -> int:
        """課題一覧を差分インデックス。戻り値は『今回新規/更新で追加したチャンク数』。

        改善点:
          - 変更のない issue は再埋め込みしない
          - 削除された issue のチャンクを除去
          - 埋め込みモデルが変わった場合は自動で full rebuild

        Args:
            issues: Redmine から取得した最新全課題
            full_rebuild: 強制で全再構築したい場合 True
        """
        if not issues:
            logger.warning("No issues provided for indexing")
            return 0

        current_embedding_model = getattr(self.ai_provider, 'embedding_model', 'unknown')
        expected_dim = getattr(self.ai_provider, 'default_dimension', None)
        state = self._load_index_state()
        prev_model = state.get('embedding_model')
        prev_dim = state.get('embedding_dimension')
        if prev_model != current_embedding_model:
            logger.info(f"Embedding model changed: {prev_model} -> {current_embedding_model}; forcing full rebuild")
            full_rebuild = True
        elif prev_dim and expected_dim and prev_dim != expected_dim:
            logger.info(f"Embedding dimension changed: {prev_dim} -> {expected_dim}; forcing full rebuild")
            full_rebuild = True

        if full_rebuild:
            logger.info(f"Rebuilding index for {len(issues)} issues (full rebuild)...")
            try:
                self.chroma_client.delete_collection("redmine_issues")
            except Exception as e:
                logger.debug(f"Collection deletion failed (may not exist): {e}")
            self.collection = self.chroma_client.get_or_create_collection(
                name="redmine_issues",
                metadata={
                    "hnsw:space": "cosine",
                    "embedding_model": current_embedding_model,
                    "embedding_dimension": expected_dim
                }
            )
            # 全件を変更扱いとして進めるため状態を空に
            state['issues'] = {}

        issue_state: Dict[str, Any] = state.get('issues', {})
        latest_issue_ids = {str(i['id']) for i in issues}
        existing_issue_ids = set(issue_state.keys())

        # 削除された issue をコレクションから削除
        removed_issue_ids = existing_issue_ids - latest_issue_ids
        removed_count = 0
        for rid in removed_issue_ids:
            try:
                self.collection.delete(where={"issue_id": int(rid)})
                removed_count += 1
                issue_state.pop(rid, None)
            except Exception as e:
                logger.error(f"Failed to delete removed issue {rid}: {e}")

        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        ids: List[str] = []
        added_chunk_total = 0
        new_issues = 0
        updated_issues = 0
        skipped_issues = 0

        embedding_model_at_index = current_embedding_model

        for issue in issues:
            issue_id_str = str(issue['id'])
            issue_hash = self._hash_issue(issue)
            prev = issue_state.get(issue_id_str)
            if prev and prev.get('hash') == issue_hash and not full_rebuild:
                skipped_issues += 1
                continue

            # 既存チャンク削除 (更新/新規問わず安全に再投入)
            if prev:
                try:
                    self.collection.delete(where={"issue_id": issue['id']})
                except Exception as e:
                    logger.debug(f"Delete existing chunks for issue {issue['id']} failed: {e}")

            content = self._create_issue_content(issue)
            chunks = self.text_splitter.split_text(content)
            issue_updated_on = issue.get('updated_on') or issue.get('updated_at') or ''

            for i, chunk in enumerate(chunks):
                doc_id = f"issue_{issue['id']}_chunk_{i}"
                chunk_hash = hashlib.sha256(chunk.encode('utf-8')).hexdigest()[:16]
                documents.append(chunk)
                metadatas.append({
                    "issue_id": issue['id'],
                    "subject": issue.get('subject', ''),
                    "status": issue.get('status', {}).get('name', ''),
                    "priority": issue.get('priority', {}).get('name', ''),
                    "tracker": issue.get('tracker', {}).get('name', ''),
                    "chunk_index": i,
                    "source_type": "issue",
                    "source_id": issue['id'],
                    "source_updated_on": issue_updated_on,
                    "chunk_hash": chunk_hash,
                    "chunk_char_length": len(chunk),
                    "embedding_model_at_index": embedding_model_at_index,
                })
                ids.append(doc_id)
            added_chunk_total += len(chunks)

            if prev:
                updated_issues += 1
            else:
                new_issues += 1

            issue_state[issue_id_str] = {
                "hash": issue_hash,
                "chunk_count": len(chunks),
                "updated_on": issue_updated_on,
            }

        # 埋め込み (新規/更新分のみ)
        if documents:
            try:
                embeddings = self.ai_provider.embed_documents(documents)
                if len(embeddings) != len(documents):
                    logger.error("Embedding count mismatch; aborting incremental index batch")
                    return 0
                normalized_embeddings = [list(vec) for vec in embeddings]
                self.collection.add(
                    documents=documents,
                    metadatas=metadatas,  # type: ignore[arg-type]
                    ids=ids,
                    embeddings=normalized_embeddings  # type: ignore[arg-type]
                )
            except Exception as e:
                logger.error(f"Failed to embed incremental documents: {e}")
                return 0

        # 状態保存
        state['issues'] = issue_state
        state['embedding_model'] = current_embedding_model
        state['embedding_dimension'] = expected_dim
        self._save_index_state(state)

        logger.info(
            f"Index update done: new={new_issues}, updated={updated_issues}, skipped={skipped_issues}, removed={removed_count}, chunks_added={added_chunk_total}"
        )
        return added_chunk_total
    
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

            # コレクションに保持されている埋め込み次元とクエリ埋め込み次元を検証
            try:
                col_meta = self.collection.metadata or {}
                stored_dim = col_meta.get('embedding_dimension')
                if stored_dim and len(query_embedding) != stored_dim:
                    logger.error(
                        f"Embedding dimension mismatch (stored={stored_dim}, query={len(query_embedding)}). "
                        "Re-run index_issues() after switching embedding model."
                    )
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
