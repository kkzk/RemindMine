#!/usr/bin/env python3
"""ChromaDBとRAGサービスの状態をデバッグするためのスクリプト"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import json
import chromadb
from chromadb.config import Settings
from src.remindmine.rag_service import RAGService
from src.remindmine.ai_providers import create_ai_provider
from src.remindmine.config import config

def debug_rag_state():
    print("=== RAG Debug Information ===\n")
    
    # AI プロバイダ情報
    ai_provider = create_ai_provider(
        config.ai_provider, 
        config.ollama_base_url, 
        config.ollama_model
    )
    print(f"AI Provider: {config.ai_provider}")
    print(f"Model: {config.ollama_embedding_model}")
    print(f"Embedding dimension: {getattr(ai_provider, 'default_dimension', 'unknown')}")
    print()
    
    # ChromaDB 直接アクセス
    chromadb_path = config.chromadb_path
    chroma_client = chromadb.PersistentClient(
        path=chromadb_path,
        settings=Settings(anonymized_telemetry=False)
    )
    
    print("=== ChromaDB Collections ===")
    collections = chroma_client.list_collections()
    for coll in collections:
        print(f"Collection: {coll.name}")
        print(f"  Count: {coll.count()}")
        print(f"  Metadata: {coll.metadata}")
        
        # 数件のドキュメントサンプルを表示
        if coll.count() > 0:
            sample = coll.peek(limit=3)
            if sample and 'documents' in sample and sample['documents']:
                docs = sample['documents']
                print(f"  Sample documents: {len(docs)} documents")
                for i, doc in enumerate(docs[:3]):
                    print(f"    Document {i}: {str(doc)[:100]}...")
        print()
    
    # RAG状態ファイル確認
    rag_state_path = os.path.join(os.path.dirname(chromadb_path), 'rag_index_state.json')
    print("=== RAG Index State ===")
    if os.path.exists(rag_state_path):
        with open(rag_state_path, 'r', encoding='utf-8') as f:
            state = json.load(f)
        print(f"Embedding Model: {state.get('embedding_model', 'unknown')}")
        print(f"Embedding Dimension: {state.get('embedding_dimension', 'unknown')}")
        print(f"Total Issues: {len(state.get('issues', {}))}")
        print("Issues in state:")
        for issue_id, issue_data in list(state.get('issues', {}).items())[:5]:
            print(f"  Issue {issue_id}: hash={issue_data.get('hash', '')[:8]}, chunks={issue_data.get('chunk_count', 0)}")
        if len(state.get('issues', {})) > 5:
            print(f"  ... and {len(state.get('issues', {})) - 5} more")
    else:
        print("RAG state file not found")
    print()
    
    # RAG サービス初期化してテスト検索
    print("=== RAG Service Test ===")
    try:
        rag_service = RAGService(chromadb_path=chromadb_path)
        print("RAG Service initialized successfully")
        
        # テスト検索
        test_results = rag_service.search_similar_issues("test query", n_results=3)
        print(f"Test search returned {len(test_results)} results")
        
        # 強制再インデックスのテスト
        print("\n=== Force Reindex Test ===")
        from src.remindmine.redmine_client import RedmineClient
        redmine_client = RedmineClient(
            base_url=config.redmine_url,
            api_key=config.redmine_api_key
        )
        issues = redmine_client.get_issues()
        print(f"Fetched {len(issues)} issues from Redmine")
        
        chunks_added = rag_service.index_issues(issues, full_rebuild=True)
        print(f"Force reindex added {chunks_added} chunks")
        
        # 再検索テスト
        test_results_after = rag_service.search_similar_issues("test query", n_results=3)
        print(f"Test search after reindex returned {len(test_results_after)} results")
        
    except Exception as e:
        print(f"RAG Service error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_rag_state()
