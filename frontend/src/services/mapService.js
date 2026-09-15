/**
 * SatQuery AI — Map Service & Camera Controller (3D Spherical Globe Engine)
 *
 * Provides a clean, decoupled abstraction over MapLibre GL JS for:
 * - 3D Spherical Globe & 2D Mercator projection toggling
 * - Smooth camera movements (flyTo, setCenter, setZoom, resetView)
 * - Base map layer switching (NatGeo 3D Globe, Esri Satellite, World Topo, Carto Dark, OSM)
 * - Automatic Lat/Lon graticule lines & atmospheric space rendering
 * - Prepared layer handlers for raster overlays, GeoJSON AOI polygons, and AI masks
 */

import * as maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

const MapCtor = maplibregl.Map || maplibregl;

// Satellite & Base Map Styles
export const MAP_BASE_STYLES = {
  'natgeo-globe': {
    name: 'Natural Earth 3D Globe',
    version: 8,
    sources: {
      'natgeo-source': {
        type: 'raster',
        tiles: [
          'https://server.arcgisonline.com/ArcGIS/rest/services/NatGeo_World_Map/MapServer/tile/{z}/{y}/{x}',
        ],
        tileSize: 256,
        attribution: 'Natural Earth Data | NOAA/NSIDC | Esri | GEBCO | IHO',
      },
    },
    layers: [
      {
        id: 'natgeo-layer',
        type: 'raster',
        source: 'natgeo-source',
        minzoom: 0,
        maxzoom: 16,
      },
    ],
  },
  'esri-satellite': {
    name: 'Esri World Imagery (Satellite)',
    version: 8,
    sources: {
      'esri-satellite-source': {
        type: 'raster',
        tiles: [
          'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        ],
        tileSize: 256,
        attribution: 'Tiles &copy; Esri &mdash; Source: Esri, Maxar, GeoEye, Earthstar Geographics',
      },
    },
    layers: [
      {
        id: 'esri-satellite-layer',
        type: 'raster',
        source: 'esri-satellite-source',
        minzoom: 0,
        maxzoom: 19,
      },
    ],
  },
  'world-topo': {
    name: 'Esri World Topographic',
    version: 8,
    sources: {
      'world-topo-source': {
        type: 'raster',
        tiles: [
          'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
        ],
        tileSize: 256,
        attribution: 'Esri Topographic Base',
      },
    },
    layers: [
      {
        id: 'world-topo-layer',
        type: 'raster',
        source: 'world-topo-source',
        minzoom: 0,
        maxzoom: 19,
      },
    ],
  },
  'carto-dark': {
    name: 'CartoDB Dark Vector',
    version: 8,
    sources: {
      'carto-dark-source': {
        type: 'raster',
        tiles: [
          'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
          'https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
          'https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
        ],
        tileSize: 256,
        attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
      },
    },
    layers: [
      {
        id: 'carto-dark-layer',
        type: 'raster',
        source: 'carto-dark-source',
        minzoom: 0,
        maxzoom: 19,
      },
    ],
  },
  'osm-standard': {
    name: 'OpenStreetMap Standard',
    version: 8,
    sources: {
      'osm-standard-source': {
        type: 'raster',
        tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
        tileSize: 256,
        attribution: '&copy; OpenStreetMap contributors',
      },
    },
    layers: [
      {
        id: 'osm-standard-layer',
        type: 'raster',
        source: 'osm-standard-source',
        minzoom: 0,
        maxzoom: 19,
      },
    ],
  },
};

// Default camera focusing on South Asia / Indian Ocean sphere (exact reference image framing)
export const DEFAULT_CAMERA = {
  center: [78.0, 20.0], // [lng, lat]
  zoom: 1.8,
  pitch: 0,
  bearing: 0,
};

/**
 * Generate 15-degree Lat/Lon Graticule Lines GeoJSON
 */
function createGraticuleGeoJSON() {
  const features = [];

  // Parallels (Latitudes every 15 degrees)
  for (let lat = -75; lat <= 75; lat += 15) {
    const coords = [];
    for (let lng = -180; lng <= 180; lng += 5) {
      coords.push([lng, lat]);
    }
    features.push({
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: coords },
      properties: {
        isEquator: lat === 0,
        isTropic: Math.abs(lat) === 30,
        label: lat === 0 ? '0° Equator' : `${Math.abs(lat)}° ${lat > 0 ? 'N' : 'S'}`,
      },
    });
  }

  // Meridians (Longitudes every 15 degrees)
  for (let lng = -180; lng <= 180; lng += 15) {
    const coords = [];
    for (let lat = -80; lat <= 80; lat += 5) {
      coords.push([lng, lat]);
    }
    features.push({
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: coords },
      properties: {
        isPrime: lng === 0,
        label: `${Math.abs(lng)}° ${lng >= 0 ? 'E' : 'W'}`,
      },
    });
  }

  return { type: 'FeatureCollection', features };
}

