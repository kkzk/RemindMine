# RemindMine ポーリング実装への変更

## 変更理由
RedmineでWebhook機能が使用できないため、Webhookベースの実装からポーリングベースの実装に変更しました。

## 主要な変更内容

### 1. `redmine_client.py` の拡張
- `get_issues_since(since_datetime)`: 指定日時以降に作成されたIssueを取得
- `get_latest_issue_creation_time()`: 最新Issueの作成時刻を取得

### 2. `scheduler.py` の大幅改修
- **二重スレッド化**: RAG更新とIssue監視を独立したスレッドで実行
- `_run_rag_updates()`: 既存のRAG更新ロジック（60分間隔）
- `_run_issue_polling()`: 新規Issue検出ロジック（5分間隔）
- `_check_new_issues()`: 新規Issue検出とAIアドバイス自動投稿
- `_process_new_issue()`: 個別Issue処理（類似検索→AIアドバイス生成→コメント投稿）

### 3. `rag_service.py` の拡張
- `generate_advice_for_issue(issue)`: Issue辞書から直接アドバイス生成

### 4. `app.py` の簡素化
- Webhook関連エンドポイント削除（`/webhook/redmine`）
- ポーリングベースの初期化に変更
- 型安全性の改善

### 5. `config.py` の拡張
- `POLLING_INTERVAL_MINUTES`: ポーリング間隔設定（デフォルト5分）

### 6. `README.md` の全面改訂
- Webhook設定の削除
- ポーリング動作の説明
- 新しいシーケンス図
- 環境変数設定の更新
- トラブルシューティングの更新

## 新しい動作フロー

1. **起動時**: RAG初期化とスケジューラ開始
2. **ポーリング監視** (5分間隔):
   - Redmineから新規Issue検索
   - 新規Issue発見時：詳細取得→類似検索→AIアドバイス生成→コメント投稿
3. **RAG更新** (60分間隔):
   - 全Issue取得とベクトルDB更新

## 設定例

```bash
# .env ファイル
REDMINE_URL=http://your-redmine-server
REDMINE_API_KEY=your-api-key
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
POLLING_INTERVAL_MINUTES=5
UPDATE_INTERVAL_MINUTES=60
```

## 利点・欠点

### 利点
- Redmine側の設定不要
- Webhook機能が無いRedmineでも動作
- 安定したポーリング動作

### 欠点
- リアルタイム性がやや劣る（最大5分の遅延）
- ポーリング間隔が短いとRedmineサーバーへの負荷増加

## テスト確認
```bash
python test_setup.py  # ✓ All tests passed
```

すべての機能が正常に動作し、Webhook不要の自立型AIエージェントとして動作します。
