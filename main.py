"""
VanSetu Platform — Visualization Generator

A comprehensive geospatial visualization suite for pitch deck generation.
Produces publication-quality cartographic outputs from raster and vector data.

Purpose: Generate 6 core figures for VanSetu planning platform
"""

import os
import sys
import warnings
import numpy as np
import rasterio
from rasterio.plot import show
from rasterio.windows import from_bounds
from rasterio.transform import rowcol, Affine
from scipy.ndimage import zoom
import geopandas as gpd
from shapely.geometry import box, LineString, Point
from shapely.ops import unary_union
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.lines import Line2D
import contextily as ctx
import osmnx as ox
import pandas as pd

warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

# FILE PATHS — MODIFY THESE TO POINT TO YOUR LOCAL GEOTIFF FILES
NDVI_PATH = "delhi_ndvi_10m.tif"  # Sentinel-2 NDVI, 10m resolution
LST_PATH = "delhi_lst_modis_daily_celsius.tif"    # MODIS LST, ~1km resolution
OUTPUT_DIR = "./figures/"

# DELHI BOUNDS (approximate)
DELHI_BOUNDS = {
    'north': 28.87,
    'south': 28.40,
    'east': 77.35,
    'west': 76.73
}

# VISUALIZATION DEFAULTS
DPI = 300
FIGSIZE_16_9 = (16, 9)  # 16:9 aspect ratio for slides
FIGSIZE_SQUARE = (12, 12)
BACKGROUND_COLOR = '#f5f5f5'
TEXT_COLOR = '#333333'

# COLOR MAPS
CMAP_HEAT = plt.cm.RdYlBu_r  # Red for hot
CMAP_NDVI = plt.cm.YlGn      # Green for vegetation
# Priority: Green (already green, low GDI) → Yellow → Red (needs VanSetu corridors, high GDI)
CMAP_PRIORITY = LinearSegmentedColormap.from_list(
    'priority', ['#1a9850', '#fee090', '#d73027']  # Green → Yellow → Red
)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def ensure_output_dir():
    """Create output directory if it doesn't exist."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"✓ Output directory ready: {OUTPUT_DIR}")


def load_geotiff(filepath):
    """
    Load a GeoTIFF file using rasterio.
    
    Args:
        filepath (str): Path to GeoTIFF file
        
    Returns:
        data (np.ndarray): Raster data
        profile (dict): Raster metadata (CRS, transform, etc.)
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"GeoTIFF not found: {filepath}")
    
    with rasterio.open(filepath) as src:
        data = src.read(1)  # Read first band
        profile = src.profile
    
    print(f"✓ Loaded: {filepath}")
    print(f"  - Shape: {data.shape}, CRS: {profile['crs']}, NoData: {profile['nodata']}")
    
    return data, profile


def normalize_array(arr, vmin=None, vmax=None):
    """
    Normalize array to [0, 1] range, handling NoData values.
    
    Args:
        arr (np.ndarray): Input array
        vmin (float): Minimum value for normalization
        vmax (float): Maximum value for normalization
        
    Returns:
        normalized (np.ndarray): Normalized array in [0, 1]
    """
    # Handle NoData (typically masked or NaN)
    valid_mask = np.isfinite(arr)
    
    if vmin is None:
        vmin = np.nanmin(arr[valid_mask]) if np.any(valid_mask) else 0
    if vmax is None:
        vmax = np.nanmax(arr[valid_mask]) if np.any(valid_mask) else 1
    
    normalized = np.zeros_like(arr, dtype=np.float32)
    normalized[valid_mask] = (arr[valid_mask] - vmin) / (vmax - vmin + 1e-8)
    normalized[~valid_mask] = np.nan
    
    return np.clip(normalized, 0, 1)


def compute_green_deficit_index(ndvi, lst):
    """
    Compute Green Deficit Index from NDVI and LST.
    
    GDI = (normalized_heat * 0.6) + ((1 - normalized_ndvi) * 0.4)
    
    Args:
        ndvi (np.ndarray): NDVI raster [-1, 1]
        lst (np.ndarray): Land Surface Temperature [°C]
        
    Returns:
        gdi (np.ndarray): Green Deficit Index [0, 1] (0=low priority, 1=high priority)
    """
    # Normalize inputs
    ndvi_norm = normalize_array(ndvi, vmin=-0.2, vmax=0.8)
    lst_norm = normalize_array(lst, vmin=22, vmax=32)
    
    # Compute GDI
    gdi = (lst_norm * 0.6) + ((1 - ndvi_norm) * 0.4)
    
    return np.clip(gdi, 0, 1)


def get_delhi_bounds_utm(profile_crs):
    """
    Convert Delhi bounds to the CRS of the raster.
    
    Args:
        profile_crs (CRS): Rasterio CRS object
        
    Returns:
        bounds (tuple): (minx, miny, maxx, maxy)
    """
    bounds_geom = box(
        DELHI_BOUNDS['west'],
        DELHI_BOUNDS['south'],
        DELHI_BOUNDS['east'],
        DELHI_BOUNDS['north']
    )
    
    # If raster is not in EPSG:4326, reproject bounds
    if profile_crs.to_string() != 'EPSG:4326':
        from rasterio.crs import CRS
        gdf = gpd.GeoDataFrame(
            {'geometry': [bounds_geom]},
            crs='EPSG:4326'
        )
        gdf = gdf.to_crs(profile_crs)
        bounds_geom = gdf.geometry.iloc[0]
    
    return bounds_geom.bounds


