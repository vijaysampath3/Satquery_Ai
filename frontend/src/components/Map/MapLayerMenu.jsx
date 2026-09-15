import React, { useState } from 'react';
import { Layers, ChevronDown, Check } from 'lucide-react';

export const MAP_LAYERS = [
  { id: 'natgeo-globe', name: 'Natural Earth 3D Globe', type: '3D Topo', desc: 'Topographic terrain, ocean bathymetry & graticules' },
  { id: 'esri-satellite', name: 'Esri World Imagery', type: 'Satellite', desc: 'High-res global visual imagery' },
  { id: 'sentinel2-cloudless', name: 'Sentinel-2 True Color', type: 'Copernicus', desc: 'Sentinel-2 10m cloudless satellite mosaic' },
  { id: 'world-topo', name: 'Esri World Topographic', type: 'Topo', desc: 'Physical landform contours & boundaries' },
  { id: 'carto-dark', name: 'Dark Canvas Vector', type: 'Vector', desc: 'High-contrast dark cartography' },
  { id: 'osm-standard', name: 'OpenStreetMap Standard', type: 'Street', desc: 'Global road & place boundaries' },
];

export default function MapLayerMenu({ selectedLayer, onSelectLayer }) {
  const [isOpen, setIsOpen] = useState(false);
  const currentLayer = MAP_LAYERS.find((l) => l.id === selectedLayer) || MAP_LAYERS[0];

  return (
    <div className="map-dropdown-wrap">
      <button
        className="map-dropdown-trigger"
        onClick={() => setIsOpen(!isOpen)}
        title="Select Satellite Base Map Layer"
      >
        <Layers size={15} className="dropdown-icon" />
        <span className="dropdown-label">{currentLayer.name}</span>
        <ChevronDown size={13} className={`dropdown-arrow ${isOpen ? 'open' : ''}`} />
      </button>

      {isOpen && (
        <div className="map-dropdown-menu animate-fade-in">
          <div className="dropdown-header">Satellite Base Map</div>
          {MAP_LAYERS.map((layer) => (
            <div
              key={layer.id}
              className={`dropdown-item ${layer.id === selectedLayer ? 'selected' : ''}`}
              onClick={() => {
                onSelectLayer(layer.id);
                setIsOpen(false);
              }}
            >
              <div className="dropdown-item-info">
                <div className="dropdown-item-title">{layer.name}</div>
                <div className="dropdown-item-desc">{layer.desc}</div>
              </div>
              <div className="dropdown-item-badge">{layer.type}</div>
              {layer.id === selectedLayer && <Check size={14} className="check-icon" />}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
