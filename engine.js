// =====================================================
// VanSetu – NDVI + Heat (Clean MVP Script)
// =====================================================

// ---------- 1) REGION ----------
var region = ee.Geometry.Rectangle([76.80, 28.40, 77.50, 28.90]); // Delhi bbox

// ---------- 2) DATE RANGES ----------
var ndviStart = '2024-11-01';
var ndviEnd   = '2025-02-28';

var lstStart  = '2024-10-01';
var lstEnd    = '2025-03-31';

// ---------- 3) EXPORT CONFIG ----------
var exportFolder = 'GEE_exports';
var ndviFileName = 'delhi_ndvi_10m';
var lstFileName  = 'delhi_lst_modis_daily_celsius';

// ---------- 4) SENTINEL-2 NDVI ----------

// Cloud mask (QA60 – safe with S2_SR_HARMONIZED)
function maskS2(image) {
  var qa = image.select('QA60');
  var cloud = qa.bitwiseAnd(1 << 10).eq(0)
    .and(qa.bitwiseAnd(1 << 11).eq(0));
  return image.updateMask(cloud).divide(10000);
}

var s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterBounds(region)
  .filterDate(ndviStart, ndviEnd)
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 60))
  .map(maskS2)
  .map(function(img) {
    return img.normalizedDifference(['B8', 'B4']).rename('NDVI');
  });

var ndvi = s2.median();

print('Sentinel-2 scenes:', s2.size());

// ---------- 5) MODIS DAILY LST (°C) ----------

var modis = ee.ImageCollection('MODIS/061/MOD11A1')
  .filterBounds(region)
  .filterDate(lstStart, lstEnd)
  .select('LST_Day_1km');

print('MODIS LST scenes:', modis.size());

var lstC = modis
  .mean()
  .multiply(0.02)
  .subtract(273.15)
  .rename('LST_C');

// ---------- 6) VISUALIZATION ----------

Map.centerObject(region, 11);
Map.layers().reset();

// Heat first
Map.addLayer(
  lstC.clip(region),
  {
    min: 22,
    max: 32,
    palette: ['2c7bb6', 'abd9e9', 'ffffbf', 'fdae61', 'd7191c']
  },
  'Land Surface Temperature (°C)'
);

// NDVI toggle
Map.addLayer(
  ndvi.clip(region),
  {
    min: -0.2,
    max: 0.8,
    palette: ['ffffff', 'ffe6a7', '7fc97f', '006837']
  },
  'NDVI (Sentinel-2)',
  false
);

// ---------- 7) EXPORTS ----------

// NDVI (10 m)
Export.image.toDrive({
  image: ndvi.clip(region).toFloat(),
  description: 'Export_Delhi_NDVI_10m',
  folder: exportFolder,
  fileNamePrefix: ndviFileName,
  region: region,
  scale: 10,
  crs: 'EPSG:4326',
  maxPixels: 1e13,
  formatOptions: { cloudOptimized: true }
});

// LST (1 km)
Export.image.toDrive({
  image: lstC.clip(region).toFloat(),
  description: 'Export_Delhi_LST_Celsius',
  folder: exportFolder,
  fileNamePrefix: lstFileName,
  region: region,
  scale: 1000,
  crs: 'EPSG:4326',
  maxPixels: 1e13,
  formatOptions: { cloudOptimized: true }
});

print('Ready. Run exports from the Tasks tab.');
