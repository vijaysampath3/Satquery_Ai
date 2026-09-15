import React, { useState } from 'react';
import MapHeader from './MapHeader';
import LocationSearch from './LocationSearch';
import AIQueryPanel from './AIQueryPanel';
import MapView from './MapView';
import MapControls from './MapControls';
import SceneResults from './SceneResults';
import { searchSatelliteScenes, accessSatelliteScene, clipSatelliteScene, analyzeSatelliteScene } from '../../api/satquery';
import '../../styles/map.css';

export default function MapWorkspace({
  systemStatus,
  activeView,
  onToggleViewMode,
}) {
  const [selectedLayer, setSelectedLayer] = useState('natgeo-globe');
  const [selectedProjection, setSelectedProjection] = useState('globe-3d');
  const [selectedMode, setSelectedMode] = useState('single'); // single, temporal, multimodal
  const [selectedData, setSelectedData] = useState('sentinel-2'); // sentinel-2, sentinel-1
  const [date1, setDate1] = useState('2026-08-01');
  const [date2, setDate2] = useState('2026-09-01');
  const [selectedModality, setSelectedModality] = useState('optical');

  // AOI State
  const [selectedAOI, setSelectedAOI] = useState({
    min_lon: 32.20,
    min_lat: 30.50,
    max_lon: 32.40,
    max_lat: 30.70,
  });
  const [isAOIDrawing, setIsAOIDrawing] = useState(false);

  // STAC Scene Search Results State
  const [searchResult, setSearchResult] = useState(null);
  const [isSearchingScenes, setIsSearchingScenes] = useState(false);
  const [searchError, setSearchError] = useState(null);
  const [selectedScene, setSelectedScene] = useState(null);

  // Phase 3B Scene Access State
  const [accessResult, setAccessResult] = useState(null);
  const [isAccessingScene, setIsAccessingScene] = useState(false);
  const [accessError, setAccessError] = useState(null);

  // Phase 3C Scene AOI Clip State
  const [clipResult, setClipResult] = useState(null);
  const [isClippingScene, setIsClippingScene] = useState(false);
  const [clipError, setClipError] = useState(null);

  // Phase 3D-1 Spatial AI Analysis State
  const [spatialAnalysisResult, setSpatialAnalysisResult] = useState(null);
  const [isAnalyzingSpatial, setIsAnalyzingSpatial] = useState(false);
  const [spatialAnalysisError, setSpatialAnalysisError] = useState(null);

  const handleLocationSelect = (loc) => {
    if (loc && loc.lng && loc.lat) {
      setSelectedAOI({
        min_lon: loc.lng - 0.1,
        min_lat: loc.lat - 0.1,
        max_lon: loc.lng + 0.1,
        max_lat: loc.lat + 0.1,
      });
    }
  };

  const handleToggleAOIDraw = () => {
    setIsAOIDrawing(!isAOIDrawing);
  };

  const handleSearchScenes = async () => {
    if (!selectedAOI) {
      alert('Select an area on the map before searching satellite scenes.');
      return;
    }

    setSearchError(null);
    setIsSearchingScenes(true);
    setAccessResult(null);
    setAccessError(null);
    setClipResult(null);
    setClipError(null);
    setSpatialAnalysisResult(null);
    setSpatialAnalysisError(null);

    const sensorType = selectedData === 'sentinel-1' ? 'SENTINEL-1' : 'SENTINEL-2';
    const dateStart = date1;
    // In single mode, search a 30-day window from date1 to avoid empty single-day results
    const dateEnd = selectedMode === 'temporal' ? date2 : (() => {
      const d = new Date(date1);
      d.setDate(d.getDate() + 30);
      return d.toISOString().split('T')[0];
    })();

    try {
      const res = await searchSatelliteScenes({
        bbox: selectedAOI,
        sensor: sensorType,
        date_start: dateStart,
        date_end: dateEnd,
        cloud_cover_max: 60.0,
        limit: 10,
      });

      setSearchResult(res);
      if (res.scenes && res.scenes.length > 0) {
        handleSelectScene(res.scenes[0]);
      } else {
        setSelectedScene(null);
      }
    } catch (err) {
      setSearchError(err.message);
      alert(`Scene Search Validation / Error: ${err.message}`);
    } finally {
      setIsSearchingScenes(false);
    }
  };

  const handleSelectScene = async (scene) => {
    setSelectedScene(scene);
    if (!scene) return;

    setIsAccessingScene(true);
    setAccessError(null);
    setAccessResult(null);
    setClipResult(null);
    setClipError(null);
    setSpatialAnalysisResult(null);
    setSpatialAnalysisError(null);

    try {
      const res = await accessSatelliteScene({
        scene_id: scene.id,
        sensor: scene.sensor,
        collection: scene.collection,
        aoi: selectedAOI,
      });
      setAccessResult(res);
    } catch (err) {
      setAccessError(err.message);
    } finally {
      setIsAccessingScene(false);
    }
  };

  const handleClipScene = async () => {
    if (!selectedScene || !selectedAOI) return;

    setIsClippingScene(true);
    setClipError(null);
    setClipResult(null);
    setSpatialAnalysisResult(null);
    setSpatialAnalysisError(null);

    try {
      const res = await clipSatelliteScene({
        scene_id: selectedScene.id,
        sensor: selectedScene.sensor,
        collection: selectedScene.collection,
        aoi: selectedAOI,
      });
      setClipResult(res);
    } catch (err) {
      setClipError(err.message);
    } finally {
      setIsClippingScene(false);
    }
  };

  const handleSendAIQuery = async (queryText) => {
    if (!clipResult || clipResult.status !== 'ready' || !selectedScene) {
      alert('Select and clip a Sentinel-2 scene to your AOI before asking AI.');
      return;
    }
    if (selectedScene.sensor && selectedScene.sensor.toUpperCase() !== 'SENTINEL-2') {
      alert('Phase 3D-1 supports Sentinel-2 satellite analysis. Please select a Sentinel-2 scene.');
      return;
    }

    setIsAnalyzingSpatial(true);
    setSpatialAnalysisError(null);

    try {
      const res = await analyzeSatelliteScene({
        scene_id: selectedScene.id,
        sensor: selectedScene.sensor || 'SENTINEL-2',
        collection: selectedScene.collection || 'sentinel-2-l2a',
        aoi: clipResult.aoi || selectedAOI,
        query: queryText,
      });
      setSpatialAnalysisResult(res);
    } catch (err) {
      setSpatialAnalysisError(err.message);
    } finally {
      setIsAnalyzingSpatial(false);
    }
  };

  const isClipReadyForAI = Boolean(
    clipResult &&
    clipResult.status === 'ready' &&
    selectedScene &&
    selectedScene.sensor?.toUpperCase() === 'SENTINEL-2'
  );

  // Evidence Tab View Mode (Original AOI Clip vs Grounding Result)
  const [evidenceTabMode, setEvidenceTabMode] = useState('grounding');

  const getActiveEvidenceImageUrl = () => {
    if (!spatialAnalysisResult) return null;
    const images = spatialAnalysisResult.evidence?.images || [];
    const groundingImg = images.find(
      (img) => img.url?.includes('grounding_overlay') || img.url?.includes('mask')
    );

    if (evidenceTabMode === 'original' || !groundingImg) {
      return spatialAnalysisResult.preview_url || (images[0]?.url);
    }
    return groundingImg.url;
  };

  return (
    <div className="map-workspace-layout">
      {/* 1. Top Bar Header */}
      <MapHeader
        selectedLayer={selectedLayer}
        onSelectLayer={setSelectedLayer}
        selectedProjection={selectedProjection}
        onSelectProjection={setSelectedProjection}
        systemStatus={systemStatus}
        activeView={activeView}
        onToggleViewMode={onToggleViewMode}
      />

      {/* Main Map Viewport Area */}
      <div className="map-viewport-wrapper">
        {/* 2. Central Map Area */}
        <MapView
          selectedLayer={selectedLayer}
          selectedProjection={selectedProjection}
          selectedAOI={selectedAOI}
        />

        {/* 3. Left Floating Location Search Panel */}
        <LocationSearch onSelectLocation={handleLocationSelect} />

        {/* 4. Right Floating AI Query Panel */}
        <AIQueryPanel
          onSendQuery={handleSendAIQuery}
          isReady={isClipReadyForAI}
          isAnalyzing={isAnalyzingSpatial}
        />

        {/* 5. Discovered Scene Results Panel (Appears after search) */}
        {searchResult && (
          <SceneResults
            searchResult={searchResult}
            onSelectScene={handleSelectScene}
            selectedSceneId={selectedScene?.id}
            onClose={() => setSearchResult(null)}
            accessResult={accessResult}
            isAccessingScene={isAccessingScene}
            accessError={accessError}
            onClipScene={handleClipScene}
            clipResult={clipResult}
            isClippingScene={isClippingScene}
            clipError={clipError}
          />
        )}

        {/* 5b. Phase 3D Spatial AI Analysis & Grounding Result Card Overlay */}
        {(spatialAnalysisResult || isAnalyzingSpatial || spatialAnalysisError) && (
          <div className="floating-panel spatial-analysis-result-panel">
            <div className="floating-panel-header">
              <span className="panel-title-text">
                {isAnalyzingSpatial ? '🤖 Analyzing Satellite Data...' : '🤖 Sentinel-2 Spatial AI Result'}
              </span>
              <button
                className="close-panel-btn"
                onClick={() => {
                  setSpatialAnalysisResult(null);
                  setSpatialAnalysisError(null);
                }}
              >
                ×
              </button>
            </div>

            <div className="floating-panel-body">
              {isAnalyzingSpatial && (
                <div className="spatial-analyzing-state">
                  <div className="spinner-sparkle" />
                  <p>Running Sentinel-2 AI Model Pipeline on prepared AOI clip...</p>
                </div>
              )}

              {spatialAnalysisError && (
                <div className="spatial-analysis-error-box">
                  <p className="error-title">Analysis Failed</p>
                  <p className="error-desc">{spatialAnalysisError}</p>
                </div>
              )}

              {spatialAnalysisResult && !isAnalyzingSpatial && (
                <div className="spatial-analysis-content">
                  <div className="analysis-header-row">
                    <span className={`task-badge ${spatialAnalysisResult.task}`}>
                      {spatialAnalysisResult.task.toUpperCase()}
                    </span>
                    <span className="confidence-chip">
                      Confidence: {spatialAnalysisResult.confidence ? `${Math.round(spatialAnalysisResult.confidence * 100)}%` : 'N/A'}
                    </span>
                  </div>

                  <div className="analysis-query-box">
                    <strong>Query:</strong> "{spatialAnalysisResult.query}"
                  </div>

                  <div className="analysis-answer-box">
                    <p className="answer-text">{spatialAnalysisResult.answer}</p>
                  </div>

                  <div className="analysis-source-meta">
                    <span>Scene: {spatialAnalysisResult.scene_id?.slice(0, 22)}...</span>
                    <span>Input: True Color (B04, B03, B02)</span>
                    <span>{spatialAnalysisResult.status_text}</span>
                  </div>

                  {/* Evidence Image Viewer & Tab Toggle */}
                  {spatialAnalysisResult.evidence?.images?.length > 0 && (
                    <div className="analysis-preview-evidence">
                      <div className="evidence-toggle-row">
                        <button
                          className={`evidence-toggle-btn ${evidenceTabMode === 'original' ? 'active' : ''}`}
                          onClick={() => setEvidenceTabMode('original')}
                        >
                          ORIGINAL AOI CLIP
                        </button>
                        <button
                          className={`evidence-toggle-btn ${evidenceTabMode === 'grounding' ? 'active' : ''}`}
                          onClick={() => setEvidenceTabMode('grounding')}
                        >
                          GROUNDING RESULT
                        </button>
                      </div>

                      {getActiveEvidenceImageUrl() && (
                        <img
                          src={getActiveEvidenceImageUrl()}
                          alt="Sentinel-2 AOI Evidence Preview"
                          className="evidence-img"
                        />
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* 6. Bottom Secondary Controls Panel */}
        <MapControls
          selectedMode={selectedMode}
          onSelectMode={setSelectedMode}
          selectedData={selectedData}
          onSelectData={setSelectedData}
          date1={date1}
          setDate1={setDate1}
          date2={date2}
          setDate2={setDate2}
          selectedModality={selectedModality}
          onSelectModality={setSelectedModality}
          selectedAOI={selectedAOI}
          onToggleAOIDraw={handleToggleAOIDraw}
          isAOIDrawing={isAOIDrawing}
          onSearchScenes={handleSearchScenes}
          isSearchingScenes={isSearchingScenes}
        />
      </div>
    </div>
  );
}

