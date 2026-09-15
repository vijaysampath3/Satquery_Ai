import React, { useState } from 'react';
import { Bot, Sparkles, Send, HelpCircle, ChevronRight, ChevronLeft } from 'lucide-react';

const SUGGESTED_SPATIAL_QUERIES = [
  "Highlight vegetation",
  "Show water bodies",
  "Highlight urban areas",
  "What is visible in this region?",
  "Describe this satellite image.",
];

export default function AIQueryPanel({ onSendQuery, isReady = false, isAnalyzing = false }) {
  const [queryText, setQueryText] = useState('');
  const [isCollapsed, setIsCollapsed] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!queryText.trim() || isAnalyzing) return;
    if (onSendQuery) onSendQuery(queryText.trim());
  };

  const handleSelectSuggested = (q) => {
    setQueryText(q);
  };

  return (
    <div className={`floating-panel ai-query-panel ${isCollapsed ? 'collapsed' : ''}`}>
      {/* Panel Header */}
      <div className="floating-panel-header">
        <button
          className="panel-collapse-btn"
          onClick={() => setIsCollapsed(!isCollapsed)}
          title={isCollapsed ? 'Expand AI Panel' : 'Collapse AI Panel'}
        >
          {isCollapsed ? <ChevronLeft size={14} /> : <ChevronRight size={14} />}
        </button>
        <div className="panel-title-box">
          <Bot size={16} className="panel-icon-sparkle" />
          <span className="panel-title-text">SatQuery AI Assistant</span>
        </div>
      </div>

      {!isCollapsed && (
        <div className="floating-panel-body">
          {!isReady && (
            <div className="ai-readiness-hint warning">
              Select and prepare a Sentinel-2 scene before asking AI.
            </div>
          )}

          {isReady && (
            <div className="ai-readiness-hint success">
              ✓ Sentinel-2 AOI Prepared & Ready for AI Query
            </div>
          )}

          {/* Query Text Form */}
          <form className="ai-query-form" onSubmit={handleSubmit}>
            <textarea
              className="ai-query-textarea"
              placeholder={isReady ? "Ask a question about this prepared Sentinel-2 AOI..." : "Select and prepare a scene first..."}
              value={queryText}
              onChange={(e) => setQueryText(e.target.value)}
              rows={3}
              disabled={isAnalyzing}
            />
            <button
              type="submit"
              className="ask-ai-btn"
              disabled={!queryText.trim() || !isReady || isAnalyzing}
              title={isReady ? "Submit query to Qwen2.5-VL" : "Select and prepare a Sentinel-2 scene first"}
            >
              <Sparkles size={14} />
              <span>{isAnalyzing ? 'Analyzing Satellite Data...' : 'Ask AI'}</span>
            </button>
          </form>

          {/* Suggested Questions Chips */}
          <div className="suggested-queries-section">
            <div className="suggested-header">
              <HelpCircle size={12} /> Suggested Sentinel-2 Queries
            </div>
            <div className="suggested-chips-column">
              {SUGGESTED_SPATIAL_QUERIES.map((q, idx) => (
                <button
                  key={idx}
                  className="suggested-spatial-chip"
                  onClick={() => handleSelectSuggested(q)}
                  disabled={isAnalyzing}
                >
                  <Sparkles size={11} className="chip-sparkle" />
                  <span>{q}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

