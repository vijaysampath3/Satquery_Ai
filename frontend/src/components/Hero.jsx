import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, ArrowRight, CheckCircle2, ShieldAlert, Layers } from 'lucide-react';

export default function Hero() {
  const navigate = useNavigate();

  const scrollToCapabilities = () => {
    const elem = document.getElementById('capabilities');
    if (elem) {
      elem.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <section className="hero-section">
      {/* Small Eyebrow Pill */}
      <div className="hero-eyebrow animate-fade-in">
        <span className="hero-pulse-dot"></span>
        EARTH OBSERVATION · AI-POWERED
      </div>

      {/* Large Headline */}
      <h1 className="hero-title animate-fade-in">
        Understand <span className="text-gradient-cyan">satellite imagery</span> in plain language.
      </h1>

      {/* Supporting Description */}
      <p className="hero-subtitle animate-fade-in">
        Ask questions, detect changes, highlight features, and analyze optical and SAR imagery with SatQuery AI.
      </p>

      {/* CTA Buttons Group */}
      <div className="hero-cta-group animate-fade-in">
        <button
          className="btn-hero-primary-lg"
          onClick={() => navigate('/workspace')}
        >
          Launch Workspace <ArrowRight size={18} />
        </button>
        <button
          className="btn-hero-secondary"
          onClick={scrollToCapabilities}
        >
          Explore capabilities
        </button>
      </div>

      {/* Hero Visual Panel Showcase */}
      <div className="hero-visual-wrapper animate-fade-in">
        <div className="hero-showcase-panel">
          {/* Top Panel Telemetry Header */}
          <div className="panel-header-bar">
            <div className="panel-dots">
              <span className="panel-dot red"></span>
              <span className="panel-dot yellow"></span>
              <span className="panel-dot green"></span>
            </div>
            <div className="mono" style={{ fontSize: '0.7rem', color: '#94a3b8' }}>
              SATQUERY_OBSERVATION_STREAM // LAT: 17.6868° N · LON: 83.2185° E
            </div>
            <div style={{ color: '#10b981', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981' }}></span> LIVE SENSOR
            </div>
          </div>

          {/* Viewport & Satellite Scene */}
          <div className="showcase-viewport">
            <img
              src="https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=1600&auto=format&fit=crop"
              alt="Earth Observation Satellite Scene"
              className="showcase-bg-img"
              loading="eager"
            />

            {/* Scanline & Crosshair Grid */}
            <div className="showcase-scanline"></div>
            <div className="showcase-crosshair"></div>

            {/* Bottom Overlay Info */}
            <div className="showcase-overlay-bottom">
              <div className="showcase-meta-info">
                <div className="showcase-tag">SENTINEL-2 · OPTICAL MULTISPECTRAL</div>
                <div className="showcase-heading">
                  High-Resolution Earth Observation Scene
                </div>
              </div>

              <div className="sensor-badges">
                <span className="sensor-badge">OPTICAL</span>
                <span className="sensor-badge">SAR</span>
                <span className="sensor-badge">MULTIMODAL</span>
              </div>
            </div>
          </div>
        </div>

        {/* Floating Glass Analysis Card */}
        <div className="floating-analysis-card">
          <div className="float-card-header">
            <span>SATQUERY ANALYSIS</span>
            <Sparkles size={13} style={{ color: '#818cf8' }} />
          </div>
          <div className="float-card-query">
            "Highlight vegetation"
          </div>
          <div className="float-card-check">
            <CheckCircle2 size={14} /> Target identified: Vegetation
          </div>
          <div className="float-card-check">
            <CheckCircle2 size={14} /> Vegetation Mask generated
          </div>
        </div>
      </div>
    </section>
  );
}