def resample_raster_to_match(source_data, source_profile, target_data, target_profile):
    """
    Resample source raster to match target raster's extent and resolution.
    
    Args:
        source_data (np.ndarray): Source raster data
        source_profile (dict): Source raster profile
        target_data (np.ndarray): Target raster data (for shape reference)
        target_profile (dict): Target raster profile
        
    Returns:
        resampled (np.ndarray): Resampled data matching target shape
    """
    from rasterio.transform import Affine
    from scipy.ndimage import zoom
    
    # Calculate zoom factors
    zoom_row = source_data.shape[0] / target_data.shape[0]
    zoom_col = source_data.shape[1] / target_data.shape[1]
    
    # Resample using scipy
    resampled = zoom(source_data, (1/zoom_row, 1/zoom_col), order=1)
    
    # Ensure exact shape match
    if resampled.shape != target_data.shape:
        resampled = resampled[:target_data.shape[0], :target_data.shape[1]]
    
    return resampled


def fetch_roads_delhi(tags=None):
    """
    Fetch road network for Delhi from OpenStreetMap via OSMnx.
    
    Args:
        tags (dict): OSM tags to filter roads (default: major + secondary)
        
    Returns:
        gdf (GeoDataFrame): Road network with geometries
        
    Raises:
        RuntimeError: If OSM fetch fails
    """
    print("⏳ Fetching road network from OpenStreetMap (this may take 1–2 minutes)...")
    
    if tags is None:
        tags = {
            'highway': ['motorway', 'trunk', 'primary', 'secondary', 'tertiary']
        }
    
    # OSMnx bbox format: (left, bottom, right, top) = (west, south, east, north)
    bbox = (
        DELHI_BOUNDS['west'],
        DELHI_BOUNDS['south'],
        DELHI_BOUNDS['east'],
        DELHI_BOUNDS['north']
    )
    
    # Fetch features from OSM
    features = ox.features_from_bbox(bbox=bbox, tags=tags)
    
    # Convert to GeoDataFrame and filter to LineString geometries
    gdf = gpd.GeoDataFrame(features).reset_index()
    
    # Keep only LineString and MultiLineString geometries (roads)
    valid_geom_types = ['LineString', 'MultiLineString']
    gdf = gdf[gdf.geometry.geom_type.isin(valid_geom_types)].copy()
    
    # Ensure CRS is EPSG:4326
    if gdf.crs is None:
        gdf = gdf.set_crs('EPSG:4326')
    else:
        gdf = gdf.to_crs('EPSG:4326')
    
    if len(gdf) == 0:
        raise RuntimeError("No road features found in the specified bounding box")
    
    print(f"✓ Fetched {len(gdf)} road segments")
    return gdf


def sample_raster_along_roads(gdf, raster, transform, buffer_distance=0.002):
    """
    Sample raster values along buffered road segments using coordinate transformation.
    
    Args:
        gdf (GeoDataFrame): Road geometries in EPSG:4326
        raster (np.ndarray): Raster data array
        transform (Affine): Rasterio affine transform
        buffer_distance (float): Buffer distance in degrees (~200m at equator)
        
    Returns:
        gdf (GeoDataFrame): Original GDF with new 'raster_mean' column
    """
    from rasterio.transform import rowcol
    from shapely.geometry import MultiLineString
    
    sampled_values = []
    raster_height, raster_width = raster.shape
    
    for geom in gdf.geometry:
        try:
            # Handle MultiLineString by converting to list of coordinates
            if isinstance(geom, MultiLineString):
                all_coords = []
                for line in geom.geoms:
                    all_coords.extend(list(line.coords))
                coords = np.array(all_coords)
            else:
                coords = np.array(geom.coords)
            
            if len(coords) == 0:
                sampled_values.append(np.nan)
                continue
            
            # Sample points along the line at regular intervals
            # Interpolate to get more sample points
            num_samples = max(10, int(geom.length / 0.001))  # ~100m intervals
            
            sample_points = []
            for i in range(num_samples):
                point = geom.interpolate(i / num_samples, normalized=True)
                sample_points.append((point.x, point.y))
            
            # Convert geographic coordinates to raster row/col indices
            pixel_values = []
            for lon, lat in sample_points:
                try:
                    row, col = rowcol(transform, lon, lat)
                    # Check bounds
                    if 0 <= row < raster_height and 0 <= col < raster_width:
                        val = raster[row, col]
                        if np.isfinite(val):
                            pixel_values.append(val)
                except Exception:
                    continue
            
            if len(pixel_values) > 0:
                sampled_values.append(np.mean(pixel_values))
            else:
                sampled_values.append(np.nan)
                
        except Exception as e:
            sampled_values.append(np.nan)
    
    gdf = gdf.copy()
    gdf['raster_mean'] = sampled_values
    
    # Report sampling success rate
    valid_count = sum(1 for v in sampled_values if np.isfinite(v))
    print(f"  ✓ Sampled GDI for {valid_count}/{len(gdf)} road segments")
    
    return gdf


