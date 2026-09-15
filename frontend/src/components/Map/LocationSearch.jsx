import React, { useState } from 'react';
import { Search, MapPin, Navigation, History, ChevronLeft, ChevronRight } from 'lucide-react';
import { mapService } from '../../services/mapService';

const RECENT_LOCATIONS = [
  { id: 'loc-1', name: 'Suez Canal, Egypt', lng: 32.2654, lat: 30.5852, zoom: 11, coords: '30.5852° N, 32.2654° E', type: 'Maritime Bottleneck' },
  { id: 'loc-2', name: 'Amazon Rainforest, BR', lng: -62.2159, lat: -3.4653, zoom: 9, coords: '3.4653° S, 62.2159° W', type: 'Vegetation Canopy' },
  { id: 'loc-3', name: 'Mumbai Port, India', lng: 72.8360, lat: 18.9438, zoom: 12, coords: '18.9438° N, 72.8360° E', type: 'Coastal & SAR' },
  { id: 'loc-4', name: 'Tokyo Bay, Japan', lng: 139.8863, lat: 35.5311, zoom: 11, coords: '35.5311° N, 139.8863° E', type: 'Urban Hydrology' },
];

export default function LocationSearch({ onSelectLocation }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [activeLocation, setActiveLocation] = useState(RECENT_LOCATIONS[0]);

  const handleSearchSubmit = async (e) => {
    e.preventDefault();
    if (!searchTerm.trim()) return;
    
    const query = searchTerm.trim();
    
    try {
      const response = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=1`);
      const data = await response.json();
      
      if (data && data.length > 0) {
        const result = data[0];
        const lat = parseFloat(result.lat);
        const lng = parseFloat(result.lon);
        
        const newLoc = {
          id: `loc-${Date.now()}`,
          name: result.display_name.split(',')[0], // Use a short version of the returned name
          lng: lng,
          lat: lat,
          zoom: 11,
          coords: `${Math.abs(lat).toFixed(4)}° ${lat >= 0 ? 'N' : 'S'}, ${Math.abs(lng).toFixed(4)}° ${lng >= 0 ? 'E' : 'W'}`,
          type: 'Searched Place',
        };
        
        setActiveLocation(newLoc);
        mapService.flyTo({ center: [newLoc.lng, newLoc.lat], zoom: newLoc.zoom });
        if (onSelectLocation) onSelectLocation(newLoc);
        setSearchTerm('');
      } else {
        alert(`Location "${query}" not found.`);
      }
    } catch (error) {
      console.error("Geocoding error:", error);
      alert("Failed to search location. Please try again.");
    }
  };

  const handleSelectRecent = (loc) => {
    setActiveLocation(loc);
    mapService.flyTo({ center: [loc.lng, loc.lat], zoom: loc.zoom });
    if (onSelectLocation) onSelectLocation(loc);
  };

  return (
    <div className={`floating-panel location-search-panel ${isCollapsed ? 'collapsed' : ''}`}>
      {/* Panel Header */}
      <div className="floating-panel-header">
        <div className="panel-title-box">
          <MapPin size={16} className="panel-icon-accent" />
          <span className="panel-title-text">Location Explorer</span>
        </div>
        <button
          className="panel-collapse-btn"
          onClick={() => setIsCollapsed(!isCollapsed)}
          title={isCollapsed ? 'Expand Panel' : 'Collapse Panel'}
        >
          {isCollapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
        </button>
      </div>

      {!isCollapsed && (
        <div className="floating-panel-body">
          {/* Search Input Box */}
          <form className="location-search-form" onSubmit={handleSearchSubmit}>
            <div className="search-input-wrapper">
              <Search size={15} className="search-icon" />
              <input
                type="text"
                className="location-search-input"
                placeholder="Search for a place..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            <button type="submit" className="location-search-btn">
              Search
            </button>
          </form>

          {/* Active Location Coordinates HUD */}
          <div className="active-coords-hud">
            <div className="hud-label">Active Target Area</div>
            <div className="hud-location-name">{activeLocation.name}</div>
            <div className="hud-coords mono">
              <Navigation size={11} /> {activeLocation.coords}
            </div>
          </div>

          {/* Recent Searches / Popular Places */}
          <div className="recent-searches-section">
            <div className="recent-header">
              <History size={12} /> Recent Places
            </div>
            <div className="recent-chips-grid">
              {RECENT_LOCATIONS.map((loc) => (
                <button
                  key={loc.id}
                  className={`recent-chip ${loc.id === activeLocation.id ? 'active' : ''}`}
                  onClick={() => handleSelectRecent(loc)}
                  title={`${loc.name} (${loc.type})`}
                >
                  <MapPin size={11} />
                  <span>{loc.name}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
