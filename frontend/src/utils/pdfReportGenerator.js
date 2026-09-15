import { jsPDF } from 'jspdf';
import { extractOilSpillData, extractObservedInferred, getConfidencePercentage } from './formatters';

/**
 * Converts image URL (relative or absolute) to base64 data URL for jsPDF.
 */
async function loadImageAsBase64(url) {
  if (!url) return null;
  try {
    let fullUrl = url;
    if (url.startsWith('/')) {
      fullUrl = window.location.origin + url;
    }
    const response = await fetch(fullUrl);
    const blob = await response.blob();
    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result);
      reader.onerror = () => resolve(null);
      reader.readAsDataURL(blob);
    });
  } catch (err) {
    console.warn('Failed to load image for PDF embedding:', url, err);
    return null;
  }
}

/**
 * Generates a clean, vector/text structured PDF report for SatQuery AI.
 * Contains Observed Evidence, Inferred Intelligence, Visual Evidence Images,
 * and Technical Pipeline Details.
 */
export async function generatePdfReport(data = {}) {
  const doc = new jsPDF({
    orientation: 'portrait',
    unit: 'mm',
    format: 'a4',
  });

  const pageWidth = 210;
  const pageHeight = 297;
  const marginX = 15;
  const contentWidth = pageWidth - marginX * 2; // 180mm
  let yPos = 0;

  function checkAddPage(requiredHeight = 20) {
    if (yPos + requiredHeight > pageHeight - 20) {
      doc.addPage();
      yPos = 20;
      return true;
    }
    return false;
  }

  const confidencePct = getConfidencePercentage(data);

  // 1. Top Header Banner
  doc.setFillColor(15, 23, 42); // slate 900
  doc.rect(0, 0, pageWidth, 28, 'F');

  doc.setTextColor(255, 255, 255);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(14);
  doc.text('SatQuery AI — Satellite Analysis Report', marginX, 12);

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(8.5);
  doc.setTextColor(148, 163, 184); // slate 400
  const timestampStr = new Date().toLocaleString();
  const taskName = (data.task || data.execution_trace?.detected_task || 'Analysis').toUpperCase();
  const execTime = data.execution_trace?.total_time_ms
    ? `${data.execution_trace.total_time_ms.toFixed(0)} ms`
    : 'N/A';
  doc.text(`Generated: ${timestampStr}   |   Task: ${taskName}   |   Exec Time: ${execTime}   |   Confidence: ${confidencePct}%`, marginX, 20);

  // Accent line below header
  doc.setFillColor(99, 102, 241); // indigo 500
  doc.rect(0, 28, pageWidth, 1.5, 'F');

  yPos = 38;

  // 2. Extract Data
  const task = (data.task || '').toLowerCase();
  const answerText = data.answer || '';
  const { mainText, observedText, inferredText } = extractObservedInferred(answerText);
  const evidenceImages = data.evidence?.images || [];
  const trace = data.execution_trace || {};

  // 3. Headline Status Card
  let headlineTitle = 'Satellite Remote Sensing Analysis';
  let headlineBgColor = [30, 41, 59]; // slate 800
  let headlineBorderColor = [51, 65, 85];

  const isOilSpill = task === 'oil_spill' || /oil-spill candidate/i.test(answerText);

  if (isOilSpill) {
    const spill = extractOilSpillData(data);
    headlineTitle = spill.isDetected
      ? `Potential Oil-Spill Candidate Detected (${spill.candidateCount} region(s) identified)`
      : `No Potential Oil-Spill Candidates Detected (0 regions identified)`;
    headlineBgColor = spill.isDetected ? [120, 53, 15] : [6, 78, 59]; // amber vs emerald
    headlineBorderColor = spill.isDetected ? [245, 158, 11] : [16, 185, 129];
  } else if (task.includes('change') || data.change_metrics) {
    headlineTitle = 'Bi-Temporal Change Analysis Report';
    headlineBgColor = [30, 58, 138];
    headlineBorderColor = [99, 102, 241];
  } else if (task === 'grounding' || data.regions) {
    const regCount = (data.evidence?.regions || data.regions || []).length;
    headlineTitle = `Target Grounding & Segmentation (${regCount} target region(s))`;
    headlineBgColor = [49, 46, 129];
    headlineBorderColor = [129, 140, 248];
  }

  // Draw headline card
  doc.setFillColor(...headlineBgColor);
  doc.rect(marginX, yPos, contentWidth, 14, 'F');
  doc.setDrawColor(...headlineBorderColor);
  doc.setLineWidth(0.4);
  doc.rect(marginX, yPos, contentWidth, 14, 'S');

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(10);
  doc.setTextColor(255, 255, 255);
  doc.text(headlineTitle, marginX + 4, yPos + 9);

  yPos += 20;

  // 4. Key Metrics Row (if present)
  const metrics = [
    { label: 'Confidence Score', val: `${confidencePct}%` }
  ];
  if (isOilSpill) {
    const spill = extractOilSpillData(data);
    metrics.push({ label: 'Candidate Regions', val: `${spill.candidateCount}` });
    metrics.push({ label: 'Affected Pixels', val: spill.affectedPixels.toLocaleString() });
    metrics.push({ label: 'Sea Coverage', val: `${spill.seaCoverage}%` });
  } else if (task.includes('change') || data.change_metrics) {
    const cm = data.change_metrics || {};
    metrics.push({ label: 'Total Change', val: `${cm.change_percentage ?? data.change_percentage ?? 0}%` });
    metrics.push({ label: 'Changed Pixels', val: (cm.changed_pixels ?? data.changed_pixels ?? 0).toLocaleString() });
    metrics.push({ label: 'Veg Loss', val: `${cm.vegetation_loss_percentage ?? 0}%` });
    metrics.push({ label: 'Veg Gain', val: `${cm.vegetation_gain_percentage ?? 0}%` });
  } else if (task === 'grounding' || data.regions) {
    const regCount = (data.evidence?.regions || data.regions || []).length;
    metrics.push({ label: 'Identified Regions', val: `${regCount}` });
    if (data.vegetation_analysis?.vegetation_percentage !== undefined) {
      metrics.push({ label: 'Veg Coverage', val: `${data.vegetation_analysis.vegetation_percentage}%` });
    }
    if (data.built_up_analysis?.built_up_percentage !== undefined) {
      metrics.push({ label: 'Built-up Coverage', val: `${data.built_up_analysis.built_up_percentage}%` });
    }
  } else {
    metrics.push({ label: 'Pipeline Task', val: taskName });
  }

  if (metrics.length > 0) {
    const itemWidth = (contentWidth - (metrics.length - 1) * 4) / metrics.length;
    metrics.forEach((m, idx) => {
      const x = marginX + idx * (itemWidth + 4);
      doc.setFillColor(241, 245, 249);
      doc.rect(x, yPos, itemWidth, 12, 'F');
      doc.setDrawColor(226, 232, 240);
      doc.rect(x, yPos, itemWidth, 12, 'S');

      doc.setFont('helvetica', 'bold');
      doc.setFontSize(7);
      doc.setTextColor(100, 116, 139);
      doc.text(m.label.toUpperCase(), x + 3, yPos + 4.5);

      doc.setFont('helvetica', 'bold');
      doc.setFontSize(9);
      doc.setTextColor(15, 23, 42);
      doc.text(m.val, x + 3, yPos + 9.5);
    });
    yPos += 18;
  }

  // Helper to draw structured evidence text box
  function drawEvidenceBox(sectionTitle, text, accentColor) {
    if (!text) return;
    checkAddPage(30);

    doc.setFont('helvetica', 'bold');
    doc.setFontSize(10);
    doc.setTextColor(15, 23, 42);
    doc.text(sectionTitle, marginX, yPos);
    yPos += 4;

    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8.5);
    const splitLines = doc.splitTextToSize(text, contentWidth - 10);
    const boxHeight = splitLines.length * 4.2 + 6;

    checkAddPage(boxHeight + 5);

    doc.setFillColor(248, 250, 252);
    doc.rect(marginX, yPos, contentWidth, boxHeight, 'F');

    doc.setFillColor(...accentColor);
    doc.rect(marginX, yPos, 2.5, boxHeight, 'F');

    doc.setDrawColor(226, 232, 240);
    doc.setLineWidth(0.2);
    doc.rect(marginX, yPos, contentWidth, boxHeight, 'S');

    doc.setTextColor(51, 65, 85);
    let lineY = yPos + 5;
    splitLines.forEach((line) => {
      doc.text(line, marginX + 6, lineY);
      lineY += 4.2;
    });

    yPos += boxHeight + 8;
  }

  // 5. Section 1: Observed Evidence
  if (observedText) {
    drawEvidenceBox('1. OBSERVED EVIDENCE', observedText, [99, 102, 241]); // Indigo
  }

  // 6. Section 2: Inferred Intelligence
  if (inferredText) {
    drawEvidenceBox('2. INFERRED INTELLIGENCE', inferredText, [16, 185, 129]); // Emerald
  }

  // Fallback summary if no structured observed/inferred text
  if (mainText && !observedText && !inferredText) {
    drawEvidenceBox('1. ANALYSIS SUMMARY', mainText, [71, 85, 105]);
  }

  // 7. Section 3: Visual Evidence (Images)
  if (evidenceImages.length > 0) {
    checkAddPage(30);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(10);
    doc.setTextColor(15, 23, 42);
    doc.text('3. VISUAL EVIDENCE', marginX, yPos);
    yPos += 6;

    for (let i = 0; i < evidenceImages.length; i++) {
      const imgObj = evidenceImages[i];
      const imgUrl = typeof imgObj === 'string' ? imgObj : imgObj.url;
      const imgLabel =
        typeof imgObj === 'object'
          ? imgObj.title || imgObj.type || `Visual Evidence #${i + 1}`
          : `Visual Evidence #${i + 1}`;

      const base64 = await loadImageAsBase64(imgUrl);
      if (base64) {
        const imgMaxW = contentWidth;
        const imgMaxH = 75;

        checkAddPage(imgMaxH + 14);

        try {
          doc.addImage(base64, 'PNG', marginX, yPos, imgMaxW, imgMaxH, undefined, 'FAST');

          doc.setFont('helvetica', 'normal');
          doc.setFontSize(8);
          doc.setTextColor(100, 116, 139);
          doc.text(`Figure ${i + 1}: ${imgLabel}`, marginX, yPos + imgMaxH + 4);

          yPos += imgMaxH + 10;
        } catch (e) {
          console.warn('Could not embed image in PDF:', e);
        }
      }
    }
  }

  // 8. Section 4: Technical Pipeline Details
  checkAddPage(40);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(10);
  doc.setTextColor(15, 23, 42);
  doc.text('4. TECHNICAL PIPELINE DETAILS', marginX, yPos);
  yPos += 6;

  const inputType = data.input_badge || 'Remote Sensing Image';
  const analysisMode = data.analysis_mode || data.method || 'Standard Pipeline';
  const totalTimeMs = trace.total_time_ms || 0;

  const techRows = [
    ['Pipeline Task', taskName],
    ['Confidence Score', `${confidencePct}%`],
    ['Input Badge', inputType],
    ['Analysis Mode / Method', analysisMode],
    ['Total Execution Time', `${totalTimeMs.toFixed(0)} ms`],
  ];

  doc.setFillColor(248, 250, 252);
  doc.rect(marginX, yPos, contentWidth, 18, 'F');
  doc.setDrawColor(226, 232, 240);
  doc.rect(marginX, yPos, contentWidth, 18, 'S');

  doc.setFontSize(8);
  techRows.forEach(([k, v], idx) => {
    const col = idx % 2;
    const row = Math.floor(idx / 2);
    const x = marginX + 4 + col * (contentWidth / 2);
    const y = yPos + 5 + row * 8;

    doc.setFont('helvetica', 'bold');
    doc.setTextColor(71, 85, 105);
    doc.text(`${k}:`, x, y);

    doc.setFont('helvetica', 'normal');
    doc.setTextColor(15, 23, 42);
    doc.text(`${v}`, x + 35, y);
  });

  yPos += 24;

  // Pipeline execution steps table
  const steps = trace.pipeline_steps || [];
  if (steps.length > 0) {
    checkAddPage(20 + steps.length * 7);

    doc.setFont('helvetica', 'bold');
    doc.setFontSize(8.5);
    doc.setTextColor(71, 85, 105);
    doc.text('PIPELINE EXECUTION TRACE', marginX, yPos);
    yPos += 4;

    // Table Header
    doc.setFillColor(226, 232, 240);
    doc.rect(marginX, yPos, contentWidth, 6, 'F');
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(7.5);
    doc.setTextColor(51, 65, 85);
    doc.text('STEP', marginX + 3, yPos + 4.2);
    doc.text('MODEL / ENGINE', marginX + 20, yPos + 4.2);
    doc.text('ACTION', marginX + 70, yPos + 4.2);
    doc.text('TIME', marginX + 130, yPos + 4.2);
    doc.text('STATUS', marginX + 155, yPos + 4.2);

    yPos += 6;

    // Table Rows
    steps.forEach((s, idx) => {
      checkAddPage(8);

      const isEven = idx % 2 === 0;
      if (isEven) {
        doc.setFillColor(248, 250, 252);
        doc.rect(marginX, yPos, contentWidth, 6, 'F');
      }

      doc.setFont('helvetica', 'bold');
      doc.setFontSize(7.5);
      doc.setTextColor(99, 102, 241);
      doc.text(`#${s.step || idx + 1}`, marginX + 3, yPos + 4.2);

      doc.setFont('helvetica', 'bold');
      doc.setTextColor(15, 23, 42);
      doc.text(String(s.model || 'rs_vlm'), marginX + 20, yPos + 4.2);

      doc.setFont('helvetica', 'normal');
      doc.setTextColor(71, 85, 105);
      doc.text(String(s.action || 'generate'), marginX + 70, yPos + 4.2);

      doc.text(`${(s.time_ms || 0).toFixed(0)} ms`, marginX + 130, yPos + 4.2);

      doc.setFont('helvetica', 'bold');
      doc.setTextColor(16, 185, 129);
      doc.text('Ready', marginX + 155, yPos + 4.2);

      yPos += 6;
    });

    yPos += 6;
  }

  // 9. Scientific Warning Notice
  checkAddPage(16);
  doc.setFillColor(254, 243, 199); // amber 100
  doc.rect(marginX, yPos, contentWidth, 10, 'F');
  doc.setDrawColor(245, 158, 11);
  doc.setLineWidth(0.3);
  doc.rect(marginX, yPos, contentWidth, 10, 'S');

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(7.5);
  doc.setTextColor(180, 83, 9);
  doc.text('SCIENTIFIC NOTICE:', marginX + 4, yPos + 6.2);

  doc.setFont('helvetica', 'normal');
  doc.setTextColor(146, 64, 14);
  doc.text('Spectral signatures & dark SAR regions require domain expert verification.', marginX + 34, yPos + 6.2);

  // 10. Page Numbers & Footer
  const totalPages = doc.getNumberOfPages();
  for (let i = 1; i <= totalPages; i++) {
    doc.setPage(i);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(7.5);
    doc.setTextColor(148, 163, 184);

    doc.text('SatQuery AI — Autonomous Satellite Analysis Engine', marginX, pageHeight - 10);
    doc.text(`Page ${i} of ${totalPages}`, pageWidth - marginX - 18, pageHeight - 10);
  }

  // 11. Save PDF File
  const sanitizeTask = taskName.replace(/[^A-Z0-9]/gi, '_');
  const filename = `SatQuery_Report_${sanitizeTask}_${Date.now()}.pdf`;
  doc.save(filename);
}