def add_scale_bar(ax, length_km=2, location='lower left', **kwargs):
    """
    Add a simple scale bar to a map axes.
    
    Args:
        ax (Axes): Matplotlib axes
        length_km (float): Desired scale bar length in kilometers
        location (str): Position on map
    """
    from matplotlib_scalebar.scalebar import ScaleBar
    try:
        scalebar = ScaleBar(1, units="m", length_fraction=0.3, location=location)
        ax.add_artist(scalebar)
    except ImportError:
        # ScaleBar not installed; skip
        pass


def save_figure(fig, filename, dpi=DPI):
    """
    Save figure as high-resolution PNG.
    
    Args:
        fig (Figure): Matplotlib figure object
        filename (str): Output filename (without path)
        dpi (int): Resolution in DPI
    """
    filepath = os.path.join(OUTPUT_DIR, filename)
    fig.savefig(filepath, dpi=dpi, bbox_inches='tight', facecolor='white')
    print(f"✓ Saved: {filepath}")


# ============================================================================
# VISUALIZATION FUNCTIONS
# ============================================================================

def figure_1_city_heat_context(lst_data, profile):
    """
    Figure 1: City Heat Context
    
    Basemap with LST heatmap overlay.
    Purpose: "Delhi experiences uneven heat distribution"
    """
    print("📊 Generating Figure 1: City Heat Context...")
    
    fig, ax = plt.subplots(figsize=FIGSIZE_16_9, dpi=DPI)
    
    # Normalize LST
    lst_norm = normalize_array(lst_data, vmin=22, vmax=32)
    
    # Plot LST heatmap
    im = ax.imshow(
        lst_norm,
        cmap=CMAP_HEAT,
        alpha=0.75,
        origin='upper',
        extent=[DELHI_BOUNDS['west'], DELHI_BOUNDS['east'], 
                DELHI_BOUNDS['south'], DELHI_BOUNDS['north']]
    )
    
    # Add basemap context (if available)
    try:
        ctx.add_basemap(
            ax,
            crs='EPSG:4326',
            source=ctx.providers.CartoDB.Positron,
            zoom=11,
            alpha=0.3
        )
    except Exception:
        ax.set_facecolor(BACKGROUND_COLOR)
    
    ax.set_xlim(DELHI_BOUNDS['west'], DELHI_BOUNDS['east'])
    ax.set_ylim(DELHI_BOUNDS['south'], DELHI_BOUNDS['north'])
    ax.axis('off')
    fig.patch.set_facecolor('white')
    
    # Subtle title
    ax.text(
        0.5, 0.95,
        'Heat Distribution Across Delhi',
        ha='center', va='top',
        transform=ax.transAxes,
        fontsize=18, weight='bold',
        color=TEXT_COLOR
    )
    
    # Simple colorbar (minimal style)
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Surface Temperature (°C)', fontsize=12, color=TEXT_COLOR)
    cbar.ax.tick_params(labelsize=10, colors=TEXT_COLOR)
    
    save_figure(fig, '01_city_heat_context.png')
    plt.close(fig)


def figure_2_green_cover_distribution(ndvi_data, profile):
    """
    Figure 2: Green Cover Distribution
    
    NDVI visualization with green emphasis.
    Purpose: "Green spaces exist, but are unevenly distributed"
    """
    print("📊 Generating Figure 2: Green Cover Distribution...")
    
    fig, ax = plt.subplots(figsize=FIGSIZE_16_9, dpi=DPI)
    
    # Normalize NDVI
    ndvi_norm = normalize_array(ndvi_data, vmin=-0.2, vmax=0.8)
    
    # Plot NDVI with green colormap
    im = ax.imshow(
        ndvi_norm,
        cmap=CMAP_NDVI,
        alpha=0.85,
        origin='upper',
        extent=[DELHI_BOUNDS['west'], DELHI_BOUNDS['east'], 
                DELHI_BOUNDS['south'], DELHI_BOUNDS['north']]
    )
    
    # Add subtle basemap
    try:
        ctx.add_basemap(
            ax,
            crs='EPSG:4326',
            source=ctx.providers.CartoDB.Positron,
            zoom=11,
            alpha=0.2
        )
    except Exception:
        ax.set_facecolor(BACKGROUND_COLOR)
    
    ax.set_xlim(DELHI_BOUNDS['west'], DELHI_BOUNDS['east'])
    ax.set_ylim(DELHI_BOUNDS['south'], DELHI_BOUNDS['north'])
    ax.axis('off')
    fig.patch.set_facecolor('white')
    
    # Title
    ax.text(
        0.5, 0.95,
        'Vegetation Coverage (NDVI)',
        ha='center', va='top',
        transform=ax.transAxes,
        fontsize=18, weight='bold',
        color=TEXT_COLOR
    )
    
    # Colorbar
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('NDVI Index', fontsize=12, color=TEXT_COLOR)
    cbar.ax.tick_params(labelsize=10, colors=TEXT_COLOR)
    
    save_figure(fig, '02_green_cover_distribution.png')
    plt.close(fig)


