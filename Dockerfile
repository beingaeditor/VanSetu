# Hugging Face Spaces Docker deployment
# Runs both React frontend (static) and FastAPI backend

FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
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
    && rm -rf /var/lib/apt/lists/*

# Create non-root user (required by HF Spaces)
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

# Create cache and data directories (they may be gitignored)
RUN mkdir -p cache data/feedback

# Copy raster data files
COPY --chown=user:user delhi_ndvi_10m.tif ./
COPY --chown=user:user delhi_lst_modis_daily_celsius.tif ./

# Copy built frontend to serve as static files
COPY --from=frontend-builder --chown=user:user /app/frontend/dist ./static

# Expose port 7860 (Hugging Face Spaces default)
EXPOSE 7860

# Start the server
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
