import React, { useState } from 'react';
import { AlertCircle, CheckCircle2, ShieldAlert, Layers, Download, Eye, BrainCircuit } from 'lucide-react';
import EvidenceGallery from './EvidenceGallery';
import TechnicalDetails from './TechnicalDetails';
import FormattedEvidenceText from './FormattedEvidenceText';
import { extractOilSpillData, extractObservedInferred, getConfidencePercentage } from '../utils/formatters';
import { generatePdfReport } from '../utils/pdfReportGenerator';

function VisualEvidenceSection({ evidenceImages = [], observedText, inferredText }) {
  const hasContent = evidenceImages.length > 0 || Boolean(observedText) || Boolean(inferredText);
  if (!hasContent) return null;

  return (
    <div className="evidence-section">
      <div className="evidence-header-label">VISUAL EVIDENCE</div>

      {observedText && (
        <div className="evidence-text-card observed-card">
          <div className="evidence-sub-label">
            <Eye size={14} className="label-icon" />
            <span>OBSERVED EVIDENCE</span>
          </div>
          <FormattedEvidenceText text={observedText} type="observed" />
        </div>
      )}

      {inferredText && (
        <div className="evidence-text-card inferred-card">
          <div className="evidence-sub-label">
            <BrainCircuit size={14} className="label-icon" />
            <span>INFERRED INTELLIGENCE</span>
          </div>
          <FormattedEvidenceText text={inferredText} type="inferred" />
        </div>
      )}

      {evidenceImages.length > 0 && (
        <EvidenceGallery images={evidenceImages} />
      )}
    </div>
  );
}

function SavePdfButton({ onClick, isExporting }) {
  return (
    <button
      className="save-pdf-btn"
      onClick={onClick}
      disabled={isExporting}
      title="Save complete analysis report as a structured PDF"
    >
      <Download size={14} />
      <span>{isExporting ? 'Generating PDF...' : 'Save Report as PDF'}</span>
    </button>
  );
}

