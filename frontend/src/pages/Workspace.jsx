import React, { useState, useEffect } from 'react';
import Sidebar from '../components/Sidebar';
import Chat from '../components/Chat';
import MapWorkspace from '../components/Map/MapWorkspace';
import { analyzeScene, fetchHealth } from '../api/satquery';
import '../styles/workspace.css';

export default function Workspace() {
  const [activeView, setActiveView] = useState('map'); // 'map' or 'upload'
  const [sessions, setSessions] = useState([
    {
      id: 'session-1',
      title: 'New Analysis',
      messages: [],
    },
  ]);
  const [activeSessionId, setActiveSessionId] = useState('session-1');

  const [attachments, setAttachments] = useState([]);
  const [queryText, setQueryText] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [systemStatus, setSystemStatus] = useState({ status: 'healthy' });
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  // Poll backend health status
  useEffect(() => {
    fetchHealth().then(setSystemStatus);
    const interval = setInterval(() => {
      fetchHealth().then(setSystemStatus);
    }, 15000);
    return () => clearInterval(interval);
  }, []);

  const activeSession = sessions.find((s) => s.id === activeSessionId) || sessions[0];

  const handleNewAnalysis = () => {
    const newId = `session-${Date.now()}`;
    const newSession = {
      id: newId,
      title: 'New Analysis',
      messages: [],
    };
    setSessions((prev) => [newSession, ...prev]);
    setActiveSessionId(newId);
    setAttachments([]);
    setQueryText('');
  };

  const handleAddFiles = (files) => {
    const newAttachments = files.slice(0, 2 - attachments.length).map((f) => {
      const fnameLower = f.name.toLowerCase();
      const isGeoTIFF =
        fnameLower.endsWith('.tif') ||
        fnameLower.endsWith('.tiff') ||
        fnameLower.endsWith('.geotiff');
      const isSarFilename =
        fnameLower.includes('sar') ||
        fnameLower.includes('sentinel1') ||
        fnameLower.includes('s1') ||
        fnameLower.includes('vv') ||
        fnameLower.includes('vh') ||
        fnameLower.includes('radar');

      const defaultModality = isSarFilename ? 'sar' : 'optical';
      const thumbUrl = !isGeoTIFF ? URL.createObjectURL(f) : null;

      return {
        file: f,
        name: f.name,
        size: (f.size / (1024 * 1024)).toFixed(2) + ' MB',
        modality: defaultModality,
        thumbUrl,
      };
    });

    setAttachments((prev) => [...prev, ...newAttachments].slice(0, 2));
  };

  const handleRemoveFile = (index) => {
    setAttachments((prev) => prev.filter((_, i) => i !== index));
  };

  const handleToggleModality = (index, mod) => {
    setAttachments((prev) =>
      prev.map((att, i) => (i === index ? { ...att, modality: mod } : att))
    );
  };

  const handleSend = async () => {
    const q = queryText.trim();
    if (!q && attachments.length === 0) return;

    if (attachments.length === 0) {
      alert('Please attach at least 1 satellite image before analyzing.');
      return;
    }
    if (!q) {
      alert('Please enter a query or question about your satellite imagery.');
      return;
    }

    const userMessage = {
      role: 'user',
      text: q,
      attachments: attachments.map((a) => ({
        name: a.name,
        thumbUrl: a.thumbUrl,
        modality: a.modality,
      })),
    };

    // Update messages in active session
    setSessions((prev) =>
      prev.map((s) => {
        if (s.id === activeSessionId) {
          const updatedTitle =
            s.title === 'New Analysis' ? q.slice(0, 32) + (q.length > 32 ? '...' : '') : s.title;
          return {
            ...s,
            title: updatedTitle,
            messages: [...s.messages, userMessage],
          };
        }
        return s;
      })
    );

    const filesToSend = attachments.map((a) => a.file);
    const modalitiesToSend = attachments.map((a) => a.modality);

    // Clear composer
    setQueryText('');
    setAttachments([]);
    setIsAnalyzing(true);

    try {
      const data = await analyzeScene({
        files: filesToSend,
        query: q,
        modalities: modalitiesToSend,
      });

      const assistantMessage = {
        role: 'assistant',
        data,
      };

      setSessions((prev) =>
        prev.map((s) =>
          s.id === activeSessionId
            ? { ...s, messages: [...s.messages, assistantMessage] }
            : s
        )
      );
    } catch (err) {
      const errorMessage = {
        role: 'assistant',
        data: {
          answer: `OBSERVED: Analysis execution failed.\nINFERRED: ${err.message}`,
          task: 'error',
          status_text: 'Status: Error',
          input_badge: 'Input: Request Error',
          evidence: { images: [] },
        },
      };

      setSessions((prev) =>
        prev.map((s) =>
          s.id === activeSessionId
            ? { ...s, messages: [...s.messages, errorMessage] }
            : s
        )
      );
    } finally {
      setIsAnalyzing(false);
    }
  };

  const toggleViewMode = () => {
    setActiveView((v) => (v === 'map' ? 'upload' : 'map'));
  };

  if (activeView === 'map') {
    return (
      <MapWorkspace
        systemStatus={systemStatus}
        activeView={activeView}
        onToggleViewMode={toggleViewMode}
      />
    );
  }

  return (
    <div className="workspace-layout">
      <Sidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={setActiveSessionId}
        onNewAnalysis={handleNewAnalysis}
        isOpen={isSidebarOpen}
        activeView={activeView}
        onToggleViewMode={toggleViewMode}
      />

      <Chat
        messages={activeSession.messages}
        attachments={attachments}
        queryText={queryText}
        setQueryText={setQueryText}
        onAddFiles={handleAddFiles}
        onRemoveFile={handleRemoveFile}
        onToggleModality={handleToggleModality}
        onSend={handleSend}
        isAnalyzing={isAnalyzing}
        onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)}
        systemStatus={systemStatus}
        onToggleViewMode={toggleViewMode}
      />
    </div>
  );
}
