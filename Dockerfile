# VanSetu Platform — Docker deployment
# Runs both React frontend (static) and FastAPI backend

FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./

# Set the API URL for production build (backend is served from same origin)
ENV VITE_API_URL=/api
RUN npm run build

# --- Final image ---
FROM python:3.11-slim

# Install system dependencies for geospatial libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user (required by HF Spaces / Render)
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

# Install Python dependencies
COPY --chown=user:user backend/requirements.txt ./
RUN pip install --no-cache-dir --user -r requirements.txt

# Copy backend code
COPY --chown=user:user backend/app ./app

# Create cache and data directories
RUN mkdir -p cache data/feedback

# Copy raster data files if they exist (use conditional copy)
COPY --chown=user:user delhi_ndvi_10m.ti[f] ./
COPY --chown=user:user delhi_lst_modis_daily_celsius.ti[f] ./

# Copy built frontend to serve as static files
COPY --from=frontend-builder --chown=user:user /app/frontend/dist ./static

# Expose port (7860 for HF Spaces, 10000 for Render)
EXPOSE 7860
EXPOSE 10000

# Start the server — use PORT env var if set, otherwise default to 7860
CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