def figure_3_heat_vs_green_overlay(ndvi_data, lst_data, profile):
    """
    Figure 3: Heat vs Green Overlay
    
    NDVI (green) + LST (red/orange) with balanced alpha blending.
    Purpose: "Hot areas often coincide with low greenery"
    """
    print("📊 Generating Figure 3: Heat vs Green Overlay...")
    
    fig, ax = plt.subplots(figsize=FIGSIZE_16_9, dpi=DPI)
    
    # Normalize inputs
    ndvi_norm = normalize_array(ndvi_data, vmin=-0.2, vmax=0.8)
    lst_norm = normalize_array(lst_data, vmin=22, vmax=32)
    
    # Create composite RGB image
    # Red channel = LST (heat), Green channel = NDVI, Blue channel = neutral
    composite = np.stack([
        lst_norm,      # Red = heat
        ndvi_norm,     # Green = vegetation
        0.5 * np.ones_like(lst_norm)  # Blue = neutral
    ], axis=-1)
    
    # Plot composite
    ax.imshow(
        composite, 
        alpha=0.8, 
        origin='upper',
        extent=[DELHI_BOUNDS['west'], DELHI_BOUNDS['east'], 
                DELHI_BOUNDS['south'], DELHI_BOUNDS['north']]
    )
    
    # Add basemap
    try:
        ctx.add_basemap(
            ax,
            crs='EPSG:4326',
            source=ctx.providers.CartoDB.Positron,
            zoom=11,
            alpha=0.25
        )
    except Exception:
        ax.set_facecolor(BACKGROUND_COLOR)
    
    ax.set_xlim(DELHI_BOUNDS['west'], DELHI_BOUNDS['east'])
    ax.set_ylim(DELHI_BOUNDS['south'], DELHI_BOUNDS['north'])
    ax.axis('off')
    fig.patch.set_facecolor('white')
    
    # Title
    ax.text(
        0.5, 0.95,
        'Heat (Red) vs Vegetation (Green) Overlay',
        ha='center', va='top',
        transform=ax.transAxes,
        fontsize=18, weight='bold',
        color=TEXT_COLOR
    )
    
    # Legend
    heat_patch = mpatches.Patch(color='red', label='High Temperature')
    veg_patch = mpatches.Patch(color='green', label='High Vegetation')
    ax.legend(
        handles=[heat_patch, veg_patch],
        loc='lower right',
        fontsize=11,
        framealpha=0.95
    )
    
    save_figure(fig, '03_heat_vs_green_overlay.png')
    plt.close(fig)


def figure_4_green_deficit_index(ndvi_data, lst_data, profile):
    """
    Figure 4: Green Deficit Index (Derived Layer)
    
    Composite metric: GDI = (heat * 0.6) + ((1 - ndvi) * 0.4)
    Red = high priority, Green = low priority
    Purpose: "A single interpretable planning metric"
    """
    print("📊 Generating Figure 4: Green Deficit Index...")
    
    # Compute GDI
    gdi = compute_green_deficit_index(ndvi_data, lst_data)
    
    fig, ax = plt.subplots(figsize=FIGSIZE_16_9, dpi=DPI)
    
    # Plot GDI with priority colormap
    im = ax.imshow(
        gdi,
        cmap=CMAP_PRIORITY,
        vmin=0, vmax=1,
        alpha=0.85,
        origin='upper',
        extent=[DELHI_BOUNDS['west'], DELHI_BOUNDS['east'], 
                DELHI_BOUNDS['south'], DELHI_BOUNDS['north']]
    )
    
    # Add basemap
    try:
        ctx.add_basemap(
            ax,
            crs='EPSG:4326',
            source=ctx.providers.CartoDB.Positron,
            zoom=11,
            alpha=0.25
        )
    except Exception:
        ax.set_facecolor(BACKGROUND_COLOR)
    
    ax.set_xlim(DELHI_BOUNDS['west'], DELHI_BOUNDS['east'])
    ax.set_ylim(DELHI_BOUNDS['south'], DELHI_BOUNDS['north'])
    ax.axis('off')
    fig.patch.set_facecolor('white')
    
    # Title
    ax.text(
        0.5, 0.95,
        'Green Deficit Index: Planning Priority',
        ha='center', va='top',
        transform=ax.transAxes,
        fontsize=18, weight='bold',
        color=TEXT_COLOR
    )
    
    # Colorbar with semantic labels
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Priority (Low ← → High)', fontsize=12, color=TEXT_COLOR)
    cbar.ax.tick_params(labelsize=10, colors=TEXT_COLOR)
    
    save_figure(fig, '04_green_deficit_index.png')
    plt.close(fig)
    
    return gdi


