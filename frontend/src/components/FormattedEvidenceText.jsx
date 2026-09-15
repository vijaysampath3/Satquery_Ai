import React from 'react';

/**
 * Parses markdown inline formatting (**bold**, *italic*, `code`)
 */
function parseMarkdownInline(str) {
  if (!str) return null;
  const parts = [];
  const regex = /(\*\*.*?\*\*|\*.*?\*|`.*?`)/g;
  let lastIdx = 0;
  let match;

  while ((match = regex.exec(str)) !== null) {
    if (match.index > lastIdx) {
      parts.push(str.substring(lastIdx, match.index));
    }
    const token = match[0];
    if (token.startsWith('**') && token.endsWith('**')) {
      parts.push(
        <strong key={match.index} className="formatted-bold-text">
          {token.slice(2, -2)}
        </strong>
      );
    } else if (token.startsWith('*') && token.endsWith('*')) {
      parts.push(
        <em key={match.index} className="formatted-italic-text">
          {token.slice(1, -1)}
        </em>
      );
    } else if (token.startsWith('`') && token.endsWith('`')) {
      parts.push(
        <code key={match.index} className="formatted-code-text">
          {token.slice(1, -1)}
        </code>
      );
    }
    lastIdx = regex.lastIndex;
  }
  if (lastIdx < str.length) {
    parts.push(str.substring(lastIdx));
  }

  return parts.length > 0 ? parts : str;
}

export default function FormattedEvidenceText({ text, type = 'observed' }) {
  if (!text) return null;

  const rawLines = text.split('\n');
  const items = [];

  rawLines.forEach((rawLine, idx) => {
    const trimmed = rawLine.trim();
    if (!trimmed) return;

    // Check indentation level for sub-bullets
    const leadingSpaces = rawLine.search(/\S/);
    const isSubItem = leadingSpaces >= 2 || rawLine.startsWith('  ') || rawLine.startsWith('\t');

    // Check bullet types
    let lineText = trimmed;
    let isBullet = false;
    let isNumbered = false;
    let stepNumber = null;

    if (/^[-*•]\s+/.test(lineText)) {
      isBullet = true;
      lineText = lineText.replace(/^[-*•]\s+/, '');
    } else if (/^\d+\.\s+/.test(lineText)) {
      isNumbered = true;
      const numMatch = lineText.match(/^(\d+)\.\s+/);
      stepNumber = numMatch ? numMatch[1] : null;
      lineText = lineText.replace(/^\d+\.\s+/, '');
    }

    // Extract title prefix if present (e.g. "**Title**: rest" or "Title: rest")
    let titlePrefix = null;
    let bodyText = lineText;

    const boldTitleMatch = lineText.match(/^(\*\*.*?\*\*|\*.*?\*)\s*:\s*(.*)/);
    const plainTitleMatch = lineText.match(/^([A-Z][A-Za-z0-9\s/&()'-]{2,40}):\s*(.*)/);

    if (boldTitleMatch) {
      titlePrefix = boldTitleMatch[1].replace(/\*/g, '');
      bodyText = boldTitleMatch[2];
    } else if (plainTitleMatch && !isSubItem) {
      titlePrefix = plainTitleMatch[1];
      bodyText = plainTitleMatch[2];
    }

    items.push({
      id: idx,
      isSubItem,
      isBullet,
      isNumbered,
      stepNumber,
      titlePrefix,
      bodyText,
      rawLine: trimmed,
    });
  });

  const accentColor = type === 'observed' ? '#818cf8' : '#34d399';

  return (
    <div className={`formatted-evidence-container type-${type}`}>
      {items.map((item) => {
        if (item.isSubItem) {
          return (
            <div key={item.id} className="formatted-sub-item">
              <div className="sub-item-indicator" style={{ background: accentColor }} />
              <div className="sub-item-content">
                {item.titlePrefix && (
                  <span className="item-title-tag">{item.titlePrefix}: </span>
                )}
                {parseMarkdownInline(item.bodyText)}
              </div>
            </div>
          );
        }

        return (
          <div key={item.id} className="formatted-main-item">
            {item.isNumbered ? (
              <span className="step-num-badge" style={{ borderColor: accentColor, color: accentColor }}>
                {item.stepNumber}
              </span>
            ) : (
              <span className="main-item-dot" style={{ background: accentColor }} />
            )}
            <div className="main-item-content">
              {item.titlePrefix && (
                <span className="item-title-tag">{item.titlePrefix}: </span>
              )}
              {parseMarkdownInline(item.bodyText)}
            </div>
          </div>
        );
      })}
    </div>
  );
}
