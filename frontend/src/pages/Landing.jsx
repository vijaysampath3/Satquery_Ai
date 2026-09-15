import React from 'react';
import { useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import Hero from '../components/Hero';
import FeatureSection from '../components/FeatureSection';
import {
  MessageSquare,
  ArrowRight,
  Sparkles,
  CheckCircle2,
  Cpu,
  Globe,
  Database,
  Search,
  Check,
  ShieldCheck,
} from 'lucide-react';
import '../styles/landing.css';

export default function Landing() {
  const navigate = useNavigate();

  return (
    <div className="landing-container">
      {/* Background Grids & Orbital Particle Overlay */}
      <div className="landing-bg-grid"></div>
      <div className="stars-overlay"></div>

      {/* Glass Navbar */}
      <Navbar />

      <main style={{ position: 'relative', zIndex: 1 }}>
        {/* 1. Hero Section */}
        <Hero />

        {/* 2. Trust / Capability Metadata Strip */}
        <div className="trust-strip">
          <div className="trust-strip-inner">
            <span className="trust-item">
              <span className="trust-item-bullet">•</span> NATURAL LANGUAGE
            </span>
            <span className="trust-item">
              <span className="trust-item-bullet">•</span> OPTICAL IMAGERY
            </span>
            <span className="trust-item">
              <span className="trust-item-bullet">•</span> SAR
            </span>
            <span className="trust-item">
              <span className="trust-item-bullet">•</span> CHANGE DETECTION
            </span>
            <span className="trust-item">
              <span className="trust-item-bullet">•</span> VISUAL GROUNDING
            </span>
            <span className="trust-item">
              <span className="trust-item-bullet">•</span> MULTIMODAL ANALYSIS
            </span>
          </div>
        </div>

        {/* 3. Capabilities Section (4 Glass Cards) */}
        <FeatureSection />

        {/* 4. Interactive Analysis Preview ("Ask the image") */}
        <section className="interactive-demo-section" id="product">
          <div className="section-eyebrow">INTERACTIVE PREVIEW</div>
          <h2 className="section-heading">Ask the image.</h2>
          <p className="section-subheading">
            Experience conversational Earth-observation intelligence in action.
          </p>

          <div className="demo-glass-workspace">
            {/* Left: Satellite Image with Bounding Box Overlay */}
            <div className="demo-left-image">
              <img
                src="https://images.unsplash.com/photo-1500382017468-9049fed747ef?q=80&w=1000&auto=format&fit=crop"
                alt="Vegetation Grounding Preview"
              />
              <div className="demo-bbox-highlight">
                <span className="demo-bbox-tag">TARGET GROUNDED</span>
              </div>
            </div>

            {/* Right: Conversational Query Preview & Visual Evidence */}
            <div className="demo-right-chat">
              <div className="demo-user-msg">
                <MessageSquare size={18} style={{ color: '#818cf8' }} />
                <span>"Highlight vegetation near the settlement."</span>
              </div>

              <div className="demo-result-box">
                <div className="demo-result-row">
                  <span className="demo-result-key">Pipeline Task</span>
                  <span className="demo-result-val">Grounding & Segmentation</span>
                </div>
                <div className="demo-result-row">
                  <span className="demo-result-key">Detected Target</span>
                  <span className="demo-result-val">Vegetation</span>
                </div>
                <div className="demo-result-row">
                  <span className="demo-result-key">Analysis Method</span>
                  <span className="demo-result-val">RGB vegetation screening</span>
                </div>
                <div className="demo-result-row">
                  <span className="demo-result-key">Target Mask Status</span>
                  <span className="demo-result-val" style={{ color: '#10b981' }}>
                    ✓ Mask Generated
                  </span>
                </div>

                <div style={{ marginTop: '0.85rem' }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.4rem', fontWeight: 700, textTransform: 'uppercase' }}>
                    GENERATED EVIDENCE GALLERY
                  </div>
                  <div className="demo-mini-gallery">
                    <div className="demo-mini-thumb" title="True Color RGB">
                      <img src="https://images.unsplash.com/photo-1500382017468-9049fed747ef?q=80&w=200&auto=format&fit=crop" alt="RGB" />
                    </div>
                    <div className="demo-mini-thumb" title="Vegetation Mask" style={{ background: '#070a11' }}>
                      <div style={{ width: '100%', height: '100%', background: 'radial-gradient(circle, #10b981 30%, #282828 70%)' }}></div>
                    </div>
                    <div className="demo-mini-thumb" title="Grounding Overlay">
                      <img src="https://images.unsplash.com/photo-1500382017468-9049fed747ef?q=80&w=200&auto=format&fit=crop" alt="Overlay" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 5. How It Works (3-Step Connected Flow) */}
        <section className="how-it-works-section" id="how-it-works">
          <div className="section-eyebrow">WORKFLOW</div>
          <h2 className="section-heading">How SatQuery AI works.</h2>
          <p className="section-subheading">
            From raw satellite scenes to structured visual intelligence in three steps.
          </p>

          <div className="steps-flow-grid">
            <div className="step-card-item">
              <div className="step-number-badge">01</div>
              <h3 className="step-title">UPLOAD</h3>
              <p className="step-desc">
                Provide optical, multispectral, or SAR satellite imagery in PNG, JPEG, or GeoTIFF formats.
              </p>
            </div>

            <div className="step-card-item">
              <div className="step-number-badge">02</div>
              <h3 className="step-title">ASK</h3>
              <p className="step-desc">
                Describe what you want to understand using natural-language questions or feature requests.
              </p>
            </div>

            <div className="step-card-item">
              <div className="step-number-badge">03</div>
              <h3 className="step-title">ANALYZE</h3>
              <p className="step-desc">
                SatQuery selects the appropriate analysis pipeline and generates verified visual evidence.
              </p>
            </div>
          </div>
        </section>

        {/* 6. Remote Sensing Technology Architecture */}
        <section className="tech-graph-section">
          <div className="section-eyebrow">ARCHITECTURE</div>
          <h2 className="section-heading">Remote-sensing processing engine.</h2>
          <p className="section-subheading">
            Integrating spectral indices, vision-language models, and radar analytics.
          </p>

          <div className="tech-graph-card">
            <div className="tech-center-node">
              <Cpu size={22} /> SATQUERY AI ENGINE
            </div>

            <div className="tech-nodes-grid">
              <div className="tech-subnode">OPTICAL (Sentinel-2)</div>
              <div className="tech-subnode">SAR (Sentinel-1)</div>
              <div className="tech-subnode">VQA ENGINE</div>
              <div className="tech-subnode">OBJECT GROUNDING</div>
              <div className="tech-subnode">TEMPORAL CHANGE</div>
              <div className="tech-subnode">NDVI / NDWI / NDBI</div>
              <div className="tech-subnode">OIL-SPILL SCREENING</div>
            </div>
          </div>
        </section>

        {/* 7. Real-World Applications Grid */}
        <section className="apps-section">
          <div className="section-eyebrow">APPLICATIONS</div>
          <h2 className="section-heading">Real-world Earth observation.</h2>
          <p className="section-subheading">
            Applied remote-sensing intelligence across environmental, marine, and urban domains.
          </p>

          <div className="apps-grid">
            <div className="app-card">
              <img
                src="/images/water_body.jpg"
                alt="Water Body Monitoring"
                className="app-card-img"
              />
              <div className="app-card-body">
                <h3 className="app-card-title">Water-Body Monitoring</h3>
                <p className="app-card-desc">
                  Track lake expansion, seasonal recession, and flood gain/loss with NDWI and visual screening.
                </p>
              </div>
            </div>

            <div className="app-card">
              <img
                src="/images/vegetation_canopy.jpg"
                alt="Vegetation & Canopy Analysis"
                className="app-card-img"
              />
              <div className="app-card-body">
                <h3 className="app-card-title">Vegetation & Land Cover</h3>
                <p className="app-card-desc">
                  Identify crop health, forest canopy cover, and agricultural boundaries with NDVI index calculation.
                </p>
              </div>
            </div>

            <div className="app-card">
              <img
                src="/images/urban_infrastructure.jpg"
                alt="Urban & Infrastructure"
                className="app-card-img"
              />
              <div className="app-card-body">
                <h3 className="app-card-title">Urban & Built-up Areas</h3>
                <p className="app-card-desc">
                  Detect built structures, roads, and urban sprawl using NDBI spectral reflectance and visual screening.
                </p>
              </div>
            </div>

            <div className="app-card">
              <img
                src="/images/marine_oil_spill.jpg"
                alt="Marine Oil-Spill Screening"
                className="app-card-img"
              />
              <div className="app-card-body">
                <h3 className="app-card-title">Marine Oil-Spill Screening</h3>
                <p className="app-card-desc">
                  Analyze Sentinel-1 SAR backscatter to identify potential oil-slick candidates on sea surfaces.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* 8. Why SatQuery ("From pixels to questions") */}
        <section className="why-section">
          <div className="section-eyebrow">POSITIONING</div>
          <h2 className="section-heading">From pixels to questions.</h2>
          <p className="section-subheading">
            SatQuery bridges the gap between complex remote-sensing data and natural-language analysis.
          </p>

          <div className="pipeline-flow-box">
            <div className="flow-step-pill">Natural language</div>
            <div className="flow-arrow">→</div>
            <div className="flow-step-pill">Task understanding</div>
            <div className="flow-arrow">→</div>
            <div className="flow-step-pill">Remote sensing analysis</div>
            <div className="flow-arrow">→</div>
            <div className="flow-step-pill">Visual evidence</div>
          </div>
        </section>

        {/* 9. Final CTA Banner */}
        <section className="final-cta-section">
          <div className="final-cta-card">
            <h2 className="final-cta-title">Ask your next satellite image a question.</h2>
            <p className="final-cta-sub">
              Explore satellite imagery through a natural-language interface.
            </p>
            <button
              className="btn-hero-primary-lg"
              onClick={() => navigate('/workspace')}
              style={{ margin: '0 auto' }}
            >
              Launch Workspace <ArrowRight size={18} />
            </button>
          </div>
        </section>
      </main>

      {/* Minimal Footer */}
      <footer className="landing-footer" id="about">
        <div className="footer-inner">
          <div className="footer-brand">
            <h3>SatQuery AI</h3>
            <p>Remote sensing intelligence</p>
          </div>

          <div className="footer-links">
            <a href="#product" className="footer-link">Product</a>
            <a href="#capabilities" className="footer-link">Capabilities</a>
            <a href="/workspace" onClick={(e) => { e.preventDefault(); navigate('/workspace'); }} className="footer-link">Workspace</a>
            <a href="#about" className="footer-link">About</a>
          </div>

          <div>
            SIH 2026 / ISRO-SAC
          </div>
        </div>
      </footer>
    </div>
  );
}
