"""Web API routes for RemindMine dashboard."""

import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .redmine_client import RedmineClient
from .rag_service import RAGService
from .web_config import web_config

logger = logging.getLogger(__name__)

# Initialize templates
templates = Jinja2Templates(directory="src/remindmine/templates")

# Router for web endpoints
web_router = APIRouter()


class IssueCreateRequest(BaseModel):
    """Request model for issue creation."""
    project_id: int
    tracker_id: int
    subject: str
    description: Optional[str] = None
    priority_id: Optional[int] = None
    assigned_to_id: Optional[int] = None


class SettingsUpdateRequest(BaseModel):
    """Request model for settings update."""
    issues_per_page: Optional[int] = None


class AutoAdviceSettingsRequest(BaseModel):
    """Request model for auto-advice settings."""
    enabled: bool


@web_router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Serve the main dashboard page."""
    try:
        # Get system info for template
        from .config import config
        
        return templates.TemplateResponse("index.html", {
            "request": request,
            "web_config": web_config,
            "redmine_url": config.redmine_url,
            "ollama_url": config.ollama_base_url,
            "chromadb_path": config.chromadb_path
        })
    except Exception as e:
        logger.error(f"Failed to render dashboard: {e}")
        raise HTTPException(status_code=500, detail="Failed to load dashboard")


@web_router.get("/api/web/issues")
async def get_issues(
    page: int = 1,
    limit: int = 20,
    project: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None
):
    """Get paginated issues with filters."""
    try:
        from .app import redmine_client, rag_service
        
        if not redmine_client:
            raise HTTPException(status_code=503, detail="Redmine client not initialized")
        
        # Calculate offset
        offset = (page - 1) * limit
        
        # Build filters
        filters = {}
        if project:
            filters['project_id'] = project
        if status:
            filters['status_id'] = status
        if priority:
            filters['priority_id'] = priority
            
        # Get issues from Redmine
        issues = redmine_client.get_issues(
            status_id='*',  # All issues, let client-side handle filtering
            limit=limit,
            offset=offset
        )
        
        # Enhance issues with AI advice
        enhanced_issues = []
        for issue in issues:
            enhanced_issue = _enhance_issue_data(issue, rag_service)
            enhanced_issues.append(enhanced_issue)
        
        # Get total count (approximation)
        total_issues = len(issues)  # This is approximate
        total_pages = max(1, (total_issues + limit - 1) // limit)
        
        return {
            "issues": enhanced_issues,
            "pagination": {
                "current_page": page,
                "total_pages": total_pages,
                "total_issues": total_issues,
                "per_page": limit
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get issues: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch issues")


@web_router.post("/api/web/issues")
async def create_issue(issue_data: IssueCreateRequest):
    """Create a new issue in Redmine."""
    try:
        from .app import redmine_client
        
        if not redmine_client:
            raise HTTPException(status_code=503, detail="Redmine client not initialized")
        
        # Create issue in Redmine
        issue_id = redmine_client.create_issue(
            project_id=issue_data.project_id,
            tracker_id=issue_data.tracker_id,
            subject=issue_data.subject,
            description=issue_data.description,
            priority_id=issue_data.priority_id,
            assigned_to_id=issue_data.assigned_to_id
        )
        
        return {
            "id": issue_id,
            "message": "Issue created successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to create issue: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create issue: {str(e)}")


@web_router.post("/api/web/issues/{issue_id}/advice")
async def generate_issue_advice(issue_id: int):
    """Generate AI advice for a specific issue."""
    try:
        from .app import redmine_client, rag_service
        
        if not redmine_client or not rag_service:
            raise HTTPException(status_code=503, detail="Services not initialized")
        
        # Get issue details
        issue = redmine_client.get_issue(issue_id)
        if not issue:
            raise HTTPException(status_code=404, detail="Issue not found")
        
        # Generate advice
        advice = rag_service.generate_advice_for_issue(issue)
        
        if advice:
            # Post advice as comment to Redmine
            comment_text = f"🤖 AI自動アドバイス\n\n{advice}"
            redmine_client.add_comment(issue_id, comment_text)
            
            return {
                "advice": advice,
                "message": "Advice generated and posted successfully"
            }
        else:
            return {
                "advice": None,
                "message": "No advice could be generated"
            }
            
    except Exception as e:
        logger.error(f"Failed to generate advice for issue {issue_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate advice: {str(e)}")


@web_router.get("/api/web/projects")
async def get_projects():
    """Get all projects from Redmine."""
    try:
        from .app import redmine_client
        
        if not redmine_client:
            raise HTTPException(status_code=503, detail="Redmine client not initialized")
        
        projects = redmine_client.get_projects()
        return projects
        
    except Exception as e:
        logger.error(f"Failed to get projects: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch projects")


@web_router.get("/api/web/trackers")
async def get_trackers():
    """Get all trackers from Redmine."""
    try:
        from .app import redmine_client
        
        if not redmine_client:
            raise HTTPException(status_code=503, detail="Redmine client not initialized")
        
        trackers = redmine_client.get_trackers()
        return trackers
        
    except Exception as e:
        logger.error(f"Failed to get trackers: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch trackers")


@web_router.get("/api/web/priorities")
async def get_priorities():
    """Get all priorities from Redmine."""
    try:
        from .app import redmine_client
        
        if not redmine_client:
            raise HTTPException(status_code=503, detail="Redmine client not initialized")
        
        priorities = redmine_client.get_priorities()
        return priorities
        
    except Exception as e:
        logger.error(f"Failed to get priorities: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch priorities")


@web_router.get("/api/web/users")
async def get_users():
    """Get all users from Redmine."""
    try:
        from .app import redmine_client
        
        if not redmine_client:
            raise HTTPException(status_code=503, detail="Redmine client not initialized")
        
        users = redmine_client.get_users()
        return users
        
    except Exception as e:
        logger.error(f"Failed to get users: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch users")


@web_router.get("/api/web/settings")
async def get_settings():
    """Get current web UI settings."""
    try:
        return {
            "auto_advice_enabled": web_config.auto_advice_enabled,
            "issues_per_page": web_config.issues_per_page,
            "max_advice_length": web_config.max_advice_length
        }
    except Exception as e:
        logger.error(f"Failed to get settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to get settings")


@web_router.get("/api/web/statuses")
async def get_statuses():
    """Get all issue statuses from Redmine."""
    try:
        from .app import redmine_client
        
        if not redmine_client:
            raise HTTPException(status_code=503, detail="Redmine client not initialized")
        
        statuses = redmine_client.get_statuses()
        return statuses
        
    except Exception as e:
        logger.error(f"Failed to get statuses: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch statuses")


@web_router.post("/api/web/settings")
async def update_settings(settings: SettingsUpdateRequest):
    """Update web UI settings."""
    try:
        if settings.issues_per_page is not None:
            web_config.issues_per_page = settings.issues_per_page
        
        return {"message": "Settings updated successfully"}
        
    except Exception as e:
        logger.error(f"Failed to update settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to update settings")


@web_router.post("/api/web/settings/auto-advice")
async def update_auto_advice_settings(settings: AutoAdviceSettingsRequest):
    """Update auto-advice settings."""
    try:
        web_config.auto_advice_enabled = settings.enabled
        
        return {
            "enabled": web_config.auto_advice_enabled,
            "message": "Auto-advice settings updated successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to update auto-advice settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to update auto-advice settings")


def _enhance_issue_data(issue: Dict[str, Any], rag_service: Optional[RAGService]) -> Dict[str, Any]:
    """Enhance issue data with additional information for web display."""
    from .config import config
    
    enhanced = {
        "id": issue.get("id"),
        "subject": issue.get("subject", ""),
        "description": issue.get("description", ""),
        "status": issue.get("status", {}).get("name", "Unknown"),
        "priority": issue.get("priority", {}).get("name", "Normal"),
        "project": issue.get("project", {}).get("name", "Unknown"),
        "tracker": issue.get("tracker", {}).get("name", "Unknown"),
        "assigned_to": issue.get("assigned_to", {}).get("name") if issue.get("assigned_to") else None,
        "created_on": issue.get("created_on"),
        "updated_on": issue.get("updated_on"),
        "redmine_url": f"{config.redmine_url}/issues/{issue.get('id')}",
        "ai_advice": None
    }
    
    # Check for existing AI advice in journals
    if issue.get("journals"):
        for journal in issue["journals"]:
            notes = journal.get("notes", "")
            if "🤖 AI自動アドバイス" in notes:
                # Extract advice content (remove the header)
                advice_lines = notes.split("\n")
                if len(advice_lines) > 1:
                    enhanced["ai_advice"] = "\n".join(advice_lines[2:]).strip()
                break
    
    return enhanced
