import React, { useState, useEffect } from 'react';
import { Menu, Loader2, Map } from 'lucide-react';
import Message from './Message';
import Composer from './Composer';
import EmptyWorkspace from './EmptyWorkspace';

const LOADING_STAGES = [
  'Understanding your query...',
  'Identifying analysis task...',
  'Processing satellite imagery...',
  'Generating visual evidence...',
];

export default function Chat({
  messages,
  attachments,
  queryText,
  setQueryText,
  onAddFiles,
  onRemoveFile,
  onToggleModality,
  onSend,
  isAnalyzing,
  onToggleSidebar,
  systemStatus,
  onToggleViewMode,
}) {
  const [loadingStageIdx, setLoadingStageIdx] = useState(0);

  // Cycle loading stages while analyzing
  useEffect(() => {
    if (!isAnalyzing) {
      setLoadingStageIdx(0);
      return;
    }
    const interval = setInterval(() => {
      setLoadingStageIdx((prev) => (prev + 1) % LOADING_STAGES.length);
    }, 1200);
    return () => clearInterval(interval);
  }, [isAnalyzing]);

  const isConversationActive = messages.length > 0;

  return (
    <div className="workspace-main">
      {/* Top Bar */}
      <header className="workspace-topbar">
        <div className="topbar-left">
          <button
            className="sidebar-toggle-btn"
            onClick={onToggleSidebar}
            title="Toggle Sidebar"
          >
            <Menu size={18} />
          </button>
          <div className="topbar-title">SatQuery AI Analysis Workspace</div>
        </div>

        <div className="topbar-right">
          {onToggleViewMode && (
            <button
              className="mode-switch-btn"
              onClick={onToggleViewMode}
              title="Switch to Interactive Map Workspace"
            >
              <Map size={14} />
              <span>Map Workspace</span>
            </button>
          )}

          <div className="status-badge">
            <div className="status-badge-dot" />
            <span>
              {systemStatus?.status === 'healthy' ? 'API Ready' : 'Backend Ready'}
            </span>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      {!isConversationActive ? (
        /* Empty State / New Analysis View */
        <div className="chat-scroll-area empty-scroll-area">
          <EmptyWorkspace
            attachments={attachments}
            queryText={queryText}
            setQueryText={setQueryText}
            onAddFiles={onAddFiles}
            onRemoveFile={onRemoveFile}
            onToggleModality={onToggleModality}
            onSend={onSend}
            isAnalyzing={isAnalyzing}
          />
        </div>
      ) : (
        /* Active Conversation Stream */
        <>
          <div className="chat-scroll-area">
            <div className="chat-content-max">
              {messages.map((msg, idx) => (
                <Message key={idx} message={msg} />
              ))}

              {/* Loading Indicator */}
              {isAnalyzing && (
                <div className="message-block message-assistant animate-fade-in">
                  <div
                    className="assistant-response-container"
                    style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}
                  >
                    <Loader2
                      size={20}
                      className="animate-spin"
                      style={{
                        color: 'var(--accent-primary)',
                        animation: 'spin 1s linear infinite',
                      }}
                    />
                    <div>
                      <div
                        style={{
                          fontSize: '0.9rem',
                          fontWeight: 600,
                          color: 'var(--text-primary)',
                        }}
                      >
                        Analyzing your satellite scene...
                      </div>
                      <div
                        style={{
                          fontSize: '0.78rem',
                          color: '#a5b4fc',
                          marginTop: '0.15rem',
                        }}
                        className="mono"
                      >
                        {LOADING_STAGES[loadingStageIdx]}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Fixed Bottom Composer during active conversation */}
          <Composer
            attachments={attachments}
            queryText={queryText}
            setQueryText={setQueryText}
            onAddFiles={onAddFiles}
            onRemoveFile={onRemoveFile}
            onToggleModality={onToggleModality}
            onSend={onSend}
            isAnalyzing={isAnalyzing}
          />
        </>
      )}
    </div>
  );
}