def figure_5_street_level_priority_map(ndvi_data, lst_data, profile):
    """
    Figure 5: Street-Level Priority Map
    
    Road network overlaid on GDI, colored by mean GDI values.
    Purpose: "We translate satellite data into actionable streets"
    """
    print("📊 Generating Figure 5: Street-Level Priority Map...")
    
    # Compute GDI
    gdi = compute_green_deficit_index(ndvi_data, lst_data)
    
    # Fetch roads
    roads = fetch_roads_delhi()
    
    fig, ax = plt.subplots(figsize=FIGSIZE_16_9, dpi=DPI)
    
    # Plot GDI as background
    im = ax.imshow(
        gdi,
        cmap=CMAP_PRIORITY,
        vmin=0, vmax=1,
        alpha=0.6,
        origin='upper',
        extent=[DELHI_BOUNDS['west'], DELHI_BOUNDS['east'], 
                DELHI_BOUNDS['south'], DELHI_BOUNDS['north']]
    )
    
    # Add basemap
    try:
        ctx.add_basemap(
            ax,
            crs='EPSG:4326',
            source=ctx.providers.CartoDB.Positron,
            zoom=11,
            alpha=0.2
        )
    except Exception:
        pass
    
    # Sample GDI values along roads
    print("  ⏳ Sampling GDI values along road network...")
    roads = sample_raster_along_roads(roads, gdi, profile['transform'])
    
    # Plot roads colored by their mean GDI value
    roads_valid = roads[roads['raster_mean'].notna()].copy()
    if len(roads_valid) > 0:
        roads_valid.plot(
            ax=ax,
            column='raster_mean',
            cmap=CMAP_PRIORITY,
            linewidth=1.5,
            alpha=0.85,
            legend=False
        )
        print(f"  ✓ Plotted {len(roads_valid)} road segments with GDI values")
    else:
        raise RuntimeError("No valid GDI samples obtained for road segments")
    
    ax.set_xlim(DELHI_BOUNDS['west'], DELHI_BOUNDS['east'])
    ax.set_ylim(DELHI_BOUNDS['south'], DELHI_BOUNDS['north'])
    ax.axis('off')
    fig.patch.set_facecolor('white')
    
    # Title
    ax.text(
        0.5, 0.95,
        'Street-Level Intervention Priority',
        ha='center', va='top',
        transform=ax.transAxes,
        fontsize=18, weight='bold',
        color=TEXT_COLOR
    )
    
    # Colorbar
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Priority Index', fontsize=12, color=TEXT_COLOR)
    
    save_figure(fig, '05_street_level_priority_map.png')
    plt.close(fig)


def figure_6_example_green_corridor(ndvi_data, lst_data, profile):
    """
    Figure 6: Example VanSetu Corridor
    
    Highlight a single high-priority corridor; mute everything else.
    Purpose: "This is how intervention would be targeted"
    """
    print("📊 Generating Figure 6: Example VanSetu Corridor...")
    
    # Compute GDI
    gdi = compute_green_deficit_index(ndvi_data, lst_data)
    
    # Create background (muted)
    background = np.ones_like(gdi) * 0.8  # Light gray
    
    # Identify high-priority corridor (top 15% of GDI)
    threshold = np.nanpercentile(gdi, 85)
    corridor_mask = gdi > threshold
    
    # Create emphasized layer
    emphasized = np.where(corridor_mask, gdi, np.nan)
    
    fig, ax = plt.subplots(figsize=FIGSIZE_16_9, dpi=DPI)
    
    # Plot muted background
    ax.imshow(
        background, 
        cmap='Greys', 
        vmin=0, vmax=1, 
        alpha=0.5, 
        origin='upper',
        extent=[DELHI_BOUNDS['west'], DELHI_BOUNDS['east'], 
                DELHI_BOUNDS['south'], DELHI_BOUNDS['north']]
    )
    
    # Plot high-priority corridor
    im = ax.imshow(
        emphasized, 
        cmap=CMAP_PRIORITY, 
        vmin=0, vmax=1, 
        alpha=0.9, 
        origin='upper',
        extent=[DELHI_BOUNDS['west'], DELHI_BOUNDS['east'], 
                DELHI_BOUNDS['south'], DELHI_BOUNDS['north']]
    )
    
    # Add basemap
    try:
        ctx.add_basemap(
            ax,
            crs='EPSG:4326',
            source=ctx.providers.CartoDB.Positron,
            zoom=11,
            alpha=0.15
        )
    except Exception:
        pass
    
    ax.set_xlim(DELHI_BOUNDS['west'], DELHI_BOUNDS['east'])
    ax.set_ylim(DELHI_BOUNDS['south'], DELHI_BOUNDS['north'])
    ax.axis('off')
    fig.patch.set_facecolor('white')
    
    # Title
    ax.text(
        0.5, 0.95,
        'High-Priority VanSetu Corridor Opportunity',
        ha='center', va='top',
        transform=ax.transAxes,
        fontsize=18, weight='bold',
        color=TEXT_COLOR
    )
    
    # Annotation
    ax.text(
        0.05, 0.05,
        'Highlighted zones represent highest intervention priority',
        ha='left', va='bottom',
        transform=ax.transAxes,
        fontsize=11,
        style='italic',
        color='#666666',
        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8)
    )
    
    # Colorbar
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Priority Index', fontsize=12, color=TEXT_COLOR)
    
    save_figure(fig, '06_example_green_corridor.png')
    plt.close(fig)


