import React, { useRef } from 'react';
import { Paperclip, Send, X } from 'lucide-react';

export default function Composer({
  attachments,
  queryText,
  setQueryText,
  onAddFiles,
  onRemoveFile,
  onToggleModality,
  onSend,
  isAnalyzing,
}) {
  const fileInputRef = useRef(null);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      onAddFiles(Array.from(e.target.files));
      e.target.value = '';
    }
  };

  return (
    <div className="composer-wrapper">
      <div className="composer-box">
        {/* Attachments Preview Area */}
        {attachments && attachments.length > 0 && (
          <div className="composer-attachments-bar">
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
                <div key={idx} className="attachment-chip">
                  {att.thumbUrl ? (
                    <img src={att.thumbUrl} alt={att.name} className="attachment-thumb" />
                  ) : (
                    <div
                      className="attachment-thumb"
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: '#a5b4fc',
                        fontWeight: 700,
                        fontSize: '0.7rem',
                      }}
                    >
                      TIFF
                    </div>
                  )}

                  <div className="attachment-info">
                    <span className="attachment-name" title={att.name}>
                      {att.name}
                    </span>
                    <span className="attachment-type-badge">{badgeText}</span>

                    <div className="modality-btn-toggle">
                      <button
                        type="button"
                        className={`mod-toggle-pill ${!isSar ? 'active' : ''}`}
                        onClick={() => onToggleModality(idx, 'optical')}
                      >
                        OPTICAL
                      </button>
                      <button
                        type="button"
                        className={`mod-toggle-pill ${isSar ? 'active' : ''}`}
                        onClick={() => onToggleModality(idx, 'sar')}
                      >
                        SAR
                      </button>
                    </div>
                  </div>

                  <button
                    type="button"
                    className="attachment-remove-btn"
                    onClick={() => onRemoveFile(idx)}
                    title="Remove attachment"
                  >
                    <X size={14} />
                  </button>
                </div>
              );
            })}
          </div>
        )}

        {/* Input Row */}
        <div className="composer-input-row">
          <input
            type="file"
            ref={fileInputRef}
            style={{ display: 'none' }}
            accept=".tif,.tiff,.geotiff,.png,.jpg,.jpeg"
            multiple
            onChange={handleFileChange}
          />

          <button
            type="button"
            className="attach-btn"
            onClick={() => fileInputRef.current?.click()}
            title="Attach satellite image (.tif, .png, .jpg)"
          >
            <Paperclip size={18} />
          </button>

          <textarea
            className="composer-textarea"
            placeholder="Ask anything about your satellite image..."
            rows={1}
            value={queryText}
            onChange={(e) => setQueryText(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isAnalyzing}
          />

          <button
            type="button"
            className="send-btn"
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