class MapService {
  constructor() {
    this.map = null;
    this.activeProjection = 'globe';
    this.activeBaseStyle = 'natgeo-globe';
    this.moveListeners = new Set();
  }

  /**
   * Initialize MapLibre GL 3D Globe instance
   */
  initMap(container, options = {}) {
    if (this.map) {
      this.destroyMap();
    }

    const styleKey = options.baseStyle || this.activeBaseStyle;
    const baseStyle = MAP_BASE_STYLES[styleKey] || MAP_BASE_STYLES['natgeo-globe'];

    const map = new MapCtor({
      container,
      style: baseStyle,
      center: options.center || DEFAULT_CAMERA.center,
      zoom: options.zoom || DEFAULT_CAMERA.zoom,
      pitch: options.pitch || DEFAULT_CAMERA.pitch,
      bearing: options.bearing || DEFAULT_CAMERA.bearing,
      projection: 'globe', // Native 3D Globe Projection
      canvasContextAttributes: { antialias: true, alpha: true },
    });

    this.map = map;
    this.activeBaseStyle = styleKey;

    map.on('load', () => {
      this.applyProjection(options.projection || 'globe');
      this.setupGraticule();
      this.setupAtmosphere();
      map.resize();
    });

    // Listen for map camera movements to update HUD subscribers
    map.on('move', () => {
      const center = map.getCenter();
      const zoom = map.getZoom();
      const pitch = map.getPitch();
      const bearing = map.getBearing();

      const state = {
        lng: center.lng,
        lat: center.lat,
        zoom: Math.round(zoom * 10) / 10,
        pitch: Math.round(pitch),
        bearing: Math.round(bearing),
      };

      this.moveListeners.forEach((fn) => fn(state));
    });

    return map;
  }

  /**
   * Add Lat/Lon Graticule Lines Overlay on the Globe
   */
  setupGraticule() {
    if (!this.map) return;
    try {
      if (this.map.getSource('graticule-source')) return;

      this.map.addSource('graticule-source', {
        type: 'geojson',
        data: createGraticuleGeoJSON(),
      });

      this.map.addLayer({
        id: 'graticule-line-layer',
        type: 'line',
        source: 'graticule-source',
        paint: {
          'line-color': 'rgba(60, 120, 180, 0.45)',
          'line-width': [
            'case',
            ['boolean', ['get', 'isEquator'], false],
            1.8,
            1.0,
          ],
          'line-dasharray': [3, 3],
        },
      });
    } catch (e) {
      console.warn('Graticule setup error:', e);
    }
  }

  /**
   * Setup 3D space atmosphere glow for dark globe view
   */
  setupAtmosphere() {
    if (!this.map) return;
    try {
      if (typeof this.map.setSky === 'function') {
        this.map.setSky({
          'sky-color': '#030712',
          'horizon-color': '#0f172a',
          'fog-color': '#020408',
        });
      }
    } catch (e) {
      // Ignore if setSky is not supported
    }
  }

