"""Web API routes for RemindMine dashboard."""

import logging
import os
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Request, Form, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .redmine_client import RedmineClient
from .rag_service import RAGService
from .summary_service import SummaryService
from .web_config import web_config
from .pending_advice import pending_advice_manager

logger = logging.getLogger(__name__)

# Initialize templates
templates = Jinja2Templates(directory="src/remindmine/templates")

# Router for web endpoints
web_router = APIRouter()

# Dependency functions (will be set up by main app)
_rag_service = None
_redmine_client = None


def get_rag_service():
    """Get RAG service instance."""
    return _rag_service


def get_redmine_client():
    """Get Redmine client instance."""
    return _redmine_client


def set_dependencies(rag_service: RAGService, redmine_client: RedmineClient):
    """Set dependency instances."""
    global _rag_service, _redmine_client
    _rag_service = rag_service
    _redmine_client = redmine_client


# IssueCreateRequest は Issue 作成機能廃止に伴い削除


class SettingsUpdateRequest(BaseModel):
    """Request model for settings update."""
    issues_per_page: Optional[int] = None


class AutoAdviceSettingsRequest(BaseModel):
    """Request model for auto-advice settings."""
    enabled: bool


class AIProviderSettingsRequest(BaseModel):
    """Request model for AI provider settings."""
    ai_provider: str
    ollama_model: Optional[str] = None
    ollama_embedding_model: Optional[str] = None
    openai_model: Optional[str] = None
    openai_embedding_model: Optional[str] = None


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
    priority: Optional[str] = None,
    redmine_client: RedmineClient = Depends(get_redmine_client),
    rag_service: RAGService = Depends(get_rag_service)
):
    """Get paginated issues with filters."""
    try:
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
        total_issues = getattr(redmine_client, 'last_total_count', len(issues))
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


# POST /api/web/issues は廃止


