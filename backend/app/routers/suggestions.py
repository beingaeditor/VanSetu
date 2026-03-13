"""
Suggestions Router — Community Suggestions API Endpoints

Endpoints for corridor-level community participation:
- POST /corridors/{id}/suggestions - Submit a suggestion
- GET /corridors/{id}/suggestions - Get suggestions for a corridor
- POST /suggestions/{id}/upvote - Upvote a suggestion

DESIGN NOTES:
- No authentication required
- IP-based rate limiting for abuse prevention
- Suggestions are advisory and don't affect corridor ranking
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from typing import List, Dict, Any

from app.dependencies import get_suggestion_service
from app.services.suggestion_service import SuggestionService


router = APIRouter()


class SuggestionCreate(BaseModel):
    """Request body for creating a suggestion."""
    text: str = Field(
        ..., 
        min_length=3, 
        max_length=300,
        description="Suggestion text (3-300 characters)"
    )


class SuggestionResponse(BaseModel):
    """Response model for a suggestion."""
    id: str
    text: str
    upvotes: int
    created_at: str


class SuggestionListResponse(BaseModel):
    """Response model for a list of suggestions."""
    corridor_id: str
    suggestions: List[SuggestionResponse]
    total: int


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, considering proxies."""
    # Check for forwarded headers (reverse proxy)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the first IP in the chain
        return forwarded.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fallback to direct client
    return request.client.host if request.client else "unknown"


@router.post(
    "/corridors/{corridor_id}/suggestions",
    response_model=SuggestionResponse,
    tags=["Community Suggestions"],
    summary="Submit a suggestion for a corridor",
    responses={
        201: {"description": "Suggestion created successfully"},
        400: {"description": "Invalid input"},
        429: {"description": "Rate limit exceeded"},
        503: {"description": "Database unavailable"}
    }
)
async def create_suggestion(
    corridor_id: str,
    body: SuggestionCreate,
    request: Request,
    suggestion_service: SuggestionService = Depends(get_suggestion_service)
) -> SuggestionResponse:
    """
    Submit a community suggestion for a specific corridor.
    
    Rate limited to 3 suggestions per IP per corridor per hour.
    
    Args:
        corridor_id: The corridor UUID
        body: Suggestion text (10-300 characters)
        
    Returns:
        Created suggestion with ID and initial upvote count
    """
    client_ip = get_client_ip(request)
    
    try:
        result = suggestion_service.create_suggestion(
            corridor_id=corridor_id,
            text=body.text,
            client_ip=client_ip
        )
        return SuggestionResponse(**result)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        error_msg = str(e)
        if "Rate limit" in error_msg:
            raise HTTPException(status_code=429, detail=error_msg)
        raise HTTPException(status_code=503, detail=error_msg)


@router.get(
    "/corridors/{corridor_id}/suggestions",
    response_model=SuggestionListResponse,
    tags=["Community Suggestions"],
    summary="Get suggestions for a corridor"
)
async def get_suggestions(
    corridor_id: str,
    suggestion_service: SuggestionService = Depends(get_suggestion_service)
) -> SuggestionListResponse:
    """
    Get all community suggestions for a corridor.
    
    Sorted by upvotes (descending), then by creation time (ascending).
    
    Args:
        corridor_id: The corridor UUID
        
    Returns:
        List of suggestions with upvote counts
    """
    suggestions = suggestion_service.get_suggestions(corridor_id)
    
    return SuggestionListResponse(
        corridor_id=corridor_id,
        suggestions=[SuggestionResponse(**s) for s in suggestions],
        total=len(suggestions)
    )


@router.post(
    "/suggestions/{suggestion_id}/upvote",
    response_model=SuggestionResponse,
    tags=["Community Suggestions"],
    summary="Upvote a suggestion",
    responses={
        200: {"description": "Upvote recorded"},
        404: {"description": "Suggestion not found"},
        429: {"description": "Rate limit exceeded"},
        503: {"description": "Database unavailable"}
    }
)
async def upvote_suggestion(
    suggestion_id: str,
    request: Request,
    suggestion_service: SuggestionService = Depends(get_suggestion_service)
) -> SuggestionResponse:
    """
    Upvote a community suggestion.
    
    Rate limited to 10 upvotes per IP per hour.
    
    Args:
        suggestion_id: The suggestion ID
        
    Returns:
        Updated suggestion with new upvote count
    """
    client_ip = get_client_ip(request)
    
    try:
        result = suggestion_service.upvote_suggestion(
            suggestion_id=suggestion_id,
            client_ip=client_ip
        )
        return SuggestionResponse(**result)
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        error_msg = str(e)
        if "Rate limit" in error_msg:
            raise HTTPException(status_code=429, detail=error_msg)
        raise HTTPException(status_code=503, detail=error_msg)


@router.get(
    "/corridors/{corridor_id}/suggestions/stats",
    tags=["Community Suggestions"],
    summary="Get suggestion statistics for a corridor"
)
async def get_suggestion_stats(
    corridor_id: str,
    suggestion_service: SuggestionService = Depends(get_suggestion_service)
) -> Dict[str, Any]:
    """
    Get statistics about community suggestions for a corridor.
    
    Args:
        corridor_id: The corridor UUID
        
    Returns:
        Suggestion count and total upvotes
    """
    return {
        "corridor_id": corridor_id,
        "suggestion_count": suggestion_service.get_suggestion_count(corridor_id),
        "total_upvotes": suggestion_service.get_total_upvotes(corridor_id)
    }


@router.post(
    "/corridors/{corridor_id}/upvote",
    tags=["Community Suggestions"],
    summary="Upvote a corridor",
    responses={
        200: {"description": "Upvote recorded"},
        429: {"description": "Rate limit exceeded"},
        503: {"description": "Database unavailable"}
    }
)
async def upvote_corridor(
    corridor_id: str,
    request: Request,
    suggestion_service: SuggestionService = Depends(get_suggestion_service)
) -> Dict[str, Any]:
    """
    Upvote a corridor to show community support.
    
    Rate limited to 10 upvotes per IP per hour.
    
    Args:
        corridor_id: The corridor UUID
        
    Returns:
        Updated corridor upvote count
    """
    client_ip = get_client_ip(request)
    
    try:
        result = suggestion_service.upvote_corridor(
            corridor_id=corridor_id,
            client_ip=client_ip
        )
        return result
        
    except RuntimeError as e:
        error_msg = str(e)
        if "Rate limit" in error_msg:
            raise HTTPException(status_code=429, detail=error_msg)
        raise HTTPException(status_code=503, detail=error_msg)


@router.get(
    "/corridors/{corridor_id}/upvotes",
    tags=["Community Suggestions"],
    summary="Get corridor upvote count"
)
async def get_corridor_upvotes(
    corridor_id: str,
    suggestion_service: SuggestionService = Depends(get_suggestion_service)
) -> Dict[str, Any]:
    """
    Get the upvote count for a corridor.
    
    Args:
        corridor_id: The corridor UUID
        
    Returns:
        Corridor upvote count
    """
    return {
        "corridor_id": corridor_id,
        "upvotes": suggestion_service.get_corridor_upvotes(corridor_id)
    }