  /**
   * Toggle projection mode between 3D Globe and 2D Mercator
   */
  applyProjection(projectionType = 'globe') {
    if (!this.map) return;
    const proj = projectionType === 'mercator' || projectionType === 'epsg-3857' ? 'mercator' : 'globe';
    this.activeProjection = proj;

    try {
      if (typeof this.map.setProjection === 'function') {
        this.map.setProjection({ type: proj });
      }
    } catch (e) {
      console.warn('Projection change warning:', e);
    }
  }

  /**
   * Switch Base Map Style & Re-apply Graticule
   */
  setBaseStyle(styleId) {
    if (!this.map || !MAP_BASE_STYLES[styleId]) return;
    this.activeBaseStyle = styleId;
    const newStyle = MAP_BASE_STYLES[styleId];

    const center = this.map.getCenter();
    const zoom = this.map.getZoom();
    const pitch = this.map.getPitch();
    const bearing = this.map.getBearing();

    this.map.setStyle(newStyle);

    this.map.once('style.load', () => {
      this.applyProjection(this.activeProjection);
      this.setupGraticule();
      this.setupAtmosphere();
      this.map.jumpTo({ center, zoom, pitch, bearing });
    });
  }

  // ── Camera Navigation API ──

  flyTo({ center, zoom = 4.0, pitch = 0, bearing = 0, speed = 1.2 }) {
    if (!this.map) return;
    this.map.flyTo({
      center,
      zoom,
      pitch,
      bearing,
      speed,
      curve: 1.4,
      essential: true,
    });
  }

  setCenter(center) {
    if (!this.map) return;
    this.map.setCenter(center);
  }

  setZoom(zoom) {
    if (!this.map) return;
    this.map.setZoom(zoom);
  }

  zoomIn() {
    if (!this.map) return;
    this.map.zoomIn();
  }

  zoomOut() {
    if (!this.map) return;
    this.map.zoomOut();
  }

  resetView() {
    if (!this.map) return;
    this.map.flyTo({
      center: DEFAULT_CAMERA.center,
      zoom: DEFAULT_CAMERA.zoom,
      pitch: DEFAULT_CAMERA.pitch,
      bearing: DEFAULT_CAMERA.bearing,
      speed: 1.2,
      essential: true,
    });
  }

  // ── HUD Event Subscriptions ──

  onMove(callback) {
    this.moveListeners.add(callback);
    return () => this.moveListeners.delete(callback);
  }

  // ── Prepared Layer Extensions for Future Phases ──

  addGeoJSONSourceAndLayer(id, geojson, paintOptions = {}) {
    if (!this.map) return;
    const sourceId = `src-${id}`;
    const layerId = `lyr-${id}`;

    if (this.map.getLayer(layerId)) this.map.removeLayer(layerId);
    if (this.map.getSource(sourceId)) this.map.removeSource(sourceId);

    this.map.addSource(sourceId, {
      type: 'geojson',
      data: geojson,
    });

    this.map.addLayer({
      id: layerId,
      type: paintOptions.type || 'fill',
      source: sourceId,
      paint: paintOptions.paint || {
        'fill-color': '#06b6d4',
        'fill-opacity': 0.35,
        'fill-outline-color': '#38bdf8',
      },
    });
  }

  addRasterOverlay(id, imageUrl, bounds) {
    if (!this.map) return;
    const sourceId = `src-raster-${id}`;
    const layerId = `lyr-raster-${id}`;

    if (this.map.getLayer(layerId)) this.map.removeLayer(layerId);
    if (this.map.getSource(sourceId)) this.map.removeSource(sourceId);

    this.map.addSource(sourceId, {
      type: 'image',
      url: imageUrl,
      coordinates: bounds,
    });

    this.map.addLayer({
      id: layerId,
      type: 'raster',
      source: sourceId,
      paint: {
        'raster-opacity': 0.85,
        'raster-fade-duration': 300,
      },
    });
  }

  destroyMap() {
    if (this.map) {
      this.moveListeners.clear();
      this.map.remove();
      this.map = null;
    }
  }
}

export const mapService = new MapService();