def figure_7_continuous_map_story(ndvi_data, lst_data, profile):
    """
    Figure 7: Continuous Map Story — Three Separate Panel Images
    
    Generates three separate PNG files, each cropped to map content only:
    - 07a_city_today.png — Clean basemap with road network
    - 07b_priority_zones.png — GDI priority overlay  
    - 07c_green_corridors.png — Proposed VanSetu corridors
    
    All panels share identical geographic extent for visual continuity.
    No titles, labels, padding, or text — pure map content only.
    """
    print("📊 Generating Figure 7: Continuous Map Story (3 separate panels)...")
    
    # Compute Green Deficit Index
    gdi = compute_green_deficit_index(ndvi_data, lst_data)
    
    # Fetch road network
    print("  ⏳ Fetching road network...")
    roads = fetch_roads_delhi()
    
    # Sample GDI values along roads for corridor selection
    print("  ⏳ Sampling GDI along roads for corridor identification...")
    roads_sampled = sample_raster_along_roads(roads.copy(), gdi, profile['transform'])
    
    # Filter to roads with valid GDI samples
    roads_valid = roads_sampled[roads_sampled['raster_mean'].notna()].copy()
    
    if len(roads_valid) > 0:
        gdi_threshold = roads_valid['raster_mean'].quantile(0.85)
        corridor_display = roads_valid[roads_valid['raster_mean'] >= gdi_threshold].copy()
        print(f"  ✓ Identified {len(corridor_display)} high-priority corridor segments")
    else:
        corridor_display = gpd.GeoDataFrame(geometry=[], crs='EPSG:4326')
    
    # Shared extent
    extent = [DELHI_BOUNDS['west'], DELHI_BOUNDS['east'], 
              DELHI_BOUNDS['south'], DELHI_BOUNDS['north']]
    
    # -------------------------------------------------------------------------
    # PANEL 1: "The City As It Is" — Roads only
    # -------------------------------------------------------------------------
    print("  📍 Generating Panel 1: The City Today...")
    fig1, ax1 = plt.subplots(figsize=FIGSIZE_16_9, dpi=DPI)
    
    # White/light gray background
    ax1.set_facecolor('#f0f0f0')
    
    # Road network
    if len(roads) > 0:
        roads.plot(ax=ax1, color='#4a4a4a', linewidth=0.6, alpha=0.7)
    
    ax1.set_xlim(extent[0], extent[1])
    ax1.set_ylim(extent[2], extent[3])
    ax1.axis('off')
    fig1.patch.set_facecolor('#f0f0f0')
    
    # Save tightly cropped
    filepath1 = os.path.join(OUTPUT_DIR, '07a_city_today.png')
    fig1.savefig(filepath1, dpi=DPI, bbox_inches='tight', pad_inches=0)
    print(f"  ✓ Saved: {filepath1}")
    plt.close(fig1)
    
    # -------------------------------------------------------------------------
    # PANEL 2: "Where the City Suffers" — GDI overlay
    # -------------------------------------------------------------------------
    print("  📍 Generating Panel 2: Priority Zones...")
    fig2, ax2 = plt.subplots(figsize=FIGSIZE_16_9, dpi=DPI)
    
    # GDI overlay
    ax2.imshow(gdi, cmap=CMAP_PRIORITY, vmin=0, vmax=1, alpha=0.85, origin='upper', extent=extent)
    
    # Faint roads
    if len(roads) > 0:
        roads.plot(ax=ax2, color='#333333', linewidth=0.3, alpha=0.25)
    
    ax2.set_xlim(extent[0], extent[1])
    ax2.set_ylim(extent[2], extent[3])
    ax2.axis('off')
    fig2.patch.set_facecolor('white')
    
    filepath2 = os.path.join(OUTPUT_DIR, '07b_priority_zones.png')
    fig2.savefig(filepath2, dpi=DPI, bbox_inches='tight', pad_inches=0)
    print(f"  ✓ Saved: {filepath2}")
    plt.close(fig2)
    
    # -------------------------------------------------------------------------
    # PANEL 3: "What We Can Do" — VanSetu corridors
    # -------------------------------------------------------------------------
    print("  📍 Generating Panel 3: VanSetu Corridor Vision...")
    fig3, ax3 = plt.subplots(figsize=FIGSIZE_16_9, dpi=DPI)
    
    # Muted GDI background
    ax3.imshow(gdi, cmap='Greys', vmin=0, vmax=1, alpha=0.15, origin='upper', extent=extent)
    
    # Faint roads
    if len(roads) > 0:
        roads.plot(ax=ax3, color='#888888', linewidth=0.3, alpha=0.3)
    
    # VanSetu corridors
    if len(corridor_display) > 0:
        corridor_buffer = corridor_display.copy()
        corridor_buffer['geometry'] = corridor_buffer.geometry.buffer(0.005)
        corridor_buffer.plot(ax=ax3, color='#2ecc71', alpha=0.3, edgecolor='none')
        corridor_display.plot(ax=ax3, color='#27ae60', linewidth=2.5, alpha=0.9)
        print(f"  ✓ Rendered {len(corridor_display)} VanSetu corridor segments")
    
    ax3.set_xlim(extent[0], extent[1])
    ax3.set_ylim(extent[2], extent[3])
    ax3.axis('off')
    fig3.patch.set_facecolor('white')
    
    filepath3 = os.path.join(OUTPUT_DIR, '07c_green_corridors.png')
    fig3.savefig(filepath3, dpi=DPI, bbox_inches='tight', pad_inches=0)
    print(f"  ✓ Saved: {filepath3}")
    plt.close(fig3)
    
    print("  ✓ Three-panel narrative visualization complete (3 separate files)")


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def validate_raster_data(data, name, expected_range=None):
    """
    Validate raster data integrity.
    
    Args:
        data (np.ndarray): Raster data array
        name (str): Dataset name for error messages
        expected_range (tuple): Optional (min, max) expected value range
        
    Raises:
        ValueError: If validation fails
    """
    # Check for valid data
    if data is None or data.size == 0:
        raise ValueError(f"{name}: Empty or None data array")
    
    # Check for all NaN
    valid_count = np.sum(np.isfinite(data))
    if valid_count == 0:
        raise ValueError(f"{name}: All values are NaN/invalid")
    
    # Check data range
    data_min = np.nanmin(data)
    data_max = np.nanmax(data)
    print(f"  ✓ {name}: shape={data.shape}, range=[{data_min:.2f}, {data_max:.2f}], valid_pixels={valid_count}")
    
    if expected_range:
        if data_max < expected_range[0] or data_min > expected_range[1]:
            print(f"    ⚠ Warning: Data range [{data_min:.2f}, {data_max:.2f}] outside expected [{expected_range[0]}, {expected_range[1]}]")


