/**
 * Utility functions for text sanitization and structured data extraction.
 */

export function stripMarkdown(str) {
  if (!str) return '';
  return str
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/\*(.*?)\*/g, '$1')
    .replace(/`(.*?)`/g, '$1')
    .replace(/#{1,6}\s?/g, '')
    .trim();
}

export function extractObservedInferred(text) {
  if (!text) return { mainText: '', observedText: '', inferredText: '' };

  const cleanText = stripMarkdown(text);

  const obsIndex = cleanText.search(/OBSERVED:/i);
  const infIndex = cleanText.search(/INFERRED:/i);

  let firstIndex = -1;
  if (obsIndex !== -1 && infIndex !== -1) {
    firstIndex = Math.min(obsIndex, infIndex);
  } else if (obsIndex !== -1) {
    firstIndex = obsIndex;
  } else if (infIndex !== -1) {
    firstIndex = infIndex;
  }

  let mainText = cleanText;
  if (firstIndex !== -1) {
    mainText = cleanText.slice(0, firstIndex).trim();
  }

  let observedText = '';
  const obsMatch = cleanText.match(/OBSERVED:\s*([\s\S]*?)(?=INFERRED:|$)/i);
  if (obsMatch) {
    observedText = obsMatch[1].trim();
  }

  let inferredText = '';
  const infMatch = cleanText.match(/INFERRED:\s*([\s\S]*?)$/i);
  if (infMatch) {
    inferredText = infMatch[1].trim();
  }

  return {
    mainText,
    observedText,
    inferredText,
  };
}

export function extractOilSpillData(data = {}) {
  const regions = data.evidence?.regions || data.regions || [];

  // 1. Candidate count
  let candidateCount = data.candidate_count;
  if (candidateCount === undefined || candidateCount === null) {
    const matchCount =
      data.answer?.match(/Identified Candidates:\s*\**(\d+)\**/i) ||
      data.answer?.match(/(\d+)\s*candidate region/i) ||
      data.answer?.match(/(\d+)\s*potential oil-spill/i);
    if (matchCount) {
      candidateCount = parseInt(matchCount[1], 10);
    } else {
      candidateCount = regions.length;
    }
  }

  // 2. Is detected
  let isDetected;
  if (data.detected !== undefined && data.detected !== null) {
    isDetected = Boolean(data.detected);
  } else {
    isDetected = candidateCount > 0;
  }

  if (!isDetected) {
    candidateCount = 0;
  } else if (candidateCount === 0) {
    isDetected = false;
  }

  // 3. Affected pixel count
  let affectedPixels = data.affected_pixel_count;
  if (affectedPixels === undefined || affectedPixels === null) {
    const matchPixels =
      data.answer?.match(/Affected (?:Area|Pixel Count):\s*\**([\d,]+)\**/i) ||
      data.answer?.match(/([\d,]+)\s*pixels/i);
    if (matchPixels) {
      affectedPixels = parseInt(matchPixels[1].replace(/,/g, ''), 10);
    } else if (regions.length > 0 && isDetected) {
      affectedPixels = regions.reduce((sum, r) => sum + (r.pixel_count || 0), 0);
    } else {
      affectedPixels = 0;
    }
  }
  if (!isDetected) affectedPixels = 0;

  // 4. Sea surface coverage percentage
  let seaCoverage = data.affected_percentage;
  if (seaCoverage === undefined || seaCoverage === null) {
    const matchCoverage =
      data.answer?.match(/Sea Surface Coverage:\s*\**([\d.]+)\%\**/i) ||
      data.answer?.match(/([\d.]+)\%\s*of (?:analyzed )?sea/i) ||
      data.answer?.match(/across\s*([\d.]+)\%\s*of/i);
    if (matchCoverage) {
      seaCoverage = parseFloat(matchCoverage[1]);
    } else {
      seaCoverage = 0;
    }
  }
  if (!isDetected) seaCoverage = 0;

  // 5. Analysis mode
  let analysisMode = data.analysis_mode;
  if (!analysisMode) {
    const matchMode = data.answer?.match(/Analysis mode:\s*([^\)\n]+)/i);
    if (matchMode) {
      analysisMode = matchMode[1].trim();
    } else {
      analysisMode = 'Sentinel-1 SAR visual screening';
    }
  }

  return {
    isDetected,
    candidateCount,
    affectedPixels,
    seaCoverage,
    analysisMode,
    regions,
  };
}

export function getConfidencePercentage(data = {}) {
  let conf = data.confidence;
  if (conf === undefined || conf === null) {
    conf = data.execution_trace?.task_confidence;
  }
  if (conf === undefined || conf === null) {
    conf = 0.94;
  }
  if (typeof conf === 'number') {
    if (conf <= 1.0) {
      return Math.round(conf * 100);
    }
    return Math.round(conf);
  }
  return 94;
}
