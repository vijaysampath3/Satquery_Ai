import React, { useRef, useState } from 'react';
import { UploadCloud, Sparkles, Paperclip, Send, X, Plus } from 'lucide-react';

const SUGGESTED_QUESTIONS = [
  'Describe this image',
  'Highlight water',
  'Detect changes',
  'Highlight built-up areas',
  'Analyze Optical + SAR',
  'Detect oil spills',
];

export default function EmptyWorkspace({
  attachments = [],
  queryText,
  setQueryText,
  onAddFiles,
  onRemoveFile,
  onToggleModality,
  onSend,
  isAnalyzing,
}) {
  const fileInputRef = useRef(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onAddFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      onAddFiles(Array.from(e.target.files));
      e.target.value = '';
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  return (
    <div className="empty-workspace-container animate-fade-in">
      <input
        type="file"
        ref={fileInputRef}
        style={{ display: 'none' }}
        accept=".tif,.tiff,.geotiff,.png,.jpg,.jpeg"
        multiple
        onChange={handleFileChange}
      />

      {/* Header */}
      <div className="empty-workspace-header">
        <h1 className="empty-title">Analyze a scene</h1>
        <p className="empty-subtitle">
          Upload satellite imagery and ask SatQuery what you want to know.
        </p>
      </div>

      {/* Upload Card Dropzone */}
      <div
        className={`upload-card-dropzone ${isDragOver ? 'drag-over' : ''} ${
          attachments.length > 0 ? 'has-attachments' : ''
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <div className="upload-card-dashed-inner">
          {attachments.length === 0 ? (
            /* Prompt to Upload */
            <div
              className="upload-prompt-content"
              onClick={() => fileInputRef.current?.click()}
            >
              <div className="upload-icon-wrapper">
                <UploadCloud size={36} />
              </div>
              <div className="upload-main-text">Click or drag to upload</div>
              <div className="upload-sub-text">
                PNG, JPEG, TIFF, GeoTIFF · up to 10 MB
              </div>
              <button
                type="button"
                className="browse-files-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  fileInputRef.current?.click();
                }}
              >
                Browse files
              </button>
            </div>
          ) : (
            /* Attached Files List */
            <div className="uploaded-files-list">
              {attachments.map((att, idx) => {
                const isGeoTIFF =
                  att.name.toLowerCase().endsWith('.tif') ||
                  att.name.toLowerCase().endsWith('.tiff') ||
                  att.name.toLowerCase().endsWith('.geotiff');
                const isSar = att.modality === 'sar';

                let badgeText = isSar
                  ? isGeoTIFF
                    ? 'Sentinel-1 SAR GeoTIFF'
                    : 'Sentinel-1 SAR Visual'
                  : isGeoTIFF
                  ? 'Multispectral GeoTIFF'
                  : 'RGB Visual Image';

                return (
                  <div key={idx} className="empty-attached-item">
                    {att.thumbUrl ? (
                      <img
                        src={att.thumbUrl}
                        alt={att.name}
                        className="empty-attached-thumb"
                      />
                    ) : (
                      <div className="empty-attached-thumb tiff-placeholder">
                        TIFF
                      </div>
                    )}

                    <div className="empty-attached-info">
                      <div className="empty-attached-name" title={att.name}>
                        {att.name}
                      </div>
                      <div className="empty-attached-badge">{badgeText}</div>
                      <div className="empty-modality-toggle">
                        <button
                          type="button"
                          className={`mod-pill ${!isSar ? 'active' : ''}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            onToggleModality(idx, 'optical');
                          }}
                        >
                          OPTICAL
                        </button>
                        <button
                          type="button"
                          className={`mod-pill ${isSar ? 'active' : ''}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            onToggleModality(idx, 'sar');
                          }}
                        >
                          SAR
                        </button>
                      </div>
                    </div>

                    <button
                      type="button"
                      className="empty-attached-remove"
                      onClick={(e) => {
                        e.stopPropagation();
                        onRemoveFile(idx);
                      }}
                      title="Remove image"
                    >
                      <X size={16} />
                    </button>
                  </div>
                );
              })}

              {attachments.length < 2 && (
                <button
                  type="button"
                  className="add-more-image-btn"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <Plus size={14} />
                  <span>Add another image</span>
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Suggested Questions Section */}
      <div className="suggested-questions-section">
        <div className="suggested-label">Suggested questions</div>
        <div className="suggested-pills-row">
          {SUGGESTED_QUESTIONS.map((question, idx) => (
            <button
              key={idx}
              type="button"
              className="suggested-question-pill"
              onClick={() => setQueryText(question)}
            >
              <Sparkles size={12} className="sparkle-icon" />
              <span>{question}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Question Composer Card */}
      <div className="empty-composer-box">
        <div className="empty-composer-row">
          {attachments.length < 2 && (
            <button
              type="button"
              className="empty-attach-btn"
              onClick={() => fileInputRef.current?.click()}
              title="Attach image"
            >
              <Paperclip size={18} />
            </button>
          )}

          <textarea
            className="empty-composer-textarea"
            placeholder={
              attachments.length > 0
                ? 'Ask about your image...'
                : 'Ask anything about your satellite image...'
            }
            rows={1}
            value={queryText}
            onChange={(e) => setQueryText(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isAnalyzing}
          />

          <button
            type="button"
            className="empty-send-btn"
            onClick={onSend}
            disabled={isAnalyzing || (!queryText.trim() && attachments.length === 0)}
            title="Send query"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