def validate_geodataframe(gdf, name, min_features=1):
    """
    Validate GeoDataFrame integrity.
    
    Args:
        gdf (GeoDataFrame): GeoDataFrame to validate
        name (str): Dataset name for error messages
        min_features (int): Minimum required features
        
    Raises:
        ValueError: If validation fails
    """
    if gdf is None:
        raise ValueError(f"{name}: GeoDataFrame is None")
    
    if len(gdf) < min_features:
        raise ValueError(f"{name}: Expected at least {min_features} features, got {len(gdf)}")
    
    # Check for valid geometries
    invalid_geom_count = gdf.geometry.isna().sum() + (~gdf.geometry.is_valid).sum()
    if invalid_geom_count > 0:
        print(f"    ⚠ Warning: {invalid_geom_count} invalid geometries in {name}")
    
    print(f"  ✓ {name}: {len(gdf)} features, CRS={gdf.crs}")


def run_preflight_checks():
    """
    Run preflight checks to ensure all dependencies and data files are available.
    
    Raises:
        RuntimeError: If any check fails
    """
    print("\n🔍 Running preflight checks...")
    
    # Check required files exist
    for filepath, description in [(NDVI_PATH, "NDVI GeoTIFF"), (LST_PATH, "LST GeoTIFF")]:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"{description} not found: {filepath}")
        print(f"  ✓ Found: {filepath}")
    
    # Test OSMnx connectivity with a small query
    print("  ⏳ Testing OSMnx connectivity...")
    try:
        # Small test query
        test_bbox = (77.0, 28.5, 77.1, 28.6)  # Small area in Delhi
        test_tags = {'highway': 'primary'}
        test_result = ox.features_from_bbox(bbox=test_bbox, tags=test_tags)
        print(f"  ✓ OSMnx connection OK (test returned {len(test_result)} features)")
    except Exception as e:
        raise RuntimeError(f"OSMnx connectivity test failed: {e}")
    
    print("✓ All preflight checks passed!\n")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def print_usage():
    """Print command-line usage information."""
    usage = """
Usage: python main.py [OPTIONS] [FIGURES...]

Generate VanSetu corridor visualizations for pitch deck.

FIGURES:
  Specify which figures to generate (1-7). If none specified, generates all.
  
  1  City Heat Context (LST heatmap)
  2  Green Cover Distribution (NDVI)
  3  Heat vs Green Overlay (composite)
  4  Green Deficit Index (derived metric)
  5  Street-Level Priority Map (roads + GDI)
  6  Example VanSetu Corridor (highlighted priority zones)
  7  Continuous Map Story (3-panel narrative: city → problem → solution)

OPTIONS:
  -h, --help     Show this help message
  --skip-osm     Skip OSMnx preflight check (faster startup)
  --list         List available figures and exit

EXAMPLES:
  python main.py              # Generate all 7 figures
  python main.py 1 2 3        # Generate only figures 1, 2, and 3
  python main.py 7            # Generate only the 3-panel narrative
  python main.py 4 5 6        # Generate figures 4, 5, and 6
  python main.py --skip-osm 1 2 3 4  # Skip OSM check, generate 1-4
"""
    print(usage)


