import React from 'react';
import { Satellite, Upload, Activity, Compass, ShieldCheck } from 'lucide-react';
import MapLayerMenu from './MapLayerMenu';
import ProjectionMenu from './ProjectionMenu';

export default function MapHeader({
  selectedLayer,
  onSelectLayer,
  selectedProjection,
  onSelectProjection,
  systemStatus,
  activeView,
  onToggleViewMode,
}) {
  const isHealthy = systemStatus?.status === 'healthy';

  return (
    <header className="map-header-bar">
      {/* Brand Section */}
      <div className="map-header-brand">
        <div className="map-brand-icon">
          <Satellite size={20} style={{ color: '#818cf8' }} />
        </div>
        <div className="map-brand-text">
          <div className="map-brand-title">
            SatQuery AI <span className="map-brand-badge">MAP WORKSPACE</span>
          </div>
          <div className="map-brand-sub">Spatial Intelligence & Geospatial Analytics</div>
        </div>
      </div>

      {/* Center Selectors */}
      <div className="map-header-controls">
        <MapLayerMenu selectedLayer={selectedLayer} onSelectLayer={onSelectLayer} />
        <ProjectionMenu selectedProjection={selectedProjection} onSelectProjection={onSelectProjection} />
      </div>

      {/* Right Utility Section */}
      <div className="map-header-actions">
        {/* System Health Status */}
        <div className={`map-status-pill ${isHealthy ? 'healthy' : 'offline'}`} title="API Connection Status">
          <span className="status-dot"></span>
          <span className="status-text">{isHealthy ? 'API Connected' : 'Offline'}</span>
        </div>

        {/* View Mode Switcher */}
        <button
          className="mode-switch-btn"
          onClick={onToggleViewMode}
          title="Switch to classic image upload chat workspace"
        >
          <Upload size={14} />
          <span>Upload Analysis Mode</span>
        </button>
      </div>
    </header>
  );
}
