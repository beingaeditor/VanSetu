"""
Tiles Router — XYZ tile server endpoints.
"""
from fastapi import APIRouter, HTTPException, Response, Depends

from app.dependencies import get_tile_service
from app.services.tile_service import TileService

router = APIRouter()


@router.get("/tiles/{layer}/{z}/{x}/{y}.png")
async def get_tile(
    layer: str,
    z: int,
    x: int,
    y: int,
    tile_service: TileService = Depends(get_tile_service)
) -> Response:
    """
    Get a map tile for the specified layer.
    
    Args:
        layer: Layer name (ndvi, lst, gdi)
        z: Zoom level
        x: Tile X coordinate
        y: Tile Y coordinate
        
    Returns:
        PNG image tile
    """
    valid_layers = ['ndvi', 'lst', 'gdi']
    
    if layer.lower() not in valid_layers:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid layer. Must be one of: {valid_layers}"
        )
    
    if z < 1 or z > 18:
        raise HTTPException(status_code=400, detail="Zoom level must be between 1 and 18")
    
    tile_bytes = tile_service.get_tile(layer.lower(), z, x, y)
    
    if tile_bytes is None:
        # Return transparent tile for out-of-bounds requests
        return Response(
            content=b'',
            status_code=204,
            headers={"Content-Type": "image/png"}
        )
    
    return Response(
        content=tile_bytes,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Access-Control-Allow-Origin": "*"
        }
    )


@router.delete("/tiles/cache")
async def clear_tile_cache(
    tile_service: TileService = Depends(get_tile_service)
):
    """Clear the tile cache."""
    tile_service.clear_cache()
    return {"status": "ok", "message": "Tile cache cleared"}