export default function AnalysisResult({
  data = {},
  observedText: propObserved,
  inferredText: propInferred,
}) {
  const [isExporting, setIsExporting] = useState(false);

  const handleExportPdf = async () => {
    try {
      setIsExporting(true);
      await generatePdfReport(data);
    } catch (err) {
      console.error('Failed to generate PDF report:', err);
    } finally {
      setIsExporting(false);
    }
  };

  const task = (data.task || '').toLowerCase();
  const trace = data.execution_trace || {};
  const evidenceImages = data.evidence?.images || [];
  const changeMetrics = data.change_metrics;

  const { observedText: llmObserved, inferredText: llmInferred } = extractObservedInferred(data.answer);
  const { observedText: rawObserved, inferredText: rawInferred } = extractObservedInferred(data.raw_answer || data.answer);

  const observedText = propObserved || llmObserved;
  const inferredText = propInferred || llmInferred;
  const confidencePct = getConfidencePercentage(data);

  const isOilSpill =
    task === 'oil_spill' ||
    (data.answer && /oil-spill candidate/i.test(data.answer));

  // 1. Oil Spill Task
  if (isOilSpill) {
    const {
      isDetected,
      candidateCount,
      affectedPixels,
      seaCoverage,
      analysisMode,
      regions,
    } = extractOilSpillData(data);

    const totalAreaKm2 = regions.reduce((acc, r) => acc + (r.area_km2 || 0), 0);
    const hasKm2 = regions.some(
      (r) => r.area_km2 !== undefined && r.area_km2 !== null
    );

    return (
      <div className="analysis-result-box oil-spill-result">
        <div className="result-card-header">
          <div className="result-card-header-info">
            <div className="result-title">
              {isDetected ? (
                <>
                  <ShieldAlert size={20} style={{ color: '#f59e0b' }} />
                  <span>Potential oil-spill candidate detected</span>
                </>
              ) : (
                <>
                  <CheckCircle2 size={20} style={{ color: 'var(--success)' }} />
                  <span>No potential oil-spill candidates detected</span>
                </>
              )}
            </div>
            <div className="result-subtitle">{analysisMode}</div>
          </div>
          <SavePdfButton onClick={handleExportPdf} isExporting={isExporting} />
        </div>

        <div className="oil-spill-summary-text">
          {isDetected
            ? `${candidateCount} candidate region${
                candidateCount > 1 ? 's' : ''
              } identified across ${seaCoverage}% of the analyzed sea surface.`
            : `0 candidate regions identified across the analyzed sea surface.`}
        </div>

        {/* Metrics Grid */}
        <div className="metrics-row">
          <div className="metric-pill">
            <span className="metric-label">Confidence Score</span>
            <span className="metric-val" style={{ color: '#818cf8', fontWeight: 800 }}>
              {confidencePct}%
            </span>
          </div>
          <div className="metric-pill">
            <span className="metric-label">Candidate Regions</span>
            <span className="metric-val">{candidateCount}</span>
          </div>
          <div className="metric-pill">
            <span className="metric-label">Affected Pixels</span>
            <span className="metric-val">{affectedPixels.toLocaleString()}</span>
          </div>
          <div className="metric-pill">
            <span className="metric-label">Sea Surface Coverage</span>
            <span className="metric-val">{seaCoverage}%</span>
          </div>
          {hasKm2 && (
            <div className="metric-pill">
              <span className="metric-label">Estimated Area</span>
              <span className="metric-val">~{totalAreaKm2.toFixed(2)} km²</span>
            </div>
          )}
        </div>

        {/* Visual Evidence Section (LLM Brief Summary) */}
        <VisualEvidenceSection
          evidenceImages={evidenceImages}
          observedText={observedText}
          inferredText={inferredText}
        />

        {/* Scientific Warning Disclaimer */}
        <div className="scientific-warning-banner">
          <AlertCircle size={16} className="warning-icon" />
          <span>
            Dark SAR regions can also result from calm water, wind shadows and other look-alikes; expert verification is required.
          </span>
        </div>

        {/* Technical Details (Raw Telemetry Observation) */}
        <TechnicalDetails
          data={data}
          trace={trace}
          observedText={rawObserved}
          inferredText={rawInferred}
        />
      </div>
    );
  }

  // 2. Change Detection Task
  if (task.includes('change') || changeMetrics) {
    const cm = changeMetrics || {};
    const changePct = cm.change_percentage ?? data.change_percentage ?? 0;
    const changedPixels = cm.changed_pixels ?? data.changed_pixels ?? 0;
    const vegLoss =
      cm.vegetation_loss_percentage ?? data.vegetation_loss_percentage ?? 0;
    const vegGain =
      cm.vegetation_gain_percentage ?? data.vegetation_gain_percentage ?? 0;
    const wm = cm.water_analysis || data.water_analysis;

    return (
      <div className="analysis-result-box">
        <div className="result-card-header">
          <div className="result-card-header-info">
            <div className="result-title">
              <Layers size={20} style={{ color: 'var(--accent-primary)' }} />
              <span>Bi-Temporal Change Analysis</span>
            </div>
            <div className="result-subtitle">
              Spectral Divergence & Spatial Registration Engine
            </div>
          </div>
          <SavePdfButton onClick={handleExportPdf} isExporting={isExporting} />
        </div>

        <div className="metrics-row">
          <div className="metric-pill">
            <span className="metric-label">Confidence Score</span>
            <span className="metric-val" style={{ color: '#818cf8', fontWeight: 800 }}>
              {confidencePct}%
            </span>
          </div>
          <div className="metric-pill">
            <span className="metric-label">Total Change</span>
            <span className="metric-val">{changePct}%</span>
          </div>
          <div className="metric-pill">
            <span className="metric-label">Changed Pixels</span>
            <span className="metric-val">{changedPixels.toLocaleString()}</span>
          </div>
          <div className="metric-pill">
            <span className="metric-label">Veg Loss</span>
            <span
              className="metric-val"
              style={{ color: vegLoss > 0 ? '#ef4444' : 'inherit' }}
            >
              {vegLoss}%
            </span>
          </div>
          <div className="metric-pill">
            <span className="metric-label">Veg Gain</span>
            <span
              className="metric-val"
              style={{ color: vegGain > 0 ? '#10b981' : 'inherit' }}
            >
              {vegGain}%
            </span>
          </div>
        </div>

        {/* Structured Water Change Section */}
        {wm && (
          <div className="water-change-card-section" style={{ marginTop: '0.85rem' }}>
            <div
              className="water-change-header"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '0.4rem',
              }}
            >
              <span
                className="water-change-title"
                style={{
                  fontSize: '0.78rem',
                  fontWeight: 800,
                  color: 'var(--text-primary)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px',
                }}
              >
                WATER CHANGE
              </span>
              <span
                className="water-method-badge"
                style={{
                  fontSize: '0.68rem',
                  fontWeight: 700,
                  padding: '0.15rem 0.55rem',
                  borderRadius: '4px',
                  background: 'rgba(99, 102, 241, 0.15)',
                  color: '#a5b4fc',
                  border: '1px solid rgba(99, 102, 241, 0.3)',
                }}
              >
                {wm.mode === 'ndwi'
                  ? 'Method: NDWI-based water analysis'
                  : 'Method: RGB water-change screening'}
              </span>
            </div>

            <div className="metrics-row">
              <div className="metric-pill">
                <span className="metric-label">Water Gain</span>
                <span
                  className="metric-val"
                  style={{ color: wm.gain_percentage > 0 ? '#38bdf8' : 'inherit' }}
                >
                  {wm.gain_percentage}%
                </span>
              </div>
              <div className="metric-pill">
                <span className="metric-label">Water Loss</span>
                <span
                  className="metric-val"
                  style={{ color: wm.loss_percentage > 0 ? '#ef4444' : 'inherit' }}
                >
                  {wm.loss_percentage}%
                </span>
              </div>
              <div className="metric-pill">
                <span className="metric-label">Water Changed</span>
                <span
                  className="metric-val"
                  style={{ color: wm.changed_percentage > 0 ? '#6366f1' : 'inherit' }}
                >
                  {wm.changed_percentage}%
                </span>
              </div>
            </div>
          </div>
        )}

        <VisualEvidenceSection
          evidenceImages={evidenceImages}
          observedText={observedText}
          inferredText={inferredText}
        />
        <TechnicalDetails
          data={data}
          trace={trace}
          observedText={rawObserved}
          inferredText={rawInferred}
        />
      </div>
    );
  }

  // 3. Grounding / Highlight Task
  if (task === 'grounding' || data.regions) {
    const regionCount = (data.evidence?.regions || data.regions || []).length;
    const targetType = (data.target_analysis?.target_type || '').toLowerCase();

    let hasTargetMask = false;
    if (targetType === 'vegetation') {
      hasTargetMask = evidenceImages.some((img) => img.url?.includes('vegetation_mask.png'));
    } else if (targetType === 'water') {
      hasTargetMask = evidenceImages.some((img) => img.url?.includes('water_mask.png'));
    } else if (targetType === 'built_up') {
      hasTargetMask = evidenceImages.some((img) => img.url?.includes('built_up_mask.png'));
    } else {
      hasTargetMask = evidenceImages.some(
        (img) => img.url?.includes('mask.png') && !img.url?.includes('change')
      );
    }

    return (
      <div className="analysis-result-box">
        <div className="result-card-header">
          <div className="result-card-header-info">
            <div className="result-title">
              <Layers size={20} style={{ color: 'var(--accent-primary)' }} />
              <span>Target Grounding & Segmentation</span>
            </div>
            {regionCount > 0 && (
              <div className="result-subtitle">
                {regionCount} target region(s) identified & segment highlighted
              </div>
            )}
          </div>
          <SavePdfButton onClick={handleExportPdf} isExporting={isExporting} />
        </div>

        <div className="metrics-row">
          <div className="metric-pill">
            <span className="metric-label">Confidence Score</span>
            <span className="metric-val" style={{ color: '#818cf8', fontWeight: 800 }}>
              {confidencePct}%
            </span>
          </div>
          <div className="metric-pill">
            <span className="metric-label">Identified Regions</span>
            <span className="metric-val">{regionCount}</span>
          </div>
          {data.vegetation_analysis?.vegetation_percentage !== undefined && (
            <div className="metric-pill">
              <span className="metric-label">Vegetation Coverage</span>
              <span className="metric-val" style={{ color: '#10b981' }}>
                {data.vegetation_analysis.vegetation_percentage}%
              </span>
            </div>
          )}
          {data.built_up_analysis?.built_up_percentage !== undefined && (
            <div className="metric-pill">
              <span className="metric-label">Built-up Coverage</span>
              <span className="metric-val" style={{ color: '#f97316' }}>
                {data.built_up_analysis.built_up_percentage}%
              </span>
            </div>
          )}
          {hasTargetMask && (
            <div className="metric-pill">
              <span className="metric-label">Segmentation Mask</span>
              <span className="metric-val" style={{ color: 'var(--success)' }}>
                Active
              </span>
            </div>
          )}
        </div>

        <VisualEvidenceSection
          evidenceImages={evidenceImages}
          observedText={observedText}
          inferredText={inferredText}
        />
        <TechnicalDetails
          data={data}
          trace={trace}
          observedText={rawObserved}
          inferredText={rawInferred}
        />
      </div>
    );
  }

  // 4. Default / VQA / Caption / Water / Optical+SAR
  return (
    <div className="analysis-result-box">
      <div className="result-card-header">
        <div className="result-card-header-info">
          <div className="result-title">
            <Layers size={20} style={{ color: 'var(--accent-primary)' }} />
            <span>Satellite Remote Sensing Analysis</span>
          </div>
          <div className="result-subtitle">
            Multimodal Satellite Vision & Technical Analysis Report
          </div>
        </div>
        <SavePdfButton onClick={handleExportPdf} isExporting={isExporting} />
      </div>

      <div className="metrics-row">
        <div className="metric-pill">
          <span className="metric-label">Confidence Score</span>
          <span className="metric-val" style={{ color: '#818cf8', fontWeight: 800 }}>
            {confidencePct}%
          </span>
        </div>
        <div className="metric-pill">
          <span className="metric-label">Pipeline Task</span>
          <span className="metric-val">{(data.task || 'Analysis').toUpperCase()}</span>
        </div>
      </div>

      <VisualEvidenceSection
        evidenceImages={evidenceImages}
        observedText={observedText}
        inferredText={inferredText}
      />
      <TechnicalDetails
        data={data}
        trace={trace}
        observedText={rawObserved}
        inferredText={rawInferred}
      />
    </div>
  );
}
