import React from 'react';
import AnalysisResult from './AnalysisResult';
import { extractObservedInferred } from '../utils/formatters';

export default function Message({ message }) {
  const isUser = message.role === 'user';

  if (isUser) {
    return (
      <div className="message-block message-user animate-fade-in">
        <div className="user-bubble">
          {message.attachments && message.attachments.length > 0 && (
            <div className="user-attachments-grid">
              {message.attachments.map((att, idx) => (
                <div key={idx} style={{ position: 'relative' }}>
                  {att.thumbUrl ? (
                    <img src={att.thumbUrl} alt={att.name} className="user-attached-thumb" />
                  ) : (
                    <div
                      className="user-attached-thumb"
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '0.75rem',
                        fontWeight: 700,
                        color: '#a5b4fc',
                      }}
                    >
                      TIFF
                    </div>
                  )}
                  <div
                    style={{
                      position: 'absolute',
                      bottom: '4px',
                      left: '4px',
                      right: '4px',
                      background: 'rgba(0,0,0,0.7)',
                      borderRadius: '4px',
                      padding: '2px 4px',
                      fontSize: '0.62rem',
                      color: '#fff',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {att.name}
                  </div>
                </div>
              ))}
            </div>
          )}
          <div>{message.text}</div>
        </div>
      </div>
    );
  }

  // Assistant Message
  const data = message.data || {};
  const answerText = data.answer || message.text || '';
  const task = (data.task || '').toLowerCase();
  const isOilSpill =
    task === 'oil_spill' ||
    (answerText && /oil-spill candidate/i.test(answerText));

  // Extract main text (stripping OBSERVED / INFERRED and markdown markers)
  const { mainText, observedText, inferredText } = extractObservedInferred(answerText);

  return (
    <div className="message-block message-assistant animate-fade-in">
      <div className="assistant-response-container">
        {!isOilSpill && mainText && (
          <div className="assistant-text" style={{ whiteSpace: 'pre-wrap' }}>
            {mainText}
          </div>
        )}
        <AnalysisResult
          data={data}
          observedText={observedText}
          inferredText={inferredText}
        />
      </div>
    </div>
  );
}
