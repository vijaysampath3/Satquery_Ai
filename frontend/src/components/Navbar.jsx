import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Compass, ArrowRight, Satellite } from 'lucide-react';

export default function Navbar() {
  const navigate = useNavigate();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      if (window.scrollY > 20) {
        setScrolled(true);
      } else {
        setScrolled(false);
      }
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const scrollToSection = (id) => {
    const elem = document.getElementById(id);
    if (elem) {
      elem.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <header className={`landing-nav-wrap ${scrolled ? 'scrolled' : ''}`}>
      <nav className="landing-nav">
        {/* Brand Group */}
        <div className="brand-group" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
          <div className="brand-icon-box">
            <Satellite size={20} style={{ color: '#818cf8' }} />
          </div>
          <div>
            <h1 className="brand-title">SatQuery AI</h1>
            <p className="brand-subtitle">Remote sensing intelligence</p>
          </div>
        </div>

        {/* Navigation Links */}
        <div className="nav-center-links">
          <a href="#product" onClick={(e) => { e.preventDefault(); scrollToSection('product'); }} className="nav-link-item">
            Product
          </a>
          <a href="#capabilities" onClick={(e) => { e.preventDefault(); scrollToSection('capabilities'); }} className="nav-link-item">
            Capabilities
          </a>
          <a href="#how-it-works" onClick={(e) => { e.preventDefault(); scrollToSection('how-it-works'); }} className="nav-link-item">
            How it works
          </a>
          <a href="#about" onClick={(e) => { e.preventDefault(); scrollToSection('about'); }} className="nav-link-item">
            About
          </a>
        </div>

        {/* Action CTA */}
        <div>
          <button
            className="btn-launch-primary"
            onClick={() => navigate('/workspace')}
          >
            Launch Workspace <ArrowRight size={15} />
          </button>
        </div>
      </nav>
    </header>
  );
}
