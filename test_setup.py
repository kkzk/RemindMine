"""Simple test script to verify RemindMine setup."""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_imports():
    """Test if all modules can be imported."""
    try:
        from remindmine.config import config
        print("✓ Config module imported successfully")
        
        from remindmine.redmine_client import RedmineClient
        print("✓ Redmine client module imported successfully")
        
        from remindmine.rag_service import RAGService
        print("✓ RAG service module imported successfully")
        
        from remindmine.scheduler import UpdateScheduler
        print("✓ Scheduler module imported successfully")
        
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

def test_config():
    """Test configuration loading."""
    try:
        from remindmine.config import config
        
        print(f"Redmine URL: {config.redmine_url}")
        print(f"Ollama URL: {config.ollama_base_url}")
        print(f"Ollama Model: {config.ollama_model}")
        print(f"ChromaDB Path: {config.chromadb_path}")
        print(f"API Port: {config.api_port}")
        
        return True
    except Exception as e:
        print(f"✗ Config error: {e}")
        return False

def test_chromadb():
    """Test ChromaDB initialization."""
    try:
        import chromadb
        from chromadb.config import Settings
        
        # Test creating a temporary client
        client = chromadb.Client(Settings(anonymized_telemetry=False))
        collection = client.get_or_create_collection("test")
        print("✓ ChromaDB can be initialized")
        
        return True
    except Exception as e:
        print(f"✗ ChromaDB error: {e}")
        return False

def main():
    """Run all tests."""
    print("RemindMine Setup Test")
    print("=" * 50)
    
    tests = [
        ("Module Imports", test_imports),
        ("Configuration", test_config),
        ("ChromaDB", test_chromadb),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\nTesting {test_name}...")
        if test_func():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ All tests passed! RemindMine is ready to use.")
        print("\nNext steps:")
        print("1. Configure your .env file with Redmine and Ollama settings")
        print("2. Run 'python cli.py update' to populate the RAG database")
        print("3. Run 'python cli.py server' to start the API server")
    else:
        print("✗ Some tests failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
