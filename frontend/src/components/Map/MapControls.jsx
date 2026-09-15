import React, { useState } from 'react';
import { Box, Calendar, Sliders, Layers, Search, Filter, ChevronUp, ChevronDown, Loader2 } from 'lucide-react';
import AnalysisModeSelector from './AnalysisModeSelector';

export default function MapControls({
  selectedMode,
  onSelectMode,
  selectedData,
  onSelectData,
  date1,
  setDate1,
  date2,
  setDate2,
  selectedModality,
  onSelectModality,
  selectedAOI,
  onToggleAOIDraw,
  isAOIDrawing,
  onSearchScenes,
  isSearchingScenes,
}) {
  const [isExpanded, setIsExpanded] = useState(true);

  return (
    <div className={`map-bottom-controls-bar ${isExpanded ? 'expanded' : 'minimized'}`}>
      {/* Control Toggle Header */}
      <div className="controls-bar-header">
        <div className="controls-header-left">
          <Sliders size={15} className="controls-header-icon" />
          <span className="controls-header-title">Spatial Analysis & Discovery Controls</span>
        </div>
        <button
          className="controls-expand-btn"
          onClick={() => setIsExpanded(!isExpanded)}
          title={isExpanded ? 'Minimize Bar' : 'Expand Bar'}
        >
          {isExpanded ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
        </button>
      </div>

      {isExpanded && (
        <div className="controls-bar-content animate-fade-in">
          {/* 1. Select Area AOI Bounding Box Tool */}
          <div className="control-group">
            <div className="control-section-label">
              <Box size={12} /> Bounding Box AOI
            </div>
            <button
              className={`control-btn-tool ${isAOIDrawing ? 'active' : selectedAOI ? 'has-aoi' : ''}`}
              onClick={onToggleAOIDraw}
              title="Click to select Area of Interest bounding box"
            >
              <Box size={14} />
              <span>
                {isAOIDrawing
                  ? 'Click & Drag Area...'
                  : selectedAOI
                  ? 'AOI Selected ✓'
                  : 'Select Area (AOI)'}
              </span>
            </button>
          </div>

          <div className="controls-divider"></div>

          {/* 2. Satellite Data Selector */}
          <div className="control-group">
            <div className="control-section-label">
              <Layers size={12} /> Satellite Data Source
            </div>
            <div className="satellite-data-pills">
              <button
                className={`sat-pill ${selectedData === 'sentinel-2' ? 'active' : ''}`}
                onClick={() => onSelectData('sentinel-2')}
              >
                Sentinel-2 MSI (10m)
              </button>
              <button
                className={`sat-pill ${selectedData === 'sentinel-1' ? 'active' : ''}`}
                onClick={() => onSelectData('sentinel-1')}
              >
                Sentinel-1 SAR
              </button>
            </div>
          </div>

          <div className="controls-divider"></div>

          {/* 3. Analysis Mode Selector Component */}
          <AnalysisModeSelector selectedMode={selectedMode} onSelectMode={onSelectMode} />

          <div className="controls-divider"></div>

          {/* 4. Date Controls (T1 / T2) */}
          <div className="control-group">
            <div className="control-section-label">
              <Calendar size={12} /> Acquisition Dates
            </div>
            <div className="date-inputs-row">
              <div className="date-input-box">
                <span className="date-label">T1:</span>
                <input
                  type="date"
                  className="date-picker-input"
                  value={date1}
                  onChange={(e) => setDate1(e.target.value)}
                />
              </div>
              {selectedMode === 'temporal' && (
                <div className="date-input-box">
                  <span className="date-label">T2:</span>
                  <input
                    type="date"
                    className="date-picker-input"
                    value={date2}
                    onChange={(e) => setDate2(e.target.value)}
                  />
                </div>
              )}
            </div>
          </div>

          <div className="controls-divider"></div>

          {/* 5. Search Scenes CTA Action Button */}
          <div className="control-group">
            <div className="control-section-label">
              <Search size={12} /> Discovery Action
            </div>
            <button
              className="search-scenes-cta-btn"
              onClick={onSearchScenes}
              disabled={isSearchingScenes}
              title="Search Copernicus STAC catalog for real Sentinel scenes"
            >
              {isSearchingScenes ? (
                <>
                  <Loader2 size={14} className="animate-spin" /> Searching...
                </>
              ) : (
                <>
                  <Search size={14} /> Search Scenes
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
