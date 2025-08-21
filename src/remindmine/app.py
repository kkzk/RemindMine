"""FastAPI web application for handling Redmine webhooks and providing API endpoints."""

import logging
import asyncio
from typing import Dict, Any
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
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
    description="AI Agent for Redmine issue analysis and advice",
    version="1.0.0"
)

# Global services
redmine_client = None
rag_service = None
scheduler = None


class WebhookPayload(BaseModel):
    """Redmine webhook payload model."""
    action: str
    issue: Dict[str, Any]


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
    scheduler = UpdateScheduler(redmine_client, rag_service, config.update_interval_minutes)
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
        "chromadb_path": config.chromadb_path
    }


@app.post("/webhook/redmine")
async def handle_redmine_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """Handle Redmine webhook for new issues.
    
    Args:
        request: HTTP request
        background_tasks: Background task manager
    """
    try:
        # Parse webhook payload
        payload = await request.json()
        logger.info(f"Received webhook: {payload}")
        
        # Validate payload structure
        if 'action' not in payload or 'issue' not in payload:
            raise HTTPException(status_code=400, detail="Invalid webhook payload")
        
        action = payload['action']
        issue = payload['issue']
        
        # Only process issue creation
        if action != 'opened' and action != 'created':
            logger.info(f"Ignoring action: {action}")
            return {"message": "Action ignored"}
        
        # Process issue in background
        background_tasks.add_task(process_new_issue, issue['id'])
        
        return {"message": "Webhook received and being processed"}
        
    except Exception as e:
        logger.error(f"Failed to handle webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def process_new_issue(issue_id: int):
    """Process new issue and generate advice.
    
    Args:
        issue_id: Issue ID to process
    """
    try:
        logger.info(f"Processing new issue: {issue_id}")
        
        # Fetch full issue details
        issue = redmine_client.get_issue(issue_id)
        if not issue:
            logger.error(f"Failed to fetch issue {issue_id}")
            return
        
        # Create search query from issue
        query = f"{issue.get('subject', '')} {issue.get('description', '')}"
        
        # Search for similar issues
        similar_issues = rag_service.search_similar_issues(query, n_results=5)
        
        if similar_issues:
            # Generate advice
            advice = rag_service.generate_advice(query, similar_issues)
            
            # Format advice comment
            comment = f"""🤖 **AI アドバイス**

{advice}

---
*このアドバイスは過去の類似事例を基にAIが生成しました。参考程度にご活用ください。*"""
            
            # Post comment to issue
            success = redmine_client.add_comment(issue_id, comment)
            
            if success:
                logger.info(f"Successfully posted AI advice to issue {issue_id}")
            else:
                logger.error(f"Failed to post AI advice to issue {issue_id}")
        else:
            logger.info(f"No similar issues found for issue {issue_id}")
            
    except Exception as e:
        logger.error(f"Failed to process issue {issue_id}: {e}")


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
    try:
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
    try:
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
    try:
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
    uvicorn.run(
        "remindmine.app:app",
        host=config.api_host,
        port=config.api_port,
        reload=False
    )


if __name__ == "__main__":
    main()
