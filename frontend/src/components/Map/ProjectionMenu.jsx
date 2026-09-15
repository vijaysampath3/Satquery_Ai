import React, { useState } from 'react';
import { Globe, ChevronDown, Check } from 'lucide-react';

export const PROJECTIONS = [
  { id: 'epsg-3857', name: 'Web Mercator', code: 'EPSG:3857', desc: 'Standard web map tile projection' },
  { id: 'epsg-4326', name: 'WGS84 Equirectangular', code: 'EPSG:4326', desc: 'Global lat/lon geographic coordinate grid' },
  { id: 'globe-3d', name: '3D Orthographic Globe', code: '3D Globe', desc: 'Spherical planetary perspective view' },
  { id: 'utm-local', name: 'UTM Local Grid', code: 'UTM Zone', desc: 'Conformal projected spatial coordinates' },
];

export default function ProjectionMenu({ selectedProjection, onSelectProjection }) {
  const [isOpen, setIsOpen] = useState(false);
  const currentProj = PROJECTIONS.find((p) => p.id === selectedProjection) || PROJECTIONS[0];

  return (
    <div className="map-dropdown-wrap">
      <button
        className="map-dropdown-trigger"
        onClick={() => setIsOpen(!isOpen)}
        title="Select Coordinate Projection"
      >
        <Globe size={15} className="dropdown-icon" />
        <span className="dropdown-label">{currentProj.name}</span>
        <ChevronDown size={13} className={`dropdown-arrow ${isOpen ? 'open' : ''}`} />
      </button>

      {isOpen && (
        <div className="map-dropdown-menu animate-fade-in">
          <div className="dropdown-header">Map Projection System</div>
          {PROJECTIONS.map((proj) => (
            <div
              key={proj.id}
              className={`dropdown-item ${proj.id === selectedProjection ? 'selected' : ''}`}
              onClick={() => {
                onSelectProjection(proj.id);
                setIsOpen(false);
              }}
            >
              <div className="dropdown-item-info">
                <div className="dropdown-item-title">{proj.name}</div>
                <div className="dropdown-item-desc">{proj.desc}</div>
              </div>
              <div className="dropdown-item-badge mono">{proj.code}</div>
              {proj.id === selectedProjection && <Check size={14} className="check-icon" />}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
