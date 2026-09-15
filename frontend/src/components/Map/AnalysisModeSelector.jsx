import React from 'react';
import { Target, Layers, Repeat, Eye } from 'lucide-react';

export const ANALYSIS_MODES = [
  { id: 'single', name: 'Single Scene', icon: Eye, desc: 'VQA, Captioning, Target Grounding' },
  { id: 'temporal', name: 'Bi-Temporal Change', icon: Repeat, desc: '2-Date Land Cover & Water Change' },
  { id: 'multimodal', name: 'Optical + SAR Fusion', icon: Layers, desc: 'Cross-modal Radar & Spectral analysis' },
];

export default function AnalysisModeSelector({ selectedMode, onSelectMode }) {
  return (
    <div className="analysis-mode-selector-wrap">
      <div className="control-section-label">
        <Target size={12} /> Analysis Mode
      </div>
      <div className="analysis-mode-pills">
        {ANALYSIS_MODES.map((mode) => {
          const Icon = mode.icon;
          const isActive = mode.id === selectedMode;
          return (
            <button
              key={mode.id}
              className={`mode-selector-btn ${isActive ? 'active' : ''}`}
              onClick={() => onSelectMode(mode.id)}
              title={mode.desc}
            >
              <Icon size={13} />
              <span>{mode.name}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
