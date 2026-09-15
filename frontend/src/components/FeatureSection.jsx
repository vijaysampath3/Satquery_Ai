import React from 'react';
import { MessageSquare, GitCompare, Layers, Droplet } from 'lucide-react';

const capabilityCards = [
  {
    icon: <MessageSquare size={24} />,
    title: "IMAGE INTELLIGENCE",
    description: "Ask questions about satellite imagery using natural language and receive visual evidence.",
    pills: ["VQA", "Image description", "Target identification"],
  },
  {
    icon: <GitCompare size={24} />,
    title: "CHANGE DETECTION",
    description: "Compare observations across time to identify meaningful spatial changes.",
    pills: ["Water change", "Vegetation change", "Pixel-level change"],
  },
  {
    icon: <Layers size={24} />,
    title: "MULTI-SENSOR ANALYSIS",
    description: "Combine optical and SAR observations for a richer understanding of the scene.",
    pills: ["Sentinel-2", "Sentinel-1", "Optical + SAR"],
  },
  {
    icon: <Droplet size={24} />,
    title: "SPECIALIZED DETECTION",
    description: "Apply targeted remote-sensing analysis to specific phenomena.",
    pills: ["Oil-spill screening", "Water detection", "Built-up areas", "Vegetation"],
  },
];

export default function FeatureSection() {
  return (
    <section className="capabilities-section" id="capabilities">
      <div className="section-eyebrow">CAPABILITIES</div>
      <h2 className="section-heading">One interface for satellite intelligence.</h2>
      <p className="section-subheading">
        From a single image to multi-temporal and multi-sensor analysis.
      </p>

      <div className="capabilities-grid-4">
        {capabilityCards.map((cap, idx) => (
          <div className="cap-glass-card" key={idx}>
            <div className="cap-icon-wrap">{cap.icon}</div>
            <h3 className="cap-card-title">{cap.title}</h3>
            <p className="cap-card-desc">{cap.description}</p>
            <div className="cap-pills-row">
              {cap.pills.map((pill, pIdx) => (
                <span className="cap-feature-pill" key={pIdx}>
                  {pill}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