@web_router.post("/api/web/issues/{issue_id}/advice")
async def generate_issue_advice(
    issue_id: int,
    redmine_client: RedmineClient = Depends(get_redmine_client),
    rag_service: RAGService = Depends(get_rag_service)
):
    """Generate AI advice for a specific issue."""
    try:
        if not redmine_client or not rag_service:
            raise HTTPException(status_code=503, detail="Services not initialized")
        
        # Get issue details
        issue = redmine_client.get_issue(issue_id)
        if not issue:
            raise HTTPException(status_code=404, detail="Issue not found")
        
        # Generate advice
        advice = rag_service.generate_advice_for_issue(issue)
        
        if advice:
            # Add to pending advice instead of posting directly
            advice_id = pending_advice_manager.add_pending_advice(issue, advice)
            
            return {
                "advice": advice,
                "advice_id": advice_id,
                "message": "Advice generated and added to pending list"
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
async def get_projects(redmine_client: RedmineClient = Depends(get_redmine_client)):
    """Get all projects from Redmine."""
    try:
        if not redmine_client:
            raise HTTPException(status_code=503, detail="Redmine client not initialized")
        
        projects = redmine_client.get_projects()
        return projects
        
    except Exception as e:
        logger.error(f"Failed to get projects: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch projects")


@web_router.get("/api/web/trackers")
async def get_trackers(redmine_client: RedmineClient = Depends(get_redmine_client)):
    """Get all trackers from Redmine."""
    try:
        if not redmine_client:
            raise HTTPException(status_code=503, detail="Redmine client not initialized")
        
        trackers = redmine_client.get_trackers()
        return trackers
        
    except Exception as e:
        logger.error(f"Failed to get trackers: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch trackers")


@web_router.get("/api/web/priorities")
async def get_priorities(redmine_client: RedmineClient = Depends(get_redmine_client)):
    """Get all priorities from Redmine."""
    try:
        if not redmine_client:
            raise HTTPException(status_code=503, detail="Redmine client not initialized")
        
        priorities = redmine_client.get_priorities()
        return priorities
        
    except Exception as e:
        logger.error(f"Failed to get priorities: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch priorities")


@web_router.get("/api/web/users")
async def get_users(redmine_client: RedmineClient = Depends(get_redmine_client)):
    """Get all users from Redmine."""
    try:
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
async def get_statuses(redmine_client: RedmineClient = Depends(get_redmine_client)):
    """Get all issue statuses from Redmine."""
    try:
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


@web_router.get("/api/web/pending-advice")
async def get_pending_advice():
    """Get all pending AI advice."""
    try:
        from .pending_advice import pending_advice_manager
        from .config import config
        
        pending_list = pending_advice_manager.get_all_pending()
        
        # Enhance with Redmine URL
        enhanced_list = []
        for pending in pending_list:
            enhanced = pending.to_dict()
            enhanced['issue_url'] = f"{config.redmine_url}/issues/{pending.issue_id}"
            enhanced_list.append(enhanced)
        
        return {
            "pending_advice": enhanced_list,
            "count": len(enhanced_list)
        }
        
    except Exception as e:
        logger.error(f"Failed to get pending advice: {e}")
        raise HTTPException(status_code=500, detail="Failed to get pending advice")


@web_router.post("/api/web/pending-advice/{advice_id}/approve")
async def approve_pending_advice(advice_id: str):
    """Approve and post pending AI advice to Redmine."""
    try:
        from .pending_advice import pending_advice_manager
        from .app import redmine_client
        
        if not redmine_client:
            raise HTTPException(status_code=503, detail="Redmine client not initialized")
        
        # Get pending advice
        pending = pending_advice_manager.get_pending_by_id(advice_id)
        if not pending:
            raise HTTPException(status_code=404, detail="Pending advice not found")
        
        # Post to Redmine
        success = redmine_client.add_comment(pending.issue_id, pending.advice_content)
        
        if success:
            # Remove from pending list
            pending_advice_manager.approve_advice(advice_id)
            
            return {
                "message": f"Advice approved and posted to issue #{pending.issue_id}",
                "issue_id": pending.issue_id
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to post advice to Redmine")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to approve advice {advice_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to approve advice: {str(e)}")


@web_router.post("/api/web/pending-advice/{advice_id}/reject")
async def reject_pending_advice(advice_id: str):
    """Reject and remove pending AI advice."""
    try:
        from .pending_advice import pending_advice_manager
        
        # Get pending advice
        pending = pending_advice_manager.get_pending_by_id(advice_id)
        if not pending:
            raise HTTPException(status_code=404, detail="Pending advice not found")
        
        # Remove from pending list
        pending_advice_manager.reject_advice(advice_id)
        
        return {
            "message": f"Advice for issue #{pending.issue_id} rejected and removed",
            "issue_id": pending.issue_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reject advice {advice_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reject advice: {str(e)}")


@web_router.delete("/api/web/pending-advice")
async def clear_all_pending_advice():
    """Clear all pending AI advice."""
    try:
        from .pending_advice import pending_advice_manager
        
        count = pending_advice_manager.clear_all_pending()
        
        return {
            "message": f"Cleared {count} pending advice items",
            "cleared_count": count
        }
        
    except Exception as e:
        logger.error(f"Failed to clear pending advice: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear pending advice")


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
        "ai_advice": None,
    # 新仕様: content_summary に本文+コメント統合サマリを格納。journal_summary は後方互換用に残すが常に None。
    "content_summary": None,
    "journal_summary": None,
        "has_journals": False,
        "journal_count": 0
    }
    
    # Check for existing AI advice in journals
    if issue.get("journals"):
        enhanced["has_journals"] = True
        enhanced["journal_count"] = len(issue["journals"])
        
        for journal in issue["journals"]:
            notes = journal.get("notes", "")
            if "🤖 AI自動アドバイス" in notes:
                # Extract advice content (remove the header)
                advice_lines = notes.split("\n")
                if len(advice_lines) > 1:
                    enhanced["ai_advice"] = "\n".join(advice_lines[2:]).strip()
                break
    
    # Generate summaries if we have rag_service (contains ollama config)
    if rag_service:
        try:
            # Initialize summary service with same ollama config as rag_service and cache
            from .config import config
            # Use the same data directory as chromadb for cache
            data_dir = os.path.dirname(config.chromadb_path)
            cache_file_path = os.path.join(data_dir, "summary_cache.json")
            
            summary_service = SummaryService(
                ollama_base_url=rag_service.ollama_base_url,
                ollama_model=rag_service.ollama_model,
                cache_file_path=cache_file_path
            )
            
            # Get all summary data (uses cache if available)
            summary_data = summary_service.get_issue_summary_data(issue)
            enhanced.update(summary_data)
            
        except Exception as e:
            logger.error(f"Failed to generate summaries for issue {issue.get('id', 'unknown')}: {e}")
    
    return enhanced


@web_router.post("/api/web/issues/{issue_id}/summaries/regenerate")
async def regenerate_issue_summaries(issue_id: int, rag_service: RAGService = Depends(get_rag_service), redmine_client: RedmineClient = Depends(get_redmine_client)):
    """Force invalidate and regenerate summaries for a specific issue.

    Frontend からの明示操作用。キャッシュを無効化し最新内容で再計算した結果を返す。
    """
    try:
        if not rag_service or not redmine_client:
            raise HTTPException(status_code=503, detail="Services not initialized")

        # Issue 詳細取得
        issue = redmine_client.get_issue(issue_id)
        if not issue:
            raise HTTPException(status_code=404, detail="Issue not found")

        from .config import config
        data_dir = os.path.dirname(config.chromadb_path)
        cache_file_path = os.path.join(data_dir, "summary_cache.json")

        summary_service = SummaryService(
            ollama_base_url=rag_service.ollama_base_url,
            ollama_model=rag_service.ollama_model,
            cache_file_path=cache_file_path
        )

        # キャッシュ無効化 -> 再生成
        summary_service.invalidate_issue_cache(issue_id)
        summary_data = summary_service.get_issue_summary_data(issue)

        return {"issue_id": issue_id, "summaries": summary_data, "message": "サマリを再生成しました"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to regenerate summaries for issue {issue_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to regenerate summaries")


@web_router.get("/api/web/cache/stats")
async def get_cache_stats(rag_service: RAGService = Depends(get_rag_service)):
    """Get summary cache statistics."""
    try:
        if not rag_service:
            return {"error": "RAG service not available"}
        
        from .config import config
        data_dir = os.path.dirname(config.chromadb_path)
        cache_file_path = os.path.join(data_dir, "summary_cache.json")
        
        summary_service = SummaryService(
            ollama_base_url=rag_service.ollama_base_url,
            ollama_model=rag_service.ollama_model,
            cache_file_path=cache_file_path
        )
        
        stats = summary_service.get_cache_stats()
        return {"success": True, "stats": stats}
        
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        return {"error": str(e)}


@web_router.get("/api/web/ai-provider/config")
async def get_ai_provider_config():
    """Get current AI provider configuration."""
    try:
        from .config import config
        
        # 利用可能なモデル一覧
        available_models = {
            "ollama": [
                "llama3.2:1b", "llama3.2:3b", "llama3.2", "llama3.1", 
                "codellama", "mistral", "qwen2.5", "phi3"
            ],
            "openai": [
                "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"
            ]
        }
        
        available_embedding_models = {
            "ollama": [
                "llama3.2", "mxbai-embed-large", "nomic-embed-text", "all-minilm"
            ],
            "openai": [
                "text-embedding-3-small", "text-embedding-3-large", "text-embedding-ada-002"
            ]
        }
        
        return {
            "current_provider": config.ai_provider,
            "current_config": {
                "ollama_model": config.ollama_model,
                "ollama_embedding_model": config.ollama_embedding_model,
                "openai_model": config.openai_model,
                "openai_embedding_model": config.openai_embedding_model,
            },
            "available_models": available_models,
            "available_embedding_models": available_embedding_models,
            "has_openai_key": bool(config.openai_api_key),
        }
        
    except Exception as e:
        logger.error(f"Failed to get AI provider config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@web_router.post("/api/web/ai-provider/config")
async def update_ai_provider_config(request: AIProviderSettingsRequest):
    """Update AI provider configuration."""
    try:
        # Web configの更新
        if request.ai_provider:
            web_config.ai_provider = request.ai_provider
        if request.ollama_model:
            web_config.ollama_model = request.ollama_model
        if request.ollama_embedding_model:
            web_config.ollama_embedding_model = request.ollama_embedding_model
        if request.openai_model:
            web_config.openai_model = request.openai_model
        if request.openai_embedding_model:
            web_config.openai_embedding_model = request.openai_embedding_model
        
        # 設定をファイルに保存（今後の起動時に反映されるよう）
        # 注意: 実際の設定反映にはサーバー再起動が必要
        return {
            "success": True, 
            "message": f"AIプロバイダを {request.ai_provider} に更新しました。変更を完全に反映するには再起動が必要です。",
            "restart_required": True
        }
        
    except Exception as e:
        logger.error(f"Failed to update AI provider config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@web_router.get("/api/web/ai-provider/test")
async def test_ai_provider(provider: Optional[str] = None):
    """Test AI provider connection."""
    try:
        from .config import config
        from .ai_providers import create_ai_provider
        
        test_provider = provider or config.ai_provider
        
        # プロバイダのテスト
        ai_provider = create_ai_provider(test_provider, config)
        
        # 簡単なテストクエリ
        test_query = "テスト"
        embedding = ai_provider.embed_query(test_query)
        
        if embedding and len(embedding) > 0:
            completion = ai_provider.generate_completion("こんにちはと挨拶してください。")
            return {
                "success": True,
                "provider": test_provider,
                "embedding_dimension": len(embedding),
                "test_completion": completion[:100] + "..." if completion and len(completion) > 100 else completion
            }
        else:
            return {
                "success": False,
                "provider": test_provider,
                "error": "エンベディング生成に失敗しました"
            }
            
    except Exception as e:
        logger.error(f"Failed to test AI provider: {e}")
        return {
            "success": False,
            "provider": provider or "unknown",
            "error": str(e)
        }


@web_router.post("/api/web/cache/clear")
async def clear_cache(rag_service: RAGService = Depends(get_rag_service)):
    """Clear all cached summaries."""
    try:
        if not rag_service:
            return {"error": "RAG service not available"}
        
        from .config import config
        data_dir = os.path.dirname(config.chromadb_path)
        cache_file_path = os.path.join(data_dir, "summary_cache.json")
        
        summary_service = SummaryService(
            ollama_base_url=rag_service.ollama_base_url,
            ollama_model=rag_service.ollama_model,
            cache_file_path=cache_file_path
        )
        
        summary_service.clear_cache()
        return {"success": True, "message": "キャッシュをクリアしました"}
        
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        return {"error": str(e)}


@web_router.post("/api/web/cache/invalidate/{issue_id}")
async def invalidate_issue_cache(issue_id: int, rag_service: RAGService = Depends(get_rag_service)):
    """Invalidate cache for a specific issue."""
    try:
        if not rag_service:
            return {"error": "RAG service not available"}
        
        from .config import config
        data_dir = os.path.dirname(config.chromadb_path)
        cache_file_path = os.path.join(data_dir, "summary_cache.json")
        
        summary_service = SummaryService(
            ollama_base_url=rag_service.ollama_base_url,
            ollama_model=rag_service.ollama_model,
            cache_file_path=cache_file_path
        )
        
        summary_service.invalidate_issue_cache(issue_id)
        return {"success": True, "message": f"Issue {issue_id} のキャッシュを無効化しました"}
        
    except Exception as e:
        logger.error(f"Failed to invalidate cache for issue {issue_id}: {e}")
        return {"error": str(e)}


@web_router.post("/api/web/rag/reindex")
async def reindex_rag(rag_service: RAGService = Depends(get_rag_service), redmine_client: RedmineClient = Depends(get_redmine_client)):
    """(管理) 全Issueを再取得しRAGベクトルインデックスを再構築。Embeddingモデル切替後などに利用。"""
    try:
        if not rag_service or not redmine_client:
            raise HTTPException(status_code=503, detail="Services not initialized")

        issues = redmine_client.get_all_issues_with_journals()
        chunk_count = rag_service.index_issues(issues)
        return {"success": True, "issues_indexed": len(issues), "chunks_indexed": chunk_count}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reindex RAG: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reindex: {e}")
