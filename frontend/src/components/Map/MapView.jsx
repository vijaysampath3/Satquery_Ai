import React, { useEffect, useRef, useState } from 'react';
import { Plus, Minus, RotateCcw, Compass, Eye, Globe } from 'lucide-react';
import { mapService, DEFAULT_CAMERA } from '../../services/mapService';

export default function MapView({ selectedLayer, selectedProjection }) {
  const containerRef = useRef(null);
  const [hudState, setHudState] = useState({
    lng: DEFAULT_CAMERA.center[0],
    lat: DEFAULT_CAMERA.center[1],
    zoom: DEFAULT_CAMERA.zoom,
    pitch: DEFAULT_CAMERA.pitch,
    bearing: DEFAULT_CAMERA.bearing,
  });

  // Initialize MapLibre GL map instance
  useEffect(() => {
    if (!containerRef.current) return;

    mapService.initMap(containerRef.current, {
      baseStyle: selectedLayer,
      projection: selectedProjection,
      center: DEFAULT_CAMERA.center,
      zoom: DEFAULT_CAMERA.zoom,
      pitch: DEFAULT_CAMERA.pitch,
      bearing: DEFAULT_CAMERA.bearing,
    });

    const unsubscribe = mapService.onMove((state) => {
      setHudState(state);
    });

    return () => {
      unsubscribe();
      mapService.destroyMap();
    };
  }, []);

  // React to Base Map Style changes
  useEffect(() => {
    if (selectedLayer) {
      mapService.setBaseStyle(selectedLayer);
    }
  }, [selectedLayer]);

  // React to Map Projection changes (3D Globe vs 2D Mercator)
  useEffect(() => {
    if (selectedProjection) {
      mapService.applyProjection(selectedProjection);
    }
  }, [selectedProjection]);

  const handleZoomIn = () => mapService.zoomIn();
  const handleZoomOut = () => mapService.zoomOut();
  const handleReset = () => mapService.resetView();

  const formattedLat = `${Math.abs(hudState.lat).toFixed(4)}° ${hudState.lat >= 0 ? 'N' : 'S'}`;
  const formattedLng = `${Math.abs(hudState.lng).toFixed(4)}° ${hudState.lng >= 0 ? 'E' : 'W'}`;

  return (
    <div className="map-view-container map-space-bg">
      {/* Real MapLibre 3D Globe Canvas Container */}
      <div ref={containerRef} className="map-canvas-root" />

      {/* Atmospheric Starfield Space Glow Overlay */}
      <div className="space-atmosphere-overlay" />

      {/* Active Coordinates HUD (Top Center) */}
      <div className="map-coords-hud">
        <div className="hud-metric">
          <span className="hud-metric-label">CENTER</span>
          <span className="hud-metric-val mono">{formattedLat}, {formattedLng}</span>
        </div>
        <div className="hud-divider" />
        <div className="hud-metric">
          <span className="hud-metric-label">ZOOM</span>
          <span className="hud-metric-val mono">{hudState.zoom}x</span>
        </div>
        <div className="hud-divider" />
        <div className="hud-metric">
          <span className="hud-metric-label">PITCH</span>
          <span className="hud-metric-val mono">{hudState.pitch}°</span>
        </div>
        <div className="hud-divider" />
        <div className="hud-metric">
          <span className="hud-metric-label">PROJECTION</span>
          <span className="hud-metric-val mono">
            {selectedProjection === 'globe-3d' || selectedProjection === 'globe' ? '3D GLOBE' : selectedProjection.toUpperCase()}
          </span>
        </div>
      </div>

      {/* Compass Indicator (Top Right) */}
      <div
        className="map-compass-box"
        style={{ transform: `rotate(${-hudState.bearing}deg)` }}
        title={`Orientation: ${hudState.bearing}°`}
      >
        <Compass size={22} className="compass-icon" />
        <span className="compass-north">N</span>
      </div>

      {/* Camera Navigation Controls (Right Side Bar) */}
      <div className="map-zoom-controls">
        <button className="map-zoom-btn" onClick={handleZoomIn} title="Zoom In (+)">
          <Plus size={16} />
        </button>
        <div className="zoom-level-text mono">{hudState.zoom}</div>
        <button className="map-zoom-btn" onClick={handleZoomOut} title="Zoom Out (-)">
          <Minus size={16} />
        </button>
        <button className="map-zoom-btn reset-btn" onClick={handleReset} title="Reset to Home View">
          <RotateCcw size={14} />
        </button>
      </div>

      {/* Scale Bar & Metadata (Bottom Left) */}
      <div className="map-scale-bar-box">
        <div className="scale-line-wrapper">
          <div className="scale-line" />
          <span className="scale-text mono">
            {hudState.zoom > 10 ? '2 km / 1.2 mi' : hudState.zoom > 6 ? '100 km / 62 mi' : '1000 km / 620 mi'}
          </span>
        </div>
        <div className="map-layer-tag">
          <Eye size={11} /> Base: {selectedLayer}
        </div>
      </div>
    </div>
  );
}
