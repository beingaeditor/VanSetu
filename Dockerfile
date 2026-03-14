# VanSetu Platform — Docker deployment
# Runs React frontend build + FastAPI backend for Render

# -------- FRONTEND BUILD --------
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./

ENV VITE_API_URL=/api
RUN npm run build


# -------- FINAL IMAGE --------
FROM python:3.11-slim

# System dependencies required for geospatial libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 user
USER user

ENV HOME=/home/user
ENV PATH=$HOME/.local/bin:$PATH

WORKDIR $HOME/app

# Install python dependencies
COPY --chown=user:user backend/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Copy backend source
COPY --chown=user:user backend/app ./app

# Create required directories
RUN mkdir -p cache data/feedback

# Copy raster data if present
COPY --chown=user:user delhi_ndvi_10m.tif* ./
COPY --chown=user:user delhi_lst_modis_daily_celsius.tif* ./

# Copy built frontend
COPY --from=frontend-builder --chown=user:user /app/frontend/dist ./static

# Render uses dynamic PORT
EXPOSE 10000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port $PORT"]