def parse_arguments():
    """
    Parse command-line arguments.
    
    Returns:
        figures (list): List of figure numbers to generate (1-6)
        skip_osm (bool): Whether to skip OSMnx preflight check
    """
    args = sys.argv[1:]
    
    # Check for help
    if '-h' in args or '--help' in args:
        print_usage()
        sys.exit(0)
    
    # Check for list
    if '--list' in args:
        print("\nAvailable figures:")
        print("  1: City Heat Context")
        print("  2: Green Cover Distribution")
        print("  3: Heat vs Green Overlay")
        print("  4: Green Deficit Index")
        print("  5: Street-Level Priority Map")
        print("  6: Example VanSetu Corridor")
        print("  7: Continuous Map Story (3-panel narrative)")
        sys.exit(0)
    
    # Check for skip-osm flag
    skip_osm = '--skip-osm' in args
    if skip_osm:
        args.remove('--skip-osm')
    
    # Parse figure numbers
    figures = []
    for arg in args:
        try:
            fig_num = int(arg)
            if 1 <= fig_num <= 7:
                figures.append(fig_num)
            else:
                print(f"⚠ Invalid figure number: {arg} (must be 1-7)")
        except ValueError:
            print(f"⚠ Unknown argument: {arg}")
    
    # Default to all figures if none specified
    if not figures:
        figures = [1, 2, 3, 4, 5, 6, 7]
    
    return sorted(set(figures)), skip_osm


def main():
    """
    Main execution function.
    Orchestrates data loading, validation, and figure generation.
    """
    # Parse command-line arguments
    figures_to_generate, skip_osm = parse_arguments()
    
    print("=" * 80)
    print("VanSetu Platform — Visualization Generator")
    print("=" * 80)
    print(f"\nFigures to generate: {figures_to_generate}")
    
    # Setup
    ensure_output_dir()
    
    # Run preflight checks (optionally skip OSM)
    if skip_osm:
        print("\n🔍 Running preflight checks (OSM skipped)...")
        for filepath, description in [(NDVI_PATH, "NDVI GeoTIFF"), (LST_PATH, "LST GeoTIFF")]:
            if not os.path.exists(filepath):
                raise FileNotFoundError(f"{description} not found: {filepath}")
            print(f"  ✓ Found: {filepath}")
        print("✓ Preflight checks passed!\n")
    else:
        run_preflight_checks()
    
    # Load data
    print("📂 Loading GeoTIFFs...")
    ndvi_data, ndvi_profile = load_geotiff(NDVI_PATH)
    lst_data_orig, lst_profile = load_geotiff(LST_PATH)
    
    # Validate loaded data
    print("\n🔍 Validating raster data...")
    validate_raster_data(ndvi_data, "NDVI", expected_range=(-0.5, 1.0))
    validate_raster_data(lst_data_orig, "LST (original)", expected_range=(15, 50))
    
    # Resample LST to match NDVI resolution (LST is coarser, so upsample)
    print("\n⚙️  Resampling LST to match NDVI resolution...")
    lst_data = resample_raster_to_match(lst_data_orig, lst_profile, ndvi_data, ndvi_profile)
    print(f"  ✓ LST resampled from {lst_data_orig.shape} to {lst_data.shape}")
    validate_raster_data(lst_data, "LST (resampled)", expected_range=(15, 50))
    
    # Use NDVI profile as reference (both now match)
    profile = ndvi_profile
    
    # Generate selected figures
    print("\n" + "=" * 80)
    print("GENERATING VISUALIZATIONS")
    print("=" * 80 + "\n")
    
    # Map figure numbers to generator functions
    figure_generators = {
        1: lambda: figure_1_city_heat_context(lst_data, profile),
        2: lambda: figure_2_green_cover_distribution(ndvi_data, profile),
        3: lambda: figure_3_heat_vs_green_overlay(ndvi_data, lst_data, profile),
        4: lambda: figure_4_green_deficit_index(ndvi_data, lst_data, profile),
        5: lambda: figure_5_street_level_priority_map(ndvi_data, lst_data, profile),
        6: lambda: figure_6_example_green_corridor(ndvi_data, lst_data, profile),
        7: lambda: figure_7_continuous_map_story(ndvi_data, lst_data, profile),
    }
    
    # Generate each selected figure
    for fig_num in figures_to_generate:
        figure_generators[fig_num]()
    
    # Summary
    print("\n" + "=" * 80)
    print("✅ COMPLETE!")
    print("=" * 80)
    print(f"\nFigures saved to: {OUTPUT_DIR}")
    print("Files in output directory:")
    for filename in sorted(os.listdir(OUTPUT_DIR)):
        filepath = os.path.join(OUTPUT_DIR, filename)
        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        print(f"  • {filename} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
