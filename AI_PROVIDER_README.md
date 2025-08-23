# AIプロバイダ切り替え機能実装

## 概要

RemindMineにOllamaとOpenAI間でのAIプロバイダ切り替え機能を実装しました。
管理画面から各プロバイダとモデルを選択・切り替えできるようになりました。

## 実装内容

### 1. 設定の拡張 (`config.py`)

新しい環境変数を追加：
- `AI_PROVIDER`: プロバイダ選択 ("ollama" または "openai")
- `OLLAMA_EMBEDDING_MODEL`: Ollama用エンベディングモデル
- `OPENAI_API_KEY`: OpenAI APIキー
- `OPENAI_MODEL`: OpenAI LLMモデル
- `OPENAI_EMBEDDING_MODEL`: OpenAI エンベディングモデル
- `OPENAI_BASE_URL`: カスタムエンドポイント（オプション）

### 2. AIプロバイダ抽象化 (`ai_providers.py`)

- `AIProvider` 基底クラス: 共通インターフェース定義
- `OllamaProvider`: Ollama実装
- `OpenAIProvider`: OpenAI実装
- `create_ai_provider()`: ファクトリ関数

### 3. RAGサービス更新 (`rag_service.py`)

- 新しいプロバイダシステムを使用
- 後方互換性を維持
- エラーハンドリングとフォールバック機能

### 4. Web UI管理画面

新しい設定セクション「AIプロバイダ設定」を追加：
- プロバイダ選択（Ollama/OpenAI）
- 各プロバイダのモデル選択
- APIキー状態表示
- プロバイダテスト機能
- 設定保存機能

### 5. API エンドポイント

- `GET /api/web/ai-provider/config`: 現在の設定取得
- `POST /api/web/ai-provider/config`: 設定更新
- `GET /api/web/ai-provider/test`: プロバイダテスト

## 使用方法

### 環境変数設定

`.env.example` を参考に `.env` ファイルを作成し、必要な設定を行います：

```bash
# Ollamaを使用する場合
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
OLLAMA_EMBEDDING_MODEL=llama3.2

# OpenAIを使用する場合
AI_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

### Web UI からの設定

1. ダッシュボードで「設定」タブを開く
2. 「AIプロバイダ設定」セクションでプロバイダを選択
3. 使用するモデルを選択
4. 「プロバイダ設定保存」ボタンで保存
5. 「AIプロバイダテスト」で動作確認

### 利用可能なモデル

#### Ollama
- **LLM**: llama3.2:1b, llama3.2:3b, llama3.2, llama3.1, codellama, mistral, qwen2.5, phi3
- **Embedding**: llama3.2, mxbai-embed-large, nomic-embed-text, all-minilm

#### OpenAI
- **LLM**: gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo
- **Embedding**: text-embedding-3-small, text-embedding-3-large, text-embedding-ada-002

## 注意事項

1. **再起動が必要**: プロバイダ変更後は完全に反映するためサーバー再起動が推奨されます
2. **APIキー**: OpenAI使用時は有効なAPIキーが必要です
3. **費用**: OpenAI使用時はAPI利用料金が発生します
4. **性能**: プロバイダとモデルにより応答速度と品質が異なります

## トラブルシューティング

### OpenAI接続エラー
- APIキーが正しく設定されているか確認
- アカウントにクレジットが残っているか確認
- ネットワーク接続を確認

### Ollama接続エラー
- Ollamaサービスが起動しているか確認 (`ollama serve`)
- 指定したモデルがダウンロード済みか確認 (`ollama list`)
- モデルをダウンロード (`ollama pull llama3.2`)

### プロバイダテスト失敗
- Web UI の「AIプロバイダテスト」機能で診断
- エラーメッセージを確認してトラブルシューティング

## 今後の拡張

- Azure OpenAI Service対応
- Claude API対応
- ローカルHugging Face Transformers対応
- プロバイダ固有の詳細設定
- 自動フェイルオーバー機能
