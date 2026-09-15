import React from 'react';
import { Link } from 'react-router-dom';
import { Plus, MessageSquare, Map, Home, ShieldCheck } from 'lucide-react';

export default function Sidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewAnalysis,
  isOpen,
  activeView,
  onToggleViewMode,
}) {
  return (
    <aside className={`workspace-sidebar ${isOpen ? 'open' : ''}`}>
      <div className="sidebar-header">
        <Link to="/" className="sidebar-brand">
          <div className="sidebar-brand-icon">🛰️</div>
          <div>
            <div className="sidebar-brand-title">SatQuery AI</div>
            <div className="sidebar-brand-sub">Remote sensing workspace</div>
          </div>
        </Link>
      </div>

      {onToggleViewMode && (
        <button
          className="new-analysis-btn"
          style={{ background: 'rgba(99, 102, 241, 0.15)', borderColor: 'rgba(99, 102, 241, 0.35)', color: '#a5b4fc' }}
          onClick={onToggleViewMode}
        >
          <Map size={16} /> Switch to Map View
        </button>
      )}

      <button className="new-analysis-btn" onClick={onNewAnalysis}>
        <Plus size={16} /> New analysis
      </button>

      <div className="sidebar-section-label">Recent Analyses</div>

      <div className="sidebar-history-list">
        {sessions && sessions.length > 0 ? (
          sessions.map((sess) => (
            <div
              key={sess.id}
              className={`history-item ${sess.id === activeSessionId ? 'active' : ''}`}
              onClick={() => onSelectSession(sess.id)}
              title={sess.title}
            >
              <MessageSquare size={14} style={{ flexShrink: 0 }} />
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {sess.title}
              </span>
            </div>
          ))
        ) : (
          <div style={{ padding: '0.75rem 0.85rem', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            No previous sessions
          </div>
        )}
      </div>

      <div className="sidebar-footer">
        <Link to="/" className="sidebar-footer-link">
          <Home size={14} /> Back to Landing Page
        </Link>
        <div className="sidebar-footer-link" style={{ cursor: 'default' }}>
          <ShieldCheck size={14} /> ISRO-SAC / SIH 2026
        </div>
      </div>
    </aside>
  );
}
