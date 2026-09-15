import React, { useState } from 'react';
import {
  Layers,
  Calendar,
  Cloud,
  Satellite,
  Check,
  ChevronDown,
  ChevronUp,
  Copy,
  Loader2,
  AlertTriangle,
  Database,
  Scissors,
  Sparkles,
  CheckCircle2
} from 'lucide-react';

export default function SceneResults({
  searchResult,
  onSelectScene,
  selectedSceneId,
  onClose,
  accessResult,
  isAccessingScene,
  accessError,
  onClipScene,
  clipResult,
  isClippingScene,
  clipError,
}) {
  const [isMinimized, setIsMinimized] = useState(false);
  const [copiedId, setCopiedId] = useState(null);

  if (!searchResult) return null;

  const { count, sensor, scenes = [], query } = searchResult;

  const handleCopyId = (id) => {
    navigator.clipboard.writeText(id);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className={`floating-panel scene-results-panel ${isMinimized ? 'minimized' : ''}`}>
      {/* Panel Header */}
      <div className="floating-panel-header">
        <div className="panel-title-box">
          <Satellite size={16} className="panel-icon-accent" />
          <span className="panel-title-text">
            Discovered Scenes <span className="scene-count-badge">{count}</span>
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <button
            className="panel-collapse-btn"
            onClick={() => setIsMinimized(!isMinimized)}
            title={isMinimized ? 'Expand Panel' : 'Minimize Panel'}
          >
            {isMinimized ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
          {onClose && (
            <button className="panel-collapse-btn" onClick={onClose} title="Close Results">
              ✕
            </button>
          )}
        </div>
      </div>

      {!isMinimized && (
        <div className="floating-panel-body scene-results-body">
          {/* Query Summary Metadata */}
          <div className="scene-query-summary">
            <span className="summary-item">
              <Layers size={11} /> {sensor === 'SENTINEL-2' ? 'Sentinel-2 L2A' : 'Sentinel-1 GRD'}
            </span>
            <span className="summary-item">
              <Calendar size={11} /> {query?.date_start} {query?.date_end && query?.date_end !== query?.date_start ? `→ ${query.date_end}` : ''}
            </span>
            {sensor === 'SENTINEL-2' && query?.cloud_cover_max !== null && (
              <span className="summary-item">
                <Cloud size={11} /> Cloud &le; {query.cloud_cover_max}%
              </span>
            )}
          </div>

          {/* Phase 3B Authenticated Raster Status Card */}
          {selectedSceneId && (
            <div className="raster-status-card animate-fade-in">
              <div className="status-card-header">
                <div className="status-card-title">
                  <Database size={13} className="text-indigo-400" />
                  <span>Authenticated Raster Access</span>
                </div>
                {isAccessingScene ? (
                  <span className="status-badge accessing">
                    <Loader2 size={11} className="animate-spin" /> ACCESSING SATELLITE DATA
                  </span>
                ) : accessResult ? (
                  <span className="status-badge ready">
                    <Check size={11} /> RASTER READY
                  </span>
                ) : accessError ? (
                  <span className="status-badge failed">
                    <AlertTriangle size={11} /> ACCESS FAILED
                  </span>
                ) : (
                  <span className="status-badge selected">
                    SELECTED
                  </span>
                )}
              </div>

              {/* Status Content */}
              {isAccessingScene && (
                <div className="raster-status-loading">
                  <Loader2 size={18} className="animate-spin text-indigo-400" />
                  <span className="loading-text">Authenticating CDSE credentials & inspecting STAC raster asset...</span>
                </div>
              )}

              {accessError && (
                <div className="raster-status-error">
                  <AlertTriangle size={14} className="error-icon" />
                  <span>{accessError}</span>
                </div>
              )}

              {accessResult && !isAccessingScene && (
                <div className="raster-metadata-grid">
                  <div className="meta-badge-row">
                    <span className="meta-pill asset-key">Asset: {accessResult.asset?.key}</span>
                    <span className="meta-pill crs">CRS: {accessResult.raster?.crs || 'EPSG:4326'}</span>
                    <span className="meta-pill dtype">Dtype: {accessResult.raster?.dtype}</span>
                  </div>

                  <div className="meta-metrics-table">
                    <div className="meta-metric-cell">
                      <span className="metric-label">Dimensions</span>
                      <span className="metric-val mono">{accessResult.raster?.width} &times; {accessResult.raster?.height}</span>
                    </div>
                    <div className="meta-metric-cell">
                      <span className="metric-label">Resolution</span>
                      <span className="metric-val mono">{accessResult.raster?.resolution?.join('m × ') || '10'}m</span>
                    </div>
                    <div className="meta-metric-cell">
                      <span className="metric-label">Bands</span>
                      <span className="metric-val mono">{accessResult.raster?.band_count}</span>
                    </div>
                    <div className="meta-metric-cell">
                      <span className="metric-label">AOI Match</span>
                      <span className="metric-val match-ok">
                        {accessResult.aoi_intersection?.intersects ? 'Intersects ✓' : 'Outside AOI ✕'}
                      </span>
                    </div>
                  </div>

                  {/* Phase 3C Clip Action Button */}
                  {!clipResult && (
                    <button
                      className="clip-aoi-cta-btn"
                      onClick={onClipScene}
                      disabled={isClippingScene}
                    >
                      {isClippingScene ? (
                        <>
                          <Loader2 size={13} className="animate-spin" />
                          <span>CLIPPING AOI & PREPARING BANDS...</span>
                        </>
                      ) : (
                        <>
                          <Scissors size={14} />
                          <span>Clip to AOI & Prepare Bands</span>
                        </>
                      )}
                    </button>
                  )}
                </div>
              )}

              {/* Phase 3C Analysis-Ready Clipped Dataset Display */}
              {clipResult && (
                <div className="clipped-analysis-card animate-fade-in">
                  <div className="clipped-header-row">
                    <span className="status-badge analysis-ready">
                      <Sparkles size={11} /> ANALYSIS READY
                    </span>
                    <span className="clip-dims-text mono">
                      Clipped: {clipResult.output?.width} &times; {clipResult.output?.height} px
                    </span>
                  </div>

                  {/* Prepared Bands Checklist */}
                  <div className="prepared-bands-section">
                    <span className="section-label">Prepared Channels:</span>
                    <div className="bands-chips-grid">
                      {clipResult.bands && Object.entries(clipResult.bands).map(([bName, bInfo]) => {
                        if (!bInfo.available) return null;
                        return (
                          <span key={bName} className="prepared-band-chip">
                            <CheckCircle2 size={11} className="text-emerald-400" />
                            <span>{bName} {bName === 'B02' ? 'Blue' : bName === 'B03' ? 'Green' : bName === 'B04' ? 'Red' : bName === 'B08' ? 'NIR' : ''}</span>
                          </span>
                        );
                      })}
                    </div>
                  </div>

                  {/* AOI Preview Image */}
                  {clipResult.preview_url && (
                    <div className="aoi-clip-preview-box">
                      <img src={clipResult.preview_url} alt="AOI Clip Preview" className="aoi-clip-preview-img" />
                      <div className="preview-footer-row">
                        <span className="preview-type-tag">AOI RGB Preview</span>
                        <span className="preview-bounds-tag mono">
                          {clipResult.aoi?.min_lat?.toFixed(2)}°N, {clipResult.aoi?.min_lon?.toFixed(2)}°E
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {clipError && (
                <div className="raster-status-error">
                  <AlertTriangle size={14} className="error-icon" />
                  <span>{clipError}</span>
                </div>
              )}
            </div>
          )}

          {/* Empty Result Notification */}
          {scenes.length === 0 ? (
            <div className="no-scenes-box">
              <Cloud size={24} style={{ color: 'var(--text-muted)' }} />
              <div className="no-scenes-title">No Scenes Discovered</div>
              <div className="no-scenes-desc">
                No matching {sensor} scenes found for this AOI and date range. Try broadening date bounds or adjusting cloud cover threshold.
              </div>
            </div>
          ) : (
            /* Scene Cards List */
            <div className="scene-cards-list">
              {scenes.map((scene) => {
                const isSelected = selectedSceneId === scene.id;
                const hasThumb = scene.assets && scene.assets.thumbnail;
                const cloudPct = scene.cloud_cover;

                return (
                  <div key={scene.id} className={`scene-card ${isSelected ? 'selected' : ''}`}>
                    {/* Thumbnail Image Preview */}
                    <div className="scene-card-thumb-box">
                      {hasThumb ? (
                        <img
                          src={scene.assets.thumbnail}
                          alt={scene.id}
                          className="scene-thumb-img"
                          onError={(e) => {
                            e.target.onerror = null;
                            e.target.style.display = 'none';
                          }}
                        />
                      ) : (
                        <div className="scene-thumb-placeholder">
                          <Satellite size={22} style={{ color: '#818cf8', opacity: 0.6 }} />
                          <span className="placeholder-text">{scene.sensor}</span>
                        </div>
                      )}
                    </div>

                    {/* Scene Card Details */}
                    <div className="scene-card-details">
                      <div className="scene-card-top">
                        <div className="scene-platform-badge">{scene.platform}</div>
                        {scene.cloud_cover !== null && (
                          <div
                            className={`cloud-badge ${
                              cloudPct < 10 ? 'low' : cloudPct < 30 ? 'mid' : 'high'
                            }`}
                          >
                            <Cloud size={10} /> {cloudPct}% Cloud
                          </div>
                        )}
                        {scene.polarizations && scene.polarizations.length > 0 && (
                          <div className="polarization-badge">
                            {scene.polarizations.join('/')}
                          </div>
                        )}
                      </div>

                      {/* Scene ID Row */}
                      <div className="scene-id-row" title={scene.id}>
                        <span className="scene-id-text mono">{scene.id}</span>
                        <button
                          className="copy-id-btn"
                          onClick={() => handleCopyId(scene.id)}
                          title="Copy Scene ID"
                        >
                          {copiedId === scene.id ? <Check size={11} style={{ color: 'var(--success)' }} /> : <Copy size={11} />}
                        </button>
                      </div>

                      {/* Datetime & Orbit Row */}
                      <div className="scene-meta-row">
                        <span className="meta-text">
                          <Calendar size={11} /> {scene.date} {scene.datetime && scene.datetime.includes('T') ? scene.datetime.split('T')[1].slice(0, 8) + ' UTC' : ''}
                        </span>
                        {scene.orbit_direction && (
                          <span className="meta-text uppercase">{scene.orbit_direction}</span>
                        )}
                      </div>

                      {/* Select Scene Action Button */}
                      <button
                        className={`select-scene-btn ${isSelected ? 'selected' : ''}`}
                        onClick={() => onSelectScene && onSelectScene(scene)}
                        disabled={isAccessingScene}
                      >
                        {isAccessingScene && isSelected ? (
                          <>
                            <Loader2 size={13} className="animate-spin" /> Accessing...
                          </>
                        ) : isSelected ? (
                          <>
                            <Check size={13} /> Scene Selected
                          </>
                        ) : (
                          'Select Scene'
                        )}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
