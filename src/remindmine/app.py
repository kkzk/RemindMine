"""FastAPI web application for Redmine issue analysis and advice API."""

import logging
import os
import sys
from typing import Dict, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks
import uvicorn

from .config import config
from .redmine_client import RedmineClient
from .rag_service import RAGService
from .scheduler import UpdateScheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="RemindMine AI Agent",
    description="AI Agent for Redmine issue analysis and advice with polling-based new issue detection",
    version="1.0.0"
)

# Global services
redmine_client = None
rag_service = None
scheduler = None


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global redmine_client, rag_service, scheduler
    
    logger.info("Starting RemindMine AI Agent...")
    
    # Initialize Redmine client
    redmine_client = RedmineClient(config.redmine_url, config.redmine_api_key)
    
    # Initialize RAG service
    rag_service = RAGService(
        config.chromadb_path,
        config.ollama_base_url,
        config.ollama_model
    )
    
    # Initialize and start scheduler
    scheduler = UpdateScheduler(
        redmine_client, 
        rag_service, 
        config.update_interval_minutes,
        config.polling_interval_minutes
    )
    scheduler.start()
    
    logger.info("RemindMine AI Agent started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global scheduler
    
    logger.info("Shutting down RemindMine AI Agent...")
    
    if scheduler:
        scheduler.stop()
    
    logger.info("RemindMine AI Agent shut down successfully")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "RemindMine AI Agent is running"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "redmine_url": config.redmine_url,
        "ollama_url": config.ollama_base_url,
        "chromadb_path": config.chromadb_path,
        "polling_enabled": True
    }


@app.post("/api/update-rag")
async def update_rag(background_tasks: BackgroundTasks):
    """Manually trigger RAG update.
    
    Returns:
        Status message
    """
    try:
        background_tasks.add_task(update_rag_database)
        return {"message": "RAG update started"}
    except Exception as e:
        logger.error(f"Failed to start RAG update: {e}")
        raise HTTPException(status_code=500, detail="Failed to start update")


async def update_rag_database():
    """Update RAG database with latest issues."""
    global redmine_client, rag_service
    
    try:
        if not redmine_client or not rag_service:
            logger.error("Services not initialized")
            return
            
        logger.info("Starting RAG database update...")
        
        # Fetch all issues with journals
        issues = redmine_client.get_all_issues_with_journals()
        
        # Index issues in RAG
        rag_service.index_issues(issues)
        
        logger.info("RAG database update completed successfully")
        
    except Exception as e:
        logger.error(f"Failed to update RAG database: {e}")


@app.get("/api/search")
async def search_issues(query: str, limit: int = 5):
    """Search for similar issues.
    
    Args:
        query: Search query
        limit: Number of results to return
        
    Returns:
        Search results
    """
    global rag_service
    
    try:
        if not rag_service:
            raise HTTPException(status_code=503, detail="RAG service not initialized")
            
        similar_issues = rag_service.search_similar_issues(query, n_results=limit)
        return {"results": similar_issues}
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail="Search failed")


@app.get("/api/stats")
async def get_stats():
    """Get RAG database statistics.
    
    Returns:
        Database statistics
    """
    global rag_service
    
    try:
        if not rag_service:
            raise HTTPException(status_code=503, detail="RAG service not initialized")
            
        # Get collection count
        count = rag_service.collection.count()
        
        return {
            "total_documents": count,
            "collection_name": rag_service.collection.name
        }
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")


def main():
    """Run the FastAPI application."""
    # デバッグモード判定
    debug_mode = (
        "--debug" in sys.argv or 
        os.getenv("DEBUG") == "1" or
        any("debugpy" in module for module in sys.modules.keys())
    )
    
    uvicorn.run(
        "remindmine.app:app",
        host=config.api_host,
        port=config.api_port,
        reload=debug_mode
    )


if __name__ == "__main__":
    main()
