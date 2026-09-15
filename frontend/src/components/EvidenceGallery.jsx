import React, { useState } from 'react';
import { Maximize2, X } from 'lucide-react';

export default function EvidenceGallery({ images = [] }) {
  const [activeImage, setActiveImage] = useState(null);

  if (!images || images.length === 0) return null;

  return (
    <div className="evidence-gallery-container">
      <div className="gallery-label">Visual Evidence Gallery</div>

      <div className="evidence-grid-responsive">
        {images.map((img, idx) => (
          <div
            key={idx}
            className="evidence-card-item"
            onClick={() => setActiveImage(img)}
            title="Click to expand"
          >
            <img src={img.url} alt={img.caption} loading="lazy" />
            <div className="evidence-caption-bar">{img.caption}</div>
          </div>
        ))}
      </div>

      {/* Lightbox Modal */}
      {activeImage && (
        <div className="lightbox-overlay" onClick={() => setActiveImage(null)}>
          <button className="lightbox-close-btn" onClick={() => setActiveImage(null)}>
            &times;
          </button>
          <div className="lightbox-content-box" onClick={(e) => e.stopPropagation()}>
            <img src={activeImage.url} alt={activeImage.caption} className="lightbox-img" />
            <div className="lightbox-caption-box">{activeImage.caption}</div>
          </div>
        </div>
      )}
    </div>
  );
}
