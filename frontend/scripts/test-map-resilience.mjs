import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const frontendDir = path.resolve(__dirname, '..');

console.log('--- Van Setu Map White Patch Resilience Regression Test ---');

// 1. Check Map.jsx
const mapJsxPath = path.join(frontendDir, 'src/components/Map.jsx');
const mapJsx = fs.readFileSync(mapJsxPath, 'utf8');

const checks = [
  {
    name: 'ResizeObserver integration in MapController',
    pass: mapJsx.includes('new ResizeObserver') && mapJsx.includes('invalidateSize'),
  },
  {
    name: 'Immediate and staggered rAF size invalidation on mount',
    pass: mapJsx.includes('requestAnimationFrame(invalidate)') && mapJsx.includes('setTimeout(invalidate, 50)'),
  },
  {
    name: 'TileLayer keepBuffer buffer optimization',
    pass: mapJsx.includes('keepBuffer={4}'),
  },
  {
    name: 'TileLayer updateWhenIdle disabled for continuous panning coverage',
    pass: mapJsx.includes('updateWhenIdle={false}'),
  },
  {
    name: 'TileLayer graceful tileerror event handlers',
    pass: mapJsx.includes('tileerror:'),
  },
];

// 2. Check Map.css
const mapCssPath = path.join(frontendDir, 'src/components/Map.css');
const mapCss = fs.readFileSync(mapCssPath, 'utf8');

const cssChecks = [
  {
    name: 'Leaflet container dark background override (#07101f)',
    pass: mapCss.includes('.map-container .leaflet-container') && mapCss.includes('background: #07101f !important;'),
  },
  {
    name: 'Leaflet container 100% width & height enforcement',
    pass: mapCss.includes('width: 100% !important;') && mapCss.includes('height: 100% !important;'),
  },
];

let failed = 0;
for (const c of [...checks, ...cssChecks]) {
  if (c.pass) {
    console.log(`  ✅ [PASS] ${c.name}`);
  } else {
    console.error(`  ❌ [FAIL] ${c.name}`);
    failed++;
  }
}

if (failed > 0) {
  console.error(`\nRegression test failed with ${failed} failure(s).`);
  process.exit(1);
} else {
  console.log('\nAll map resilience static regression tests passed successfully!');
  process.exit(0);
}
