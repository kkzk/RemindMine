"""Command-line interface for RemindMine AI Agent."""

import argparse
import logging
import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from remindmine.config import config
from remindmine.redmine_client import RedmineClient
from remindmine.rag_service import RAGService
from remindmine.app import main as run_server

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_update():
    """Run RAG database update."""
    logger.info("Starting RAG database update...")
    
    try:
        # Initialize clients
        redmine_client = RedmineClient(config.redmine_url, config.redmine_api_key)
        rag_service = RAGService(
            config.chromadb_path,
            config.ai_provider
        )
        
        # Fetch and index issues
        logger.info("Fetching issues from Redmine...")
        issues = redmine_client.get_all_issues_with_journals()
        
        logger.info(f"Indexing {len(issues)} issues...")
        rag_service.index_issues(issues)
        
        logger.info("RAG database update completed successfully")
        
    except Exception as e:
        logger.error(f"RAG update failed: {e}")
        sys.exit(1)


def test_search(query: str):
    """Test search functionality."""
    logger.info(f"Testing search with query: {query}")
    
    try:
        # Initialize RAG service
        rag_service = RAGService(
            config.chromadb_path,
            config.ai_provider
        )
        
        # Search for similar issues
        results = rag_service.search_similar_issues(query, n_results=3)
        
        if results:
            print(f"\nFound {len(results)} similar issues:")
            for i, result in enumerate(results, 1):
                metadata = result.get('metadata', {})
                similarity = result.get('similarity', 0)
                print(f"\n{i}. Issue ID: {metadata.get('issue_id')}")
                print(f"   Subject: {metadata.get('subject')}")
                print(f"   Similarity: {similarity:.3f}")
                print(f"   Content: {result.get('content', '')[:200]}...")
        else:
            print("No similar issues found.")
            
    except Exception as e:
        logger.error(f"Search test failed: {e}")
        sys.exit(1)


def generate_advice(query: str):
    """Generate advice for a query."""
    logger.info(f"Generating advice for query: {query}")
    
    try:
        # Initialize RAG service
        rag_service = RAGService(
            config.chromadb_path,
            config.ai_provider
        )
        
        # Search for similar issues
        similar_issues = rag_service.search_similar_issues(query, n_results=5)
        
        if similar_issues:
            # Generate advice
            advice = rag_service.generate_advice(query, similar_issues)
            print(f"\nGenerated advice:\n{advice}")
        else:
            print("No similar issues found to generate advice from.")
            
    except Exception as e:
        logger.error(f"Advice generation failed: {e}")
        sys.exit(1)


def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(description="RemindMine AI Agent CLI")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Server command
    server_parser = subparsers.add_parser('server', help='Start the FastAPI server')
    
    # Update command
    update_parser = subparsers.add_parser('update', help='Update RAG database')
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Test search functionality')
    search_parser.add_argument('query', help='Search query')
    
    # Advice command
    advice_parser = subparsers.add_parser('advice', help='Generate advice for a query')
    advice_parser.add_argument('query', help='Query to generate advice for')
    
    args = parser.parse_args()
    
    if args.command == 'server':
        run_server()
    elif args.command == 'update':
        run_update()
    elif args.command == 'search':
        test_search(args.query)
    elif args.command == 'advice':
        generate_advice(args.query)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
