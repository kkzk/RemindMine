"""定期的なRAGデータベース更新と新規チケット監視のためのスケジューラ"""

import logging
import threading
import time
import os
import json
from typing import TYPE_CHECKING, Optional
from datetime import datetime, timezone

if TYPE_CHECKING:
    from .redmine_client import RedmineClient
    from .rag_service import RAGService

# Import config after TYPE_CHECKING to avoid circular imports
from .config import config

logger = logging.getLogger(__name__)


class UpdateScheduler:
    """定期的なRAG更新と新規チケット監視のためのスケジューラ"""
    
    def __init__(self, redmine_client: "RedmineClient", rag_service: "RAGService", 
                 interval_minutes: int, polling_interval_minutes: int = 5):
        """
        スケジューラの初期化
        
        引数:
            redmine_client: Redmineクライアントインスタンス
            rag_service: RAGサービスインスタンス
            interval_minutes: RAG更新の間隔（分）
            polling_interval_minutes: 新規チケット監視の間隔（分）
        """
        self.redmine_client = redmine_client
        self.rag_service = rag_service
        self.interval_minutes = interval_minutes
        self.interval_seconds = interval_minutes * 60
        self.polling_interval_minutes = polling_interval_minutes
        self.polling_interval_seconds = polling_interval_minutes * 60
        
        self._stop_event = threading.Event()
        self._rag_thread = None
        self._polling_thread = None
        self._last_check_time: Optional[datetime] = None
        self._state_file = "data/scheduler_state.json"
    
    def start(self):
        """
        スケジューラを開始する
        """
        if (self._rag_thread is not None and self._rag_thread.is_alive()) or \
           (self._polling_thread is not None and self._polling_thread.is_alive()):
            logger.warning("Scheduler is already running")
            return
        
        logger.info(f"Starting scheduler with {self.interval_minutes} minute RAG intervals and {self.polling_interval_minutes} minute polling intervals")
        self._stop_event.clear()
        
        # 最終チェック時刻をロードまたは初期化
        self._load_last_check_time()
        
        # RAG更新用スレッド開始
        self._rag_thread = threading.Thread(target=self._run_rag_updates, daemon=True)
        self._rag_thread.start()
        
        # 新規チケット監視用スレッド開始
        self._polling_thread = threading.Thread(target=self._run_issue_polling, daemon=True)
        self._polling_thread.start()
    
    def stop(self):
        """
        スケジューラを停止する
        """
        if self._rag_thread is None and self._polling_thread is None:
            return
        
        logger.info("Stopping scheduler...")
        self._stop_event.set()
        
        if self._rag_thread:
            self._rag_thread.join(timeout=10)
            if self._rag_thread.is_alive():
                logger.warning("RAG update thread did not stop gracefully")
        
        if self._polling_thread:
            self._polling_thread.join(timeout=10)
            if self._polling_thread.is_alive():
                logger.warning("Issue polling thread did not stop gracefully")
        
        if (self._rag_thread is None or not self._rag_thread.is_alive()) and \
           (self._polling_thread is None or not self._polling_thread.is_alive()):
            logger.info("Scheduler stopped successfully")
            # 最終状態を保存
            self._save_last_check_time()
    
    def _run_rag_updates(self):
        """
        RAG更新のメインループ
        """
        # 初回更新
        self._update_rag()
        
        while not self._stop_event.is_set():
            # 指定間隔または停止イベントまで待機
            if self._stop_event.wait(timeout=self.interval_seconds):
                break
            
            # RAG更新を実行
            self._update_rag()
    
    def _run_issue_polling(self):
        """
        新規チケット監視のメインループ
        """
        while not self._stop_event.is_set():
            # 監視間隔または停止イベントまで待機
            if self._stop_event.wait(timeout=self.polling_interval_seconds):
                break
            
            # 新規チケットの有無を確認
            self._check_new_issues()

    def _load_last_check_time(self):
        """
        最終チェック時刻を永続ストレージから読み込む
        """
        try:
            if os.path.exists(self._state_file):
                with open(self._state_file, 'r') as f:
                    state = json.load(f)
                    last_check_str = state.get('last_check_time')
                    if last_check_str:
                        self._last_check_time = datetime.fromisoformat(last_check_str)
                        logger.info(f"Loaded last check time: {self._last_check_time}")
                        return
            
            # 保存状態がなければ現在時刻で初期化
            self._last_check_time = datetime.now(timezone.utc)
            logger.info(f"最終チェック時刻を初期化: {self._last_check_time}")
            
        except Exception as e:
            logger.error(f"最終チェック時刻の読み込みに失敗: {e}")
            self._last_check_time = datetime.now(timezone.utc)

    def _save_last_check_time(self):
        """
        最終チェック時刻を永続ストレージに保存する
        """
        try:
            # dataディレクトリが存在しなければ作成
            os.makedirs(os.path.dirname(self._state_file), exist_ok=True)
            
            state = {
                'last_check_time': self._last_check_time.isoformat() if self._last_check_time else None
            }
            
            with open(self._state_file, 'w') as f:
                json.dump(state, f)
                
        except Exception as e:
            logger.error(f"最終チェック時刻の保存に失敗: {e}")
    
    def _update_rag(self):
        """
        RAGデータベースを最新のチケットで更新する
        """
        try:
            logger.info("定期RAG更新を開始...")
            
            # ジャーナル付き全チケットを取得
            issues = self.redmine_client.get_all_issues_with_journals()
            
            # チケットをRAGにインデックス
            self.rag_service.index_issues(issues)
            
            logger.info("定期RAG更新が正常に完了")
            
        except Exception as e:
            logger.error(f"定期RAG更新に失敗: {e}")
    
    def _check_new_issues(self):
        """
        新規チケットを確認し、必要な処理を行う
        """
        try:
            if self._last_check_time is None:
                # 未設定の場合は現在時刻で初期化
                self._last_check_time = datetime.now(timezone.utc)
                self._save_last_check_time()
                return
            
            # 最終チェック以降の新規チケットを取得
            new_issues = self.redmine_client.get_issues_since(self._last_check_time)
            
            if new_issues:
                logger.info(f"{self._last_check_time.astimezone().isoformat()} 以降の新規チケットを {len(new_issues)} 件発見")
                
                # 各新規チケットを処理
                for issue in new_issues:
                    self._process_new_issue(issue)
                
                # 最新チケットの作成日時で最終チェック時刻を更新
                latest_time = max(
                    datetime.fromisoformat(issue['created_on'].replace('Z', '+00:00'))
                    for issue in new_issues
                )
                self._last_check_time = latest_time
                self._save_last_check_time()
            else:
                # 新規がなければ現在時刻で更新
                self._last_check_time = datetime.now(timezone.utc)
                self._save_last_check_time()
                
        except Exception as e:
            logger.error(f"新規チケット確認に失敗: {e}")
    
    def _process_new_issue(self, issue: dict):
        """
        新規作成されたチケットを処理する
        
        引数:
            issue: Redmine APIからのチケット辞書
        """
        try:
            issue_id = issue['id']
            issue_subject = issue.get('subject', 'No subject')
            
            logger.info(f"新規チケット #{issue_id}: {issue_subject} を処理中")
            
            # 自動アドバイス機能が有効か確認
            from .web_config import web_config
            if not web_config.auto_advice_enabled:
                logger.info(f"自動アドバイスは無効のため、チケット #{issue_id} をスキップ")
                return
            
            # 既にAIアドバイスが存在するか確認
            if self.redmine_client.has_ai_comment(issue_id, config.ai_comment_signature):
                logger.info(f"チケット #{issue_id} には既にAIアドバイスが存在するためスキップ")
                return
            
            # 新規チケットに対してAIアドバイスを生成
            advice = self.rag_service.generate_advice_for_issue(issue)
            
            if advice:
                # すぐに投稿せず、保留リストに追加
                from .pending_advice import pending_advice_manager
                advice_id = pending_advice_manager.add_pending_advice(issue, advice)
                logger.info(f"チケット #{issue_id} のAIアドバイスを保留リストに追加（ID: {advice_id}）")
            else:
                logger.warning(f"チケット #{issue_id} に対してAIアドバイスが生成されませんでした")
                
        except Exception as e:
            logger.error(f"新規チケット #{issue.get('id', 'unknown')} の処理に失敗: {e}")
