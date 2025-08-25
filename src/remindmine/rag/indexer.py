"""RAGインデックス構築モジュール。

Redmine課題データのChromaDBへのインデックス作成を担当。
差分更新、ハッシュベースの変更検出、状態管理を提供。

【ChromaDB初学者向け】
ChromaDBは「ベクトルデータベース」の一種で、以下の特徴があります：
1. ドキュメント（テキスト）を数値ベクトル（埋め込み）に変換して保存
2. 類似度検索により、意味的に近いドキュメントを高速に検索可能
3. コレクション（データベースのテーブルのような概念）でデータを管理
4. 各ドキュメントにはID、テキスト、メタデータ、埋め込みベクトルが含まれる

このモジュールは、Redmine課題をChromaDBに格納して検索可能にします。
"""

import logging
from typing import List, Dict, Any
import hashlib
import json

from .shared import RAGBase

logger = logging.getLogger(__name__)


class RAGIndexer(RAGBase):
    """RAGインデックス構築クラス。
    
    【ChromaDB初学者向け】
    このクラスの主な役割：
    1. Redmine課題データをChromaDBに格納（インデックス作成）
    2. データの変更を検出して必要な部分のみ更新（差分更新）
    3. インデックスの状態管理（どのデータが既に格納済みかを記録）
    4. テキストのチャンク分割（長いテキストを検索しやすいサイズに分割）
    """
    
    def _load_index_state(self) -> Dict[str, Any]:
        """前回インデックス状態を読み込み。
        
        【ChromaDB初学者向け】
        ChromaDBは埋め込みベクトルを保存しますが、「どのデータがいつ更新されたか」の
        管理機能は限定的です。そのため、このアプリでは独自にJSONファイルで状態管理を行います：
        - issues: 各課題のハッシュ値と更新日時を記録
        - embedding_model: 使用した埋め込みモデル名
        - embedding_dimension: ベクトルの次元数
        
        これにより、データが変更された課題のみを再インデックスできます（差分更新）。
        """
        try:
            with open(self.index_state_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {
                "issues": {},
                "embedding_model": getattr(self.ai_provider, 'embedding_model', 'unknown'),
                "embedding_dimension": getattr(self.ai_provider, 'default_dimension', None),
                "version": 1
            }

    def _save_index_state(self, state: Dict[str, Any]) -> None:
        """インデックス状態を保存。"""
        try:
            with open(self.index_state_path, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save index state: {e}")

    def _hash_issue(self, issue: Dict[str, Any]) -> str:
        """issue 全体の内容ハッシュを生成。
        
        【ChromaDB初学者向け】
        ハッシュ値は「データの指紋」のようなものです。
        - 課題の内容が少しでも変更されると、ハッシュ値も変わります
        - 前回保存したハッシュ値と比較することで、データが変更されたかを高速判定
        - これにより、変更のない課題は再インデックスをスキップできます
        
        SHA256アルゴリズムを使用して、課題の全内容から一意の文字列を生成します。
        """
        content = self._create_issue_content(issue)
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def _create_issue_content(self, issue: Dict[str, Any]) -> str:
        """課題辞書から検索対象テキストを生成。
        
        【ChromaDB初学者向け】
        ChromaDBに格納するテキストを作成します。Redmine課題の様々な情報を
        検索しやすい形式に統合：
        - 件名、説明、ステータス、優先度、トラッカー、コメントを結合
        - 「件名: ○○」のように項目名を付けて構造化
        - このテキストが埋め込みベクトルに変換され、ChromaDBに保存されます
        
        例: 「件名: バグ修正\n説明: ログイン時にエラー\nステータス: 進行中」
        """
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

    def index_issues(self, issues: List[Dict[str, Any]], full_rebuild: bool = False) -> int:
        """課題一覧を差分インデックス。戻り値は追加したチャンク数。
        
        【ChromaDB初学者向け】
        このメソッドがインデックス作成の中心です。以下の流れで動作：
        
        1. 【埋め込みモデル変更チェック】
           - 異なるモデルで作られたベクトルは互換性がないため
           - モデル変更時は既存データを全削除して再構築
        
        2. 【差分検出】
           - 各課題のハッシュ値を前回と比較
           - 変更のない課題はスキップ（効率化）
        
        3. 【チャンク分割】
           - 長いテキストを適切なサイズに分割
           - 各チャンクが独立したドキュメントとしてChromaDBに格納
           - 検索精度向上のため
        
        4. 【埋め込み生成とChromaDB格納】
           - AIプロバイダー（OpenAI等）でテキストをベクトル化
           - collection.add()でChromaDBに一括保存
           - ドキュメント、メタデータ、ID、埋め込みベクトルをセットで保存
        """
        if not issues:
            return 0

        current_embedding_model = getattr(self.ai_provider, 'embedding_model', 'unknown')
        expected_dim = getattr(self.ai_provider, 'default_dimension', None)
        state = self._load_index_state()
        prev_model = state.get('embedding_model')
        prev_dim = state.get('embedding_dimension')
        
        # モデル/次元変更時は full rebuild
        if (prev_model != current_embedding_model or 
            (prev_dim and expected_dim and prev_dim != expected_dim)):
            full_rebuild = True

        if full_rebuild:
            try:
                # 【ChromaDB初学者向け】
                # コレクション削除：既存のデータベーステーブルを完全削除
                # 埋め込みモデル変更時などに実行
                self.chroma_client.delete_collection("redmine_issues")
            except Exception:
                pass
            self._setup_collection()
            state['issues'] = {}

        issue_state: Dict[str, Any] = state.get('issues', {})
        latest_issue_ids = {str(i['id']) for i in issues}
        existing_issue_ids = set(issue_state.keys())

        # 削除された issue のクリーンアップ
        removed_issue_ids = existing_issue_ids - latest_issue_ids
        for rid in removed_issue_ids:
            try:
                # 【ChromaDB初学者向け】
                # collection.delete()：特定条件のドキュメントを削除
                # where句でメタデータ条件を指定（SQLのWHERE句に似ている）
                self.collection.delete(where={"issue_id": int(rid)})
                issue_state.pop(rid, None)
            except Exception:
                pass

        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        ids: List[str] = []
        added_chunk_total = 0

        for issue in issues:
            issue_id_str = str(issue['id'])
            issue_hash = self._hash_issue(issue)
            prev = issue_state.get(issue_id_str)
            
            if prev and prev.get('hash') == issue_hash and not full_rebuild:
                continue

            # 既存チャンク削除
            if prev:
                try:
                    self.collection.delete(where={"issue_id": issue['id']})
                except Exception:
                    pass

            content = self._create_issue_content(issue)
            chunks = self.text_splitter.split_text(content)
            issue_updated_on = issue.get('updated_on') or issue.get('updated_at') or ''

            for i, chunk in enumerate(chunks):
                # 【ChromaDB初学者向け】
                # 各チャンクに一意のIDを生成：「issue_123_chunk_0」の形式
                # ChromaDBではIDでドキュメントを特定するため重要
                doc_id = f"issue_{issue['id']}_chunk_{i}"
                documents.append(chunk)
                
                # 【メタデータ説明】
                # ChromaDBのメタデータ：検索フィルタリングや結果表示に使用
                # - issue_id: 元の課題ID（数値）
                # - subject, status等: 検索結果表示用
                # - chunk_index: チャンクの順序
                # - source_*: データの出典情報
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
                })
                ids.append(doc_id)
            added_chunk_total += len(chunks)

            issue_state[issue_id_str] = {
                "hash": issue_hash,
                "chunk_count": len(chunks),
                "updated_on": issue_updated_on,
            }

        # 埋め込み処理
        if documents:
            try:
                # 【ChromaDB初学者向け】
                # 埋め込み生成：テキストを数値ベクトルに変換
                # AIプロバイダー（OpenAI等）のAPIを呼び出し
                # 例：「バグ修正」→ [0.1, -0.3, 0.7, ...] (数百～数千次元)
                embeddings = self.ai_provider.embed_documents(documents)
                if len(embeddings) != len(documents):
                    return 0
                
                # 【ChromaDBへの一括保存】
                # collection.add()：新しいドキュメントを追加
                # - documents: 元のテキスト
                # - metadatas: 検索フィルタ用の構造化データ  
                # - ids: 各ドキュメントの一意識別子
                # - embeddings: テキストから生成したベクトル
                self.collection.add(
                    documents=documents,
                    metadatas=metadatas,  # type: ignore[arg-type]
                    ids=ids,
                    embeddings=[list(vec) for vec in embeddings]  # type: ignore[arg-type]
                )
            except Exception as e:
                logger.error(f"Failed to embed documents: {e}")
                return 0

        # 状態保存
        state['issues'] = issue_state
        state['embedding_model'] = current_embedding_model
        state['embedding_dimension'] = expected_dim
        self._save_index_state(state)

        return added_chunk_total

    def get_index_stats(self) -> Dict[str, Any]:
        """インデックスの統計情報を取得。
        
        【ChromaDB初学者向け】
        ChromaDBコレクションの現在の状態を確認するメソッド：
        - total_chunks: 保存されているドキュメント（チャンク）の総数
        - total_issues: インデックス済みの課題数
        - embedding_model: 使用している埋め込みモデル名
        - embedding_dimension: ベクトルの次元数
        
        collection.count()でChromaDBに直接問い合わせて正確な数を取得します。
        """
        try:
            # 【ChromaDB初学者向け】
            # collection.count()：コレクション内のドキュメント総数を取得
            # データベースのCOUNT(*)に相当する操作
            count_result = self.collection.count()
            state = self._load_index_state()
            return {
                "total_chunks": count_result,
                "total_issues": len(state.get('issues', {})),
                "embedding_model": state.get('embedding_model'),
                "embedding_dimension": state.get('embedding_dimension'),
            }
        except Exception as e:
            logger.error(f"Failed to get index stats: {e}")
            return {}
