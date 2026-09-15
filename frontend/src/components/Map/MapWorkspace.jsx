import React, { useState } from 'react';
import MapHeader from './MapHeader';
import LocationSearch from './LocationSearch';
import AIQueryPanel from './AIQueryPanel';
import MapView from './MapView';
import MapControls from './MapControls';
import '../../styles/map.css';

export default function MapWorkspace({
  systemStatus,
  activeView,
  onToggleViewMode,
}) {
  const [selectedLayer, setSelectedLayer] = useState('natgeo-globe');
  const [selectedProjection, setSelectedProjection] = useState('globe-3d');
  const [selectedMode, setSelectedMode] = useState('single');
  const [selectedData, setSelectedData] = useState('sentinel-2');
  const [date1, setDate1] = useState('2024-01-15');
  const [date2, setDate2] = useState('2024-05-20');
  const [selectedModality, setSelectedModality] = useState('optical');

  const handleLocationSelect = (loc) => {
    // Spatial location selection handler
  };

  const handleSendAIQuery = (query) => {
    alert(`Spatial AI Query Submitted:\n"${query}"\n\n(Map AI processing pipeline is connected)`);
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
        />

        {/* 3. Left Floating Location Search Panel */}
        <LocationSearch onSelectLocation={handleLocationSelect} />

        {/* 4. Right Floating AI Query Panel */}
        <AIQueryPanel onSendQuery={handleSendAIQuery} />

        {/* 5. Bottom Secondary Controls Panel */}
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
        />
      </div>
    </div>
  );
}
