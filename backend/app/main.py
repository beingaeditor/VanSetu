"""
FastAPI Application Entry Point

VanSetu Platform — Backend API
"""
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager

from app.config import get_settings
from app.dependencies import init_services, cleanup_services, get_raster_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Load raster data on startup, cleanup on shutdown.
    """
    settings = get_settings()
    
    print("=" * 60)
    print("🚀 Starting VanSetu Platform API")
    print("=" * 60)
    
    # Initialize all services
    print("\n📂 Loading raster data...")
    init_services()
    
    raster = get_raster_service()
    print(f"   Raster shape: {raster.shape}")
    print(f"   Bounds: {raster.bounds}")
    
    print("\n✅ API Ready!")
    print(f"   Swagger UI: http://localhost:8000/docs")
    print(f"   API Base: http://localhost:8000{settings.api_prefix}")
    print("=" * 60 + "\n")
    
    yield  # Application runs here
    
    # Cleanup
    print("\n🛑 Shutting down...")
    cleanup_services()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title=settings.app_name,
        description="API for VanSetu urban corridor analysis and visualization",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    
    # CORS middleware for frontend access
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Import routers here to avoid circular imports
    from app.routers import layers, tiles, roads, stats, aqi, corridors, suggestions, admin
    
    # Include routers
    app.include_router(layers.router, prefix=settings.api_prefix, tags=["Layers"])
    app.include_router(tiles.router, prefix=settings.api_prefix, tags=["Tiles"])
    app.include_router(roads.router, prefix=settings.api_prefix, tags=["Roads"])
    app.include_router(stats.router, prefix=settings.api_prefix, tags=["Statistics"])
    app.include_router(aqi.router, prefix=settings.api_prefix, tags=["Air Quality"])
    app.include_router(corridors.router, prefix=settings.api_prefix, tags=["Corridor Aggregation"])
    app.include_router(suggestions.router, prefix=settings.api_prefix, tags=["Community Suggestions"])
    app.include_router(admin.router, prefix=settings.api_prefix, tags=["Admin Dashboard"])
    
    @app.get("/health", tags=["Health"])
    async def health_check():
        """Detailed health check."""
        raster = get_raster_service()
        return {
            "status": "healthy",
            "raster_loaded": raster is not None and raster.is_loaded,
            "bounds": settings.delhi_bounds
        }
    
    # Serve static frontend files if the static directory exists (Docker deployment)
    static_dir = Path(__file__).parent.parent / "static"
    print(f"📁 Checking for static dir: {static_dir} (exists: {static_dir.exists()})")
    
    if static_dir.exists():
        print(f"✅ Serving frontend from {static_dir}")
        
        # Serve static assets (JS, CSS, etc.)
        if (static_dir / "assets").exists():
            app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")
        
        # Override the root route to serve index.html
        @app.get("/", include_in_schema=False)
        async def serve_index():
            """Serve the React SPA index."""
            return FileResponse(static_dir / "index.html")
        
        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str):
            """Serve the React SPA for any non-API routes."""
            # Don't intercept API routes or docs
            if full_path.startswith("api") or full_path in ["docs", "redoc", "openapi.json", "health"]:
                return None
            
            file_path = static_dir / full_path
            if file_path.exists() and file_path.is_file():
                return FileResponse(file_path)
            # Return index.html for SPA routing
            return FileResponse(static_dir / "index.html")
    
    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
