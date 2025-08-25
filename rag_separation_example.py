"""RAGモジュール分離後の使用例とテストコード。

新しい分離されたRAGモジュールの使用方法を示します。
"""

# 新しい分離されたモジュールの使用例

# 1. インデックス構築専用（バッチ処理など重い処理向け）
from remindmine.rag import RAGIndexer

def build_index_example():
    indexer = RAGIndexer("./data/chromadb")
    
    # 課題データを取得（例）
    issues = [
        {
            "id": 1,
            "subject": "ログイン問題",
            "description": "ユーザーがログインできない",
            "status": {"name": "新規"},
            "priority": {"name": "高"},
            "tracker": {"name": "バグ"}
        }
    ]
    
    # インデックス構築
    chunk_count = indexer.index_issues(issues)
    print(f"インデックスに追加されたチャンク数: {chunk_count}")
    
    # 統計情報取得
    stats = indexer.get_index_stats()
    print(f"インデックス統計: {stats}")


# 2. 検索・アドバイス生成専用（Webアプリなど軽い処理向け）
from remindmine.rag import RAGSearcher

def search_and_advice_example():
    searcher = RAGSearcher("./data/chromadb")
    
    # 類似課題検索
    query = "ログインができない問題"
    similar_issues = searcher.search_similar_issues(query, n_results=3)
    print(f"類似課題: {len(similar_issues)}件")
    
    # アドバイス生成
    advice = searcher.generate_advice(query, similar_issues)
    print(f"アドバイス: {advice}")


# 3. 統合クラス使用（後方互換性、既存コードとの互換性維持）
from remindmine.rag import RAGService

def unified_service_example():
    service = RAGService("./data/chromadb")
    
    # 既存のAPIがそのまま使える
    issues = []  # 課題データ
    service.index_issues(issues)
    similar = service.search_similar_issues("問題の説明")
    advice = service.generate_advice("問題の説明", similar)


# 4. 既存のrag_service.pyも引き続き利用可能（非推奨警告付き）
from remindmine.rag_service import RAGService as LegacyRAGService

def legacy_example():
    # 非推奨警告が表示される
    service = LegacyRAGService("./data/chromadb")
    # 既存のAPIがそのまま動作


if __name__ == "__main__":
    print("RAG分離モジュールの使用例")
    print("=" * 50)
    
    try:
        print("1. インデックス構築例:")
        build_index_example()
        
        print("\n2. 検索・アドバイス例:")
        search_and_advice_example()
        
        print("\n3. 統合サービス例:")
        unified_service_example()
        
        print("\n分離完了！")
        
    except Exception as e:
        print(f"エラー: {e}")
