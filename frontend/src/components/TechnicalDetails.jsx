import React, { useState } from 'react';
import { ChevronDown, ChevronRight, CheckCircle } from 'lucide-react';
import { extractObservedInferred, getConfidencePercentage } from '../utils/formatters';
import FormattedEvidenceText from './FormattedEvidenceText';

export default function TechnicalDetails({
  data = {},
  trace = {},
  observedText: propObserved,
  inferredText: propInferred,
}) {
  const [isOpen, setIsOpen] = useState(false);

  const steps = trace.pipeline_steps || [];
  const totalTimeMs = trace.total_time_ms || 0;
  const taskName = (trace.detected_task || data.task || 'Analysis').toUpperCase();
  const inputType = data.input_badge || 'Remote Sensing Image';
  const analysisMode = data.analysis_mode || data.method || 'Standard Pipeline';
  const confidencePct = getConfidencePercentage(data);

  let obsText = propObserved;
  let infText = propInferred;

  if (!obsText && !infText && data.answer) {
    const extracted = extractObservedInferred(data.answer);
    obsText = extracted.observedText;
    infText = extracted.inferredText;
  }

  return (
    <div className="tech-details-disclosure">
      <div className="tech-details-summary" onClick={() => setIsOpen(!isOpen)}>
        {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span>View technical details</span>
      </div>

      {isOpen && (
        <div className="tech-details-content animate-fade-in">
          <div className="tech-info-grid">
            <div className="tech-info-item">
              <span className="tech-info-key">Pipeline Task</span>
              <span className="tech-info-val">{taskName}</span>
            </div>
            <div className="tech-info-item">
              <span className="tech-info-key">Confidence Score</span>
              <span className="tech-info-val" style={{ color: '#818cf8', fontWeight: 700 }}>
                {confidencePct}%
              </span>
            </div>
            <div className="tech-info-item">
              <span className="tech-info-key">Input Badge</span>
              <span className="tech-info-val">{inputType}</span>
            </div>
            <div className="tech-info-item">
              <span className="tech-info-key">Analysis Mode / Method</span>
              <span className="tech-info-val">{analysisMode}</span>
            </div>
            <div className="tech-info-item">
              <span className="tech-info-key">Execution Time</span>
              <span className="tech-info-val">{totalTimeMs.toFixed(0)} ms</span>
            </div>
          </div>

          {obsText && (
            <div className="tech-obs-section">
              <div className="tech-section-header">OBSERVED EVIDENCE</div>
              <FormattedEvidenceText text={obsText} type="observed" />
            </div>
          )}

          {infText && (
            <div className="tech-inf-section">
              <div className="tech-section-header">INFERRED INTELLIGENCE</div>
              <FormattedEvidenceText text={infText} type="inferred" />
            </div>
          )}

          {steps.length > 0 && (
            <div className="trace-steps-wrap">
              <div
                style={{
                  fontSize: '0.68rem',
                  fontWeight: 700,
                  color: 'var(--text-muted)',
                  textTransform: 'uppercase',
                  marginBottom: '0.2rem',
                }}
              >
                Pipeline Execution Steps
              </div>
              {steps.map((s, idx) => (
                <div key={idx} className="trace-step-row-item">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span
                      style={{ color: 'var(--accent-primary)', fontWeight: 700 }}
                      className="mono"
                    >
                      #{s.step || idx + 1}
                    </span>
                    <span className="mono" style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                      {s.model}
                    </span>
                    <span style={{ color: 'var(--text-muted)' }}>({s.action})</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span className="mono" style={{ color: 'var(--text-muted)' }}>
                      {(s.time_ms || 0).toFixed(0)}ms
                    </span>
                    <span
                      style={{
                        color: 'var(--success)',
                        fontWeight: 600,
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.2rem',
                      }}
                    >
                      <CheckCircle size={12} /> Ready
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
