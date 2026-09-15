import React, { useState } from 'react';
import { Bot, Sparkles, Send, HelpCircle, ChevronRight, ChevronLeft } from 'lucide-react';

const SUGGESTED_SPATIAL_QUERIES = [
  "Identify water body changes",
  "Detect marine oil spill slicks",
  "Highlight vegetation canopy",
  "Analyze urban infrastructure",
];

export default function AIQueryPanel({ onSendQuery }) {
  const [queryText, setQueryText] = useState('');
  const [isCollapsed, setIsCollapsed] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!queryText.trim()) return;
    if (onSendQuery) onSendQuery(queryText.trim());
    setQueryText('');
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
          {/* Query Text Form */}
          <form className="ai-query-form" onSubmit={handleSubmit}>
            <textarea
              className="ai-query-textarea"
              placeholder="Ask a question about this map region..."
              value={queryText}
              onChange={(e) => setQueryText(e.target.value)}
              rows={3}
            />
            <button
              type="submit"
              className="ask-ai-btn"
              disabled={!queryText.trim()}
              title="Submit natural language query to SatQuery AI"
            >
              <Sparkles size={14} />
              <span>Ask AI</span>
            </button>
          </form>

          {/* Suggested Questions Chips */}
          <div className="suggested-queries-section">
            <div className="suggested-header">
              <HelpCircle size={12} /> Suggested Questions
            </div>
            <div className="suggested-chips-column">
              {SUGGESTED_SPATIAL_QUERIES.map((q, idx) => (
                <button
                  key={idx}
                  className="suggested-spatial-chip"
                  onClick={() => handleSelectSuggested(q)}
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
