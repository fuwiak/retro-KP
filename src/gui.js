// ===== CHART.JS REGISTER =====
// Using auto import which registers all components automatically
import Chart from "chart.js/auto";

// ===== PDF PROCESSING IMPORTS =====
import * as pdfProcessor from "./pdfProcessor.js";
import * as dataExtractor from "./dataExtractor.js";
import * as translator from "./translator.js";
import * as steelEquivalents from "./steelEquivalents.js";
import * as exporter from "./exporter.js";
import * as telegramService from "./telegramService.js";
import { RectangleSelection, initPdfSelection, extractTextFromSelection, extractSelectionAsImage, renderSelectionOverlay } from "./pdfSelection.js";
import { getApiBaseUrl } from "./config.js";

const els = {
  selectPdfBtn: document.getElementById("selectPdfBtn"),
  pdfFileInput: document.getElementById("pdfFileInput"),
  processBtn: document.getElementById("processBtn"),
  telegramChatId: document.getElementById("telegramChatId"),
  colorPicker: document.getElementById("colorPicker"),
  status: document.getElementById("statusLine"),
  logArea: document.getElementById("logArea"),
  logToggle: document.getElementById("logToggle"),
  logDrawer: document.getElementById("logDrawer"),
  progressArea: document.getElementById("progressArea"),
  progressToggle: document.getElementById("progressToggle"),
  progressDrawer: document.getElementById("progressDrawer"),
  cloudFolderToggle: document.getElementById("cloudFolderToggle"),
  cloudFolderDrawer: document.getElementById("cloudFolderDrawer"),
  cloudFolderUrl: document.getElementById("cloudFolderUrl"),
  loadCloudFolderBtn: document.getElementById("loadCloudFolderBtn"),
  cloudFolderStatus: document.getElementById("cloudFolderStatus"),
  cloudFolderContent: document.getElementById("cloudFolderContent"),
  togglePdf: document.getElementById("togglePdf"),
  pdfPreview: document.getElementById("pdfPreview"),
  pdfCanvas: document.getElementById("pdfCanvas"),
  croppedCanvas: document.getElementById("croppedCanvas"),
  polygonCanvas: document.getElementById("polygonCanvas"),
  selectionCanvas: document.getElementById("selectionCanvas"),
  croppedPreviewCanvas: document.getElementById("croppedPreviewCanvas"),
  croppedPreviewSection: document.getElementById("croppedPreviewSection"),
  croppedAreaSize: document.getElementById("croppedAreaSize"),
  croppedPointsCount: document.getElementById("croppedPointsCount"),
  finishPolygonBtn: document.getElementById("finishPolygonBtn"),
  clearPolygonBtn: document.getElementById("clearPolygonBtn"),
  enableCropBtn: document.getElementById("enableCropBtn"),
  cropModeToggle: document.getElementById("cropModeToggle"),
  clearCropBtn: document.getElementById("clearCropBtn"),
  resetPdfBtn: document.getElementById("resetPdfBtn"),
  cropStatus: document.getElementById("cropStatus"),
  cropOverlay: document.getElementById("cropOverlay"),
  cropSelection: document.getElementById("cropSelection"),
  pdfPreviewPlaceholder: document.getElementById("pdfPreviewPlaceholder"),
  modal: document.getElementById("modalOverlay"),
  modalTitleText: document.getElementById("modalTitleText"),
  modalData: document.getElementById("modalData"),
  modalClose: document.getElementById("modalClose"),
  modalSearch: document.getElementById("modalSearch"),
  modalApprove: document.getElementById("modalApprove"),
  modalReject: document.getElementById("modalReject"),
  exportBtn: document.getElementById("exportBtn"),
  extractedData: document.getElementById("extractedData"),
  resultsList: document.getElementById("resultsList"),
  steelToggle: document.getElementById("steelToggle"),
  steelDrawer: document.getElementById("steelDrawer"),
  searchSteelBtn: document.getElementById("searchSteelBtn"),
  steelSearch: document.getElementById("steelSearch"),
  steelStatus: document.getElementById("steelStatus"),
  steelResults: document.getElementById("steelResults"),
  telegramToggle: document.getElementById("telegramToggle"),
  telegramDrawer: document.getElementById("telegramDrawer"),
  telegramBotToken: document.getElementById("telegramBotToken"),
  testTelegramBtn: document.getElementById("testTelegramBtn"),
  telegramStatus: document.getElementById("telegramStatus"),
  telegramHistory: document.getElementById("telegramHistory"),
};

let humAudio = null;
let currentPdfFile = null;
let extractedData = null;
let translatedData = null;
let steelEquivData = {};
let cropMode = false;
let cropModeType = 'polygon'; // 'polygon' or 'rectangle'
let cropStartX = 0;
let cropStartY = 0;
let cropEndX = 0;
let cropEndY = 0;
let isCropping = false;
let polygonPoints = [];
let isPolygonComplete = false;
let currentCropArea = null;
let rectangleSelection = null;

let userSettings = {
  humEnabled: true,
  color: "rgb(255, 0, 0)",
  ocrLanguage: "rus+eng",
  autoTranslate: true,
  findSteelEquivalents: true,
  exportDocx: true,
  exportXlsx: true,
  exportPdf: true,
};

// ========== AUDIO ==========
function playClick(pitch = 440) {
  const ctx = new AudioContext();
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = "square";
  osc.frequency.value = pitch;
  gain.gain.value = 0.05;
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start();
  osc.stop(ctx.currentTime + 0.1);
}

function playTeleportFX() {
  const ctx = new AudioContext();
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = "sawtooth";
  osc.frequency.setValueAtTime(800, ctx.currentTime);
  osc.frequency.exponentialRampToValueAtTime(60, ctx.currentTime + 0.3);
  gain.gain.setValueAtTime(0.1, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start();
  osc.stop(ctx.currentTime + 0.4);
}

function startHum() {
  if (humAudio) return;
  const ctx = new AudioContext();
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = "sine";
  osc.frequency.value = 55;
  gain.gain.value = 0.02;
  osc.connect(gain);
  gain.connect(ctx.destination);
  osc.start();
  humAudio = { ctx, osc, gain };
}

function stopHum() {
  if (humAudio) {
    humAudio.osc.stop();
    humAudio.ctx.close();
    humAudio = null;
  }
}

// ========== LOGGING ==========
function log(msg) {
  const time = new Date().toLocaleTimeString();
  els.logArea.innerHTML += `[${time}] ${msg}<br>`;
  els.logArea.scrollTop = els.logArea.scrollHeight;
  console.log(msg);
}

// ========== PROGRESS TRACKING ==========
let progressSteps = [];
let currentStepIndex = -1;
let progressSubSteps = []; // For detailed sub-steps within a main step

function updateProgress(step, status = 'active', details = '') {
  const stepIndex = progressSteps.findIndex(s => s.id === step);
  
  if (stepIndex === -1) {
    // New step
    progressSteps.push({
      id: step,
      label: step,
      status: status,
      details: details,
      timestamp: new Date(),
      subSteps: []
    });
    currentStepIndex = progressSteps.length - 1;
  } else {
    // Update existing step
    progressSteps[stepIndex].status = status;
    progressSteps[stepIndex].details = details;
    if (status === 'completed' || status === 'error') {
      progressSteps[stepIndex].timestamp = new Date();
    }
  }
  
  renderProgress();
}

function addProgressSubStep(stepId, subStepText) {
  const stepIndex = progressSteps.findIndex(s => s.id === stepId);
  if (stepIndex !== -1) {
    if (!progressSteps[stepIndex].subSteps) {
      progressSteps[stepIndex].subSteps = [];
    }
    progressSteps[stepIndex].subSteps.push({
      text: subStepText,
      time: new Date()
    });
    // Keep only last 10 sub-steps
    if (progressSteps[stepIndex].subSteps.length > 10) {
      progressSteps[stepIndex].subSteps.shift();
    }
    renderProgress();
  }
}

function clearProgress() {
  progressSteps = [];
  currentStepIndex = -1;
  renderProgress();
}

function renderProgress() {
  if (!els.progressArea) return;
  
  if (progressSteps.length === 0) {
    els.progressArea.innerHTML = '<p style="opacity: 0.6; text-align: center; padding: 20px;">No active processing</p>';
    return;
  }
  
  let html = '';
  progressSteps.forEach((step, index) => {
    const statusClass = step.status === 'active' ? 'active' : 
                        step.status === 'completed' ? 'completed' : 
                        step.status === 'error' ? 'error' : '';
    
    const icon = step.status === 'active' ? '⏳' : 
                 step.status === 'completed' ? '✅' : 
                 step.status === 'error' ? '❌' : '⏸️';
    
    const time = step.timestamp ? step.timestamp.toLocaleTimeString() : '';
    
    html += `<div class="progress-item ${statusClass}">`;
    html += `<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 3px;">`;
    html += `<strong>${icon} ${step.label}</strong>`;
    if (time) html += `<span style="font-size: 0.7rem; opacity: 0.7;">${time}</span>`;
    html += `</div>`;
    if (step.details) {
      html += `<div style="font-size: 0.75rem; opacity: 0.8; margin-top: 3px; font-weight: bold;">${step.details}</div>`;
    }
    
    // Show sub-steps if available
    if (step.subSteps && step.subSteps.length > 0) {
      html += `<div style="margin-top: 5px; padding-left: 10px; border-left: 1px solid var(--ui-color); font-size: 0.7rem; opacity: 0.7;">`;
      step.subSteps.slice(-5).forEach(subStep => {
        const subTime = subStep.time ? subStep.time.toLocaleTimeString() : '';
        html += `<div style="margin: 2px 0;">${subTime ? `[${subTime}] ` : ''}${subStep.text}</div>`;
      });
      html += `</div>`;
    }
    
    html += `</div>`;
  });
  
  els.progressArea.innerHTML = html;
  els.progressArea.scrollTop = els.progressArea.scrollHeight;
  
  // Auto-open drawer when there's progress
  if (progressSteps.length > 0 && !els.progressDrawer.classList.contains('open')) {
    els.progressDrawer.classList.add('open');
  }
  
  // Auto-close drawer when all steps are completed
  const allCompleted = progressSteps.every(s => s.status === 'completed' || s.status === 'error');
  if (allCompleted && progressSteps.length > 0) {
    setTimeout(() => {
      if (progressSteps.every(s => s.status === 'completed' || s.status === 'error')) {
        els.progressDrawer.classList.remove('open');
      }
    }, 3000);
  }
}

// ========== PDF PREVIEW ==========
els.togglePdf.addEventListener("click", () => {
  const hidden = els.pdfPreview.classList.toggle("hidden");
  const t = translations[currentLang];
  if (hidden) {
    els.togglePdf.textContent = t.showPreview;
    log("📄 Hiding PDF preview");
      } else {
    els.togglePdf.textContent = t.hidePreview;
    log("📄 Showing PDF preview");
  }
  playClick(hidden ? 350 : 500);
});

// ========== RESET PDF ==========
els.resetPdfBtn.addEventListener("click", () => {
  // Reset everything to initial state
  currentPdfFile = null;
  currentCropArea = null;
  cropMode = false;
  extractedData = null;
  translatedData = null;
  steelEquivData = {};
  
  // Clear file input
  els.pdfFileInput.value = '';
  
  // Reset UI
  els.pdfCanvas.width = 0;
  els.pdfCanvas.height = 0;
  els.pdfCanvas.style.display = 'none';
  els.polygonCanvas.width = 0;
  els.polygonCanvas.height = 0;
  els.polygonCanvas.style.display = 'none';
  els.pdfPreviewPlaceholder.style.display = 'block';
  els.pdfPreviewPlaceholder.textContent = 'PDF preview will appear here';
  els.enableCropBtn.style.display = 'none';
  els.clearCropBtn.style.display = 'none';
  els.cropStatus.textContent = '';
  els.cropSelection.style.display = 'none';
  els.cropOverlay.style.display = 'none';
  els.cropOverlay.classList.remove('active');
  els.pdfCanvas.classList.remove('crop-mode');
  els.enableCropBtn.textContent = '✂️ Enable Crop';
  els.enableCropBtn.style.background = 'rgba(0, 0, 0, 0.8)';
  els.croppedPreviewSection.style.display = 'none';
  polygonPoints = [];
  isPolygonComplete = false;
  if (rectangleSelection) {
    rectangleSelection.clear();
    rectangleSelection = null;
  }
  els.selectionCanvas.style.display = 'none';
  
  // Clear extracted data display
  els.extractedData.innerHTML = '<p style="opacity: 0.6; text-align: center; padding: 20px;">Upload and process a PDF drawing to see extracted data</p>';
  els.resultsList.innerHTML = '';
  
  // Clear progress
  clearProgress();
  
  els.status.textContent = "💤 Idle — waiting for input";
  log("🔄 PDF reset - ready for new file");
  playTeleportFX();
});

// ========== CROP MODE TOGGLE ==========
els.cropModeToggle.addEventListener("click", () => {
  if (!cropMode) return;
  
  cropModeType = cropModeType === 'polygon' ? 'rectangle' : 'polygon';
  
  // Clear current selection
  if (rectangleSelection) {
    rectangleSelection.clear();
    rectangleSelection = null;
  }
  polygonPoints = [];
  isPolygonComplete = false;
  currentCropArea = null;
  
  // Update UI
  els.cropModeToggle.textContent = cropModeType === 'polygon' ? '📐 Rectangle' : '🔺 Polygon';
  els.polygonCanvas.style.display = cropModeType === 'polygon' ? 'block' : 'none';
  els.selectionCanvas.style.display = cropModeType === 'rectangle' ? 'block' : 'none';
  
  // Initialize rectangle selection if needed
  if (cropModeType === 'rectangle' && els.pdfCanvas.width > 0) {
    els.selectionCanvas.width = els.pdfCanvas.width;
    els.selectionCanvas.height = els.pdfCanvas.height;
    els.selectionCanvas.style.width = els.pdfCanvas.style.width;
    els.selectionCanvas.style.height = els.pdfCanvas.style.height;
    
    const uiColor = getComputedStyle(document.documentElement).getPropertyValue('--ui-color') || 'rgb(255, 0, 0)';
    
    // Function to redraw selection overlay
    const redrawSelectionOverlay = (selection) => {
      if (!selection) return;
      const ctx = els.selectionCanvas.getContext('2d');
      ctx.clearRect(0, 0, els.selectionCanvas.width, els.selectionCanvas.height);
      ctx.drawImage(els.pdfCanvas, 0, 0);
      renderSelectionOverlay(els.selectionCanvas, els.pdfCanvas, selection);
    };
    
    rectangleSelection = new RectangleSelection(els.pdfCanvas, {
      color: 'rgba(255, 0, 0, 0.2)',
      borderColor: uiColor,
      borderWidth: 3,
      onSelectionUpdate: (selection) => {
        // Update overlay in real-time during drag
        redrawSelectionOverlay(selection);
      },
      onSelection: (selection) => {
        // Finalize selection when mouse is released
        currentCropArea = {
          type: 'rectangle',
          x: selection.x,
          y: selection.y,
          width: selection.width,
          height: selection.height
        };
        
        // Extract and show preview
        const imageData = extractSelectionAsImage(els.pdfCanvas, selection);
        if (imageData && els.croppedPreviewCanvas) {
          const img = new Image();
          img.onload = () => {
            els.croppedPreviewCanvas.width = selection.width;
            els.croppedPreviewCanvas.height = selection.height;
            const ctx = els.croppedPreviewCanvas.getContext('2d');
            ctx.drawImage(img, 0, 0);
            els.croppedAreaSize.textContent = `${Math.round(selection.width)}x${Math.round(selection.height)}px`;
            els.croppedPreviewSection.style.display = 'block';
          };
          img.src = imageData;
        }
        
        // Final render overlay
        redrawSelectionOverlay(selection);
        
        els.cropStatus.textContent = `✓ Rectangle selected (${Math.round(selection.width)}x${Math.round(selection.height)}px)`;
        log(`✓ Rectangle selection: ${Math.round(selection.width)}x${Math.round(selection.height)}px`);
        playTeleportFX();
      }
    });
    
    els.cropStatus.textContent = '🖱️ Kliknij i przeciągnij na PDF, aby zaznaczyć prostokąt';
    els.cropStatus.style.display = 'inline-block';
    log(`📐 Rectangle selection mode enabled`);
    } else {
    els.cropStatus.textContent = cropModeType === 'polygon' ? '🖱️ Kliknij na PDF, aby dodać punkty (podwójne kliknięcie lub Finish kończy)' : '';
    els.cropStatus.style.display = 'inline-block';
    log(`🔺 Polygon crop mode enabled`);
  }
  
  playClick(400);
});

// ========== POLYGON CROP FUNCTIONALITY ==========
els.enableCropBtn.addEventListener("click", () => {
  if (!currentPdfFile || !els.pdfCanvas.width) {
    els.cropStatus.textContent = '⚠️ Load PDF first';
    playClick(250);
    return;
  }

  cropMode = !cropMode;
  els.pdfCanvas.classList.toggle('crop-mode', cropMode);
  els.cropModeToggle.style.display = cropMode ? 'inline-block' : 'none';
  
  if (cropMode) {
    // Ensure canvas is interactive
    els.pdfCanvas.style.pointerEvents = 'auto';
    els.pdfCanvas.style.cursor = cropModeType === 'polygon' ? 'crosshair' : 'crosshair';
    
    // Initialize based on current mode type
    if (cropModeType === 'polygon') {
      // Initialize polygon mode
      polygonPoints = [];
      isPolygonComplete = false;
      els.cropOverlay.style.display = 'block';
      els.cropOverlay.style.pointerEvents = 'none'; // Don't block clicks
      els.cropOverlay.classList.add('active');
      els.enableCropBtn.textContent = '✂️ Crop Mode ON';
      els.enableCropBtn.style.background = 'rgba(255, 0, 0, 0.3)';
      els.cropStatus.textContent = '🖱️ Kliknij na PDF, aby dodać punkty (podwójne kliknięcie lub Finish kończy)';
      els.cropStatus.style.display = 'inline-block';
      els.polygonCanvas.width = els.pdfCanvas.width;
      els.polygonCanvas.height = els.pdfCanvas.height;
      els.polygonCanvas.style.width = els.pdfCanvas.style.width;
      els.polygonCanvas.style.height = els.pdfCanvas.style.height;
      els.polygonCanvas.style.display = 'block';
      els.selectionCanvas.style.display = 'none';
      els.croppedPreviewSection.style.display = 'none';
      els.croppedPointsCount.textContent = '0';
      drawPolygon();
      log("✂️ Polygon crop mode enabled - click to add points");
    } else {
      // Initialize rectangle mode
      els.cropOverlay.style.display = 'block';
      els.cropOverlay.style.pointerEvents = 'none'; // Don't block clicks
      els.cropOverlay.classList.add('active');
      els.enableCropBtn.textContent = '✂️ Crop Mode ON';
      els.enableCropBtn.style.background = 'rgba(255, 0, 0, 0.3)';
      els.polygonCanvas.style.display = 'none';
      els.selectionCanvas.width = els.pdfCanvas.width;
      els.selectionCanvas.height = els.pdfCanvas.height;
      els.selectionCanvas.style.width = els.pdfCanvas.style.width;
      els.selectionCanvas.style.height = els.pdfCanvas.style.height;
      els.selectionCanvas.style.display = 'block';
      
      // Draw PDF on selection canvas
      const ctx = els.selectionCanvas.getContext('2d');
      ctx.drawImage(els.pdfCanvas, 0, 0);
      
      const uiColor = getComputedStyle(document.documentElement).getPropertyValue('--ui-color') || 'rgb(255, 0, 0)';
      
      // Function to redraw selection overlay
      const redrawSelectionOverlay = (selection) => {
        if (!selection) return;
        const ctx = els.selectionCanvas.getContext('2d');
        ctx.clearRect(0, 0, els.selectionCanvas.width, els.selectionCanvas.height);
        ctx.drawImage(els.pdfCanvas, 0, 0);
        renderSelectionOverlay(els.selectionCanvas, els.pdfCanvas, selection);
      };
      
      rectangleSelection = new RectangleSelection(els.pdfCanvas, {
        color: 'rgba(255, 0, 0, 0.2)',
        borderColor: uiColor,
        borderWidth: 3,
        onSelectionUpdate: (selection) => {
          // Update overlay in real-time during drag
          redrawSelectionOverlay(selection);
        },
        onSelection: (selection) => {
          // Finalize selection when mouse is released
          currentCropArea = {
            type: 'rectangle',
            x: selection.x,
            y: selection.y,
            width: selection.width,
            height: selection.height
          };
          
          // Extract and show preview
          const imageData = extractSelectionAsImage(els.pdfCanvas, selection);
          if (imageData && els.croppedPreviewCanvas) {
            const img = new Image();
            img.onload = () => {
              els.croppedPreviewCanvas.width = selection.width;
              els.croppedPreviewCanvas.height = selection.height;
              const ctx = els.croppedPreviewCanvas.getContext('2d');
              ctx.drawImage(img, 0, 0);
              els.croppedAreaSize.textContent = `${Math.round(selection.width)}x${Math.round(selection.height)}px`;
              els.croppedPreviewSection.style.display = 'block';
            };
            img.src = imageData;
          }
          
          // Final render overlay
          redrawSelectionOverlay(selection);
          
          els.cropStatus.textContent = `✓ Rectangle selected (${Math.round(selection.width)}x${Math.round(selection.height)}px)`;
          log(`✓ Rectangle selection: ${Math.round(selection.width)}x${Math.round(selection.height)}px`);
          playTeleportFX();
        }
      });
      
      els.cropStatus.textContent = '🖱️ Kliknij i przeciągnij na PDF, aby zaznaczyć prostokąt';
      els.cropStatus.style.display = 'inline-block';
      log("📐 Rectangle selection mode enabled - drag to select");
      }
    } else {
    // Exit crop mode
    els.cropOverlay.style.display = 'none';
    els.cropOverlay.classList.remove('active');
    els.enableCropBtn.textContent = '✂️ Enable Crop';
    els.enableCropBtn.style.background = 'rgba(0, 0, 0, 0.8)';
    els.cropStatus.textContent = '';
    els.polygonCanvas.style.display = 'none';
    els.selectionCanvas.style.display = 'none';
    els.cropSelection.style.display = 'none';
    polygonPoints = [];
    isPolygonComplete = false;
    els.croppedPreviewSection.style.display = 'none';
    if (rectangleSelection) {
      rectangleSelection.clear();
      rectangleSelection = null;
    }
    log("✂️ Crop mode disabled");
  }
  playClick(400);
});

els.clearCropBtn.addEventListener("click", () => {
  currentCropArea = null;
  els.clearCropBtn.style.display = 'none';
  els.cropSelection.style.display = 'none';
  els.cropStatus.textContent = 'Crop cleared';
  log("🗑️ Crop cleared");
  playClick(350);
});

els.clearPolygonBtn.addEventListener("click", () => {
  if (cropModeType === 'polygon') {
    polygonPoints = [];
    isPolygonComplete = false;
    currentCropArea = null;
    els.croppedPreviewSection.style.display = 'none';
    drawPolygon();
    els.cropStatus.textContent = 'Polygon cleared - click to add points';
    els.croppedPointsCount.textContent = '0';
    log("🗑️ Polygon cleared");
  } else {
    // Clear rectangle selection
    if (rectangleSelection) {
      rectangleSelection.clear();
      rectangleSelection = null;
    }
    currentCropArea = null;
    els.croppedPreviewSection.style.display = 'none';
    const ctx = els.selectionCanvas.getContext('2d');
    ctx.clearRect(0, 0, els.selectionCanvas.width, els.selectionCanvas.height);
    ctx.drawImage(els.pdfCanvas, 0, 0);
    els.cropStatus.textContent = 'Rectangle cleared - drag to select';
    log("🗑️ Rectangle selection cleared");
  }
  playClick(350);
});

els.finishPolygonBtn.addEventListener("click", () => {
  if (polygonPoints.length >= 3) {
    isPolygonComplete = true;
    extractPolygonArea();
    els.cropStatus.textContent = `✓ Polygon complete (${polygonPoints.length} points)`;
    log(`✓ Polygon finished with ${polygonPoints.length} points`);
    playTeleportFX();
    } else {
    els.cropStatus.textContent = '⚠️ Need at least 3 points';
    playClick(250);
  }
});

// Draw polygon on overlay canvas
function drawPolygon() {
  if (!els.polygonCanvas) return;
  
  const ctx = els.polygonCanvas.getContext('2d');
  ctx.clearRect(0, 0, els.polygonCanvas.width, els.polygonCanvas.height);
  
  if (polygonPoints.length === 0) return;
  
  const uiColor = getComputedStyle(document.documentElement).getPropertyValue('--ui-color') || 'rgb(255, 0, 0)';
  
  // Draw lines between points
  if (polygonPoints.length > 1) {
    ctx.strokeStyle = uiColor;
    ctx.lineWidth = 3;
    ctx.setLineDash([]);
    ctx.beginPath();
    ctx.moveTo(polygonPoints[0].x, polygonPoints[0].y);
    for (let i = 1; i < polygonPoints.length; i++) {
      ctx.lineTo(polygonPoints[i].x, polygonPoints[i].y);
    }
    ctx.stroke();
  }
  
  // Draw dots at each point
  polygonPoints.forEach((point, index) => {
    // Outer circle
    ctx.fillStyle = uiColor;
    ctx.beginPath();
    ctx.arc(point.x, point.y, 8, 0, Math.PI * 2);
    ctx.fill();
    
    // Inner circle (white)
    ctx.fillStyle = '#000';
    ctx.beginPath();
    ctx.arc(point.x, point.y, 4, 0, Math.PI * 2);
    ctx.fill();
    
    // Point number
    ctx.fillStyle = uiColor;
    ctx.font = 'bold 12px monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(String(index + 1), point.x, point.y);
  });
  
  // If polygon is complete, fill it
  if (isPolygonComplete && polygonPoints.length >= 3) {
    ctx.fillStyle = 'rgba(255, 0, 0, 0.15)';
    ctx.beginPath();
    ctx.moveTo(polygonPoints[0].x, polygonPoints[0].y);
    for (let i = 1; i < polygonPoints.length; i++) {
      ctx.lineTo(polygonPoints[i].x, polygonPoints[i].y);
    }
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
  }
}

// Extract polygon area from canvas
function extractPolygonArea() {
  if (polygonPoints.length < 3 || !els.pdfCanvas) return null;
  
  // Calculate bounding box
  let minX = Math.min(...polygonPoints.map(p => p.x));
  let maxX = Math.max(...polygonPoints.map(p => p.x));
  let minY = Math.min(...polygonPoints.map(p => p.y));
  let maxY = Math.max(...polygonPoints.map(p => p.y));
  
  const width = maxX - minX;
  const height = maxY - minY;
  
  // Create mask canvas
  const maskCanvas = document.createElement('canvas');
  maskCanvas.width = els.pdfCanvas.width;
  maskCanvas.height = els.pdfCanvas.height;
  const maskCtx = maskCanvas.getContext('2d');
  
  // Draw polygon mask (white inside, black outside)
  maskCtx.fillStyle = '#fff';
  maskCtx.beginPath();
  maskCtx.moveTo(polygonPoints[0].x, polygonPoints[0].y);
  for (let i = 1; i < polygonPoints.length; i++) {
    maskCtx.lineTo(polygonPoints[i].x, polygonPoints[i].y);
  }
  maskCtx.closePath();
  maskCtx.fill();
  
  // Create output canvas with bounding box
  const outputCanvas = els.croppedPreviewCanvas;
  outputCanvas.width = width;
  outputCanvas.height = height;
  const outputCtx = outputCanvas.getContext('2d');
  
  // Fill with transparent background
  outputCtx.clearRect(0, 0, width, height);
  
  // Create composite canvas
  const compositeCanvas = document.createElement('canvas');
  compositeCanvas.width = els.pdfCanvas.width;
  compositeCanvas.height = els.pdfCanvas.height;
  const compositeCtx = compositeCanvas.getContext('2d');
  
  // Draw original image
  compositeCtx.drawImage(els.pdfCanvas, 0, 0);
  
  // Apply mask (keep only polygon area)
  compositeCtx.globalCompositeOperation = 'destination-in';
  compositeCtx.drawImage(maskCanvas, 0, 0);
  
  // Extract to preview (with offset for bounding box)
  outputCtx.drawImage(compositeCanvas, minX, minY, width, height, 0, 0, width, height);
  
  // Store crop area
  currentCropArea = {
    type: 'polygon',
    points: polygonPoints.map(p => ({ x: p.x, y: p.y })), // Copy points
    bounds: { x: minX, y: minY, width, height }
  };
  
  // Update preview info
  els.croppedAreaSize.textContent = `${Math.round(width)}x${Math.round(height)}px`;
  els.croppedPointsCount.textContent = polygonPoints.length;
  els.croppedPreviewSection.style.display = 'block';
  
  return outputCanvas.toDataURL('image/png');
}

// Get cropped image data (polygon or rectangle)
function getCroppedImage() {
  if (!currentCropArea || !els.pdfCanvas) return null;
  
  if (currentCropArea.type === 'polygon') {
    // Extract polygon area - use already extracted preview
    if (els.croppedPreviewCanvas && els.croppedPreviewCanvas.width > 0) {
      return els.croppedPreviewCanvas.toDataURL('image/png');
    }
    // Fallback: extract again
    return extractPolygonArea();
  } else if (currentCropArea.type === 'rectangle') {
    // Rectangle selection - use extractSelectionAsImage
    if (rectangleSelection && rectangleSelection.getSelection()) {
      return extractSelectionAsImage(els.pdfCanvas, rectangleSelection.getSelection());
    }
    // Fallback to manual extraction
    const canvas = els.croppedCanvas;
    const ctx = canvas.getContext('2d');
    
    canvas.width = currentCropArea.width;
    canvas.height = currentCropArea.height;
    
    ctx.drawImage(
      els.pdfCanvas,
      currentCropArea.x, currentCropArea.y, currentCropArea.width, currentCropArea.height,
      0, 0, currentCropArea.width, currentCropArea.height
    );
    
    return canvas.toDataURL('image/png');
  } else {
    // Legacy rectangle crop
    const canvas = els.croppedCanvas;
    const ctx = canvas.getContext('2d');
    
    canvas.width = currentCropArea.width;
    canvas.height = currentCropArea.height;
    
    ctx.drawImage(
      els.pdfCanvas,
      currentCropArea.x, currentCropArea.y, currentCropArea.width, currentCropArea.height,
      0, 0, currentCropArea.width, currentCropArea.height
    );
    
    return canvas.toDataURL('image/png');
  }
}

// Polygon crop handlers
els.pdfCanvas.addEventListener("click", (e) => {
  console.log('Canvas click:', { cropMode, cropModeType, isPolygonComplete, canvasWidth: els.pdfCanvas.width });
  if (!cropMode || cropModeType !== 'polygon' || isPolygonComplete) {
    console.log('Click ignored - conditions not met');
      return;
    }

  const rect = els.pdfCanvas.getBoundingClientRect();
  const scaleX = els.pdfCanvas.width / rect.width;
  const scaleY = els.pdfCanvas.height / rect.height;
  
  const x = (e.clientX - rect.left) * scaleX;
  const y = (e.clientY - rect.top) * scaleY;
  
  // Add point
  polygonPoints.push({ x, y });
  drawPolygon();
  
  els.croppedPointsCount.textContent = polygonPoints.length;
  els.cropStatus.textContent = `Point ${polygonPoints.length} added (click to add more, or click Finish)`;
  log(`✂️ Added point ${polygonPoints.length} at (${Math.round(x)}, ${Math.round(y)})`);
  
  playClick(400);
});

els.pdfCanvas.addEventListener("dblclick", (e) => {
  if (!cropMode || cropModeType !== 'polygon' || polygonPoints.length < 3) return;
  
  e.preventDefault();
  isPolygonComplete = true;
  extractPolygonArea();
  els.cropStatus.textContent = `✓ Polygon complete (${polygonPoints.length} points)`;
  log(`✓ Polygon finished with ${polygonPoints.length} points (double-click)`);
    playTeleportFX();
});

// Draw preview line to mouse cursor (polygon mode only)
els.pdfCanvas.addEventListener("mousemove", (e) => {
  if (!cropMode || cropModeType !== 'polygon' || isPolygonComplete || polygonPoints.length === 0) return;
  
  const rect = els.pdfCanvas.getBoundingClientRect();
  const scaleX = els.pdfCanvas.width / rect.width;
  const scaleY = els.pdfCanvas.height / rect.height;
  
  const mouseX = (e.clientX - rect.left) * scaleX;
  const mouseY = (e.clientY - rect.top) * scaleY;
  
  // Redraw polygon with preview line
  const ctx = els.polygonCanvas.getContext('2d');
  ctx.clearRect(0, 0, els.polygonCanvas.width, els.polygonCanvas.height);
  
  // Draw existing polygon
  if (polygonPoints.length > 0) {
    const uiColor = getComputedStyle(document.documentElement).getPropertyValue('--ui-color') || 'rgb(255, 0, 0)';
    
    // Draw lines between existing points
    if (polygonPoints.length > 1) {
      ctx.strokeStyle = uiColor;
      ctx.lineWidth = 3;
      ctx.setLineDash([]);
      ctx.beginPath();
      ctx.moveTo(polygonPoints[0].x, polygonPoints[0].y);
      for (let i = 1; i < polygonPoints.length; i++) {
        ctx.lineTo(polygonPoints[i].x, polygonPoints[i].y);
      }
      ctx.stroke();
    }
    
    // Draw preview line from last point to mouse (dashed)
    ctx.strokeStyle = uiColor;
    ctx.lineWidth = 2;
    ctx.setLineDash([5, 5]);
    ctx.beginPath();
    const lastPoint = polygonPoints[polygonPoints.length - 1];
    ctx.moveTo(lastPoint.x, lastPoint.y);
    ctx.lineTo(mouseX, mouseY);
    ctx.stroke();
    ctx.setLineDash([]);
  }
  
  // Redraw polygon points
  if (polygonPoints.length > 0) {
    const uiColor = getComputedStyle(document.documentElement).getPropertyValue('--ui-color') || 'rgb(255, 0, 0)';
    polygonPoints.forEach((point, index) => {
      // Outer circle
      ctx.fillStyle = uiColor;
      ctx.beginPath();
      ctx.arc(point.x, point.y, 8, 0, Math.PI * 2);
      ctx.fill();
      
      // Inner circle (black)
      ctx.fillStyle = '#000';
      ctx.beginPath();
      ctx.arc(point.x, point.y, 4, 0, Math.PI * 2);
      ctx.fill();
      
      // Point number
      ctx.fillStyle = uiColor;
      ctx.font = 'bold 12px monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(String(index + 1), point.x, point.y);
    });
  }
});


// ========== PDF FILE SELECTION ==========
els.selectPdfBtn.addEventListener("click", () => {
  els.pdfFileInput.click();
  playClick(400);
});

els.pdfFileInput.addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  
  if (file.type !== "application/pdf") {
    els.status.textContent = "❌ Please select a PDF file";
    log("❌ Invalid file type");
    playClick(250);
    return;
  }
  
  currentPdfFile = file;
  els.status.textContent = `📄 Selected: ${file.name}`;
  log(`📄 PDF file selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`);
  
  // Show preview
  try {
    const preview = await pdfProcessor.renderPdfPreview(file, els.pdfCanvas);
    if (typeof preview === 'string' && preview.startsWith('data:')) {
      // Image data URL
      els.pdfPreview.innerHTML = `<img src="${preview}" style="max-width: 100%; height: auto;" />`;
    } else if (typeof preview === 'string') {
      // Object URL
      els.pdfPreview.innerHTML = `<iframe src="${preview}" style="width: 100%; height: 100%; border: none;"></iframe>`;
    }
    els.pdfPreview.classList.remove("hidden");
  } catch (error) {
    log(`⚠️ Preview error: ${error.message}`);
    els.pdfPreview.innerHTML = `<p style="opacity: 0.6; text-align: center; padding: 20px;">PDF loaded but preview unavailable</p>`;
  }
  
  playTeleportFX();
});

// ========== PDF PROCESSING ==========
els.processBtn.addEventListener("click", async () => {
  if (!currentPdfFile) {
    els.status.textContent = "❌ Please select a PDF file first";
    log("❌ No PDF file selected");
    playClick(250);
    return;
  }
  
  clearProgress();
  els.status.textContent = "⏳ Processing PDF...";
  log("⏳ Starting PDF processing...");
  playClick(400);
  
  try {
    // Step 1: Detect PDF type and process with OCR
    updateProgress('PDF Detection', 'active', 'Analyzing PDF structure...');
    const pdfType = await pdfProcessor.detectPdfType(currentPdfFile);
    updateProgress('PDF Detection', 'completed', `Type: ${pdfType}`);
    log(`📋 PDF type detected: ${pdfType}`);
    
    const languages = userSettings.ocrLanguage === "rus+eng" ? ["rus", "eng"] : 
                      userSettings.ocrLanguage === "rus" ? ["rus"] : ["eng"];
    
    // Step 2: OCR Processing (with crop if available)
    updateProgress('OCR Processing', 'active', `Initializing OCR with ${languages.join(' + ')} languages...`);
    addProgressSubStep('OCR Processing', `Starting OCR processing`);
    addProgressSubStep('OCR Processing', `Languages: ${languages.join(', ')}`);
    log(`📝 Starting OCR processing...`);
    log(`📝 Languages: ${languages.join(', ')}`);
    els.status.textContent = "⏳ Running OCR...";
    
    let ocrResult;
    if (currentCropArea) {
      // Use cropped image (polygon or rectangle)
      const areaInfo = currentCropArea.type === 'polygon' 
        ? `polygon (${currentCropArea.points.length} points, ${Math.round(currentCropArea.bounds.width)}x${Math.round(currentCropArea.bounds.height)}px)`
        : `${Math.round(currentCropArea.width)}x${Math.round(currentCropArea.height)}px`;
      
      updateProgress('OCR Processing', 'active', `Preparing cropped area (${areaInfo})...`);
      addProgressSubStep('OCR Processing', `Processing cropped area: ${areaInfo}`);
      if (currentCropArea.type === 'polygon') {
        addProgressSubStep('OCR Processing', `Polygon bounds: (${Math.round(currentCropArea.bounds.x)}, ${Math.round(currentCropArea.bounds.y)})`);
      } else {
        addProgressSubStep('OCR Processing', `Crop position: (${Math.round(currentCropArea.x)}, ${Math.round(currentCropArea.y)})`);
      }
      log(`✂️ Processing cropped area: ${areaInfo}`);
      if (currentCropArea.type === 'polygon') {
        log(`✂️ Polygon with ${currentCropArea.points.length} points`);
        } else {
        log(`✂️ Crop position: (${Math.round(currentCropArea.x)}, ${Math.round(currentCropArea.y)})`);
      }
      
      updateProgress('OCR Processing', 'active', `Extracting cropped image from canvas...`);
      addProgressSubStep('OCR Processing', `Extracting image data from selected area...`);
      log(`✂️ Extracting image data from selected area...`);
      const croppedImage = getCroppedImage();
      
      if (croppedImage) {
        updateProgress('OCR Processing', 'active', `Converting cropped image to file format...`);
        addProgressSubStep('OCR Processing', `Image extracted successfully, size: ${(croppedImage.length / 1024).toFixed(1)} KB`);
        log(`✂️ Image extracted successfully, size: ${(croppedImage.length / 1024).toFixed(1)} KB`);
        
        // Create a temporary file-like object for cropped image
        updateProgress('OCR Processing', 'active', `Sending cropped image to OCR engine...`);
        addProgressSubStep('OCR Processing', `Converting to blob format...`);
        log(`📤 Sending cropped image to Groq AI OCR...`);
        const croppedBlob = await fetch(croppedImage).then(r => r.blob());
        const croppedFile = new File([croppedBlob], 'cropped-area.png', { type: 'image/png' });
        addProgressSubStep('OCR Processing', `File created: ${(croppedBlob.size / 1024).toFixed(1)} KB`);
        
        updateProgress('OCR Processing', 'active', `Analyzing image with AI vision models...`);
        addProgressSubStep('OCR Processing', `Calling Groq AI API...`);
        // Import OCR_MODELS for display
        const { OCR_MODELS } = await import('./groqAgent.js');
        log(`🤖 Calling Groq AI with vision models: ${OCR_MODELS.join(', ')}`);
        addProgressSubStep('OCR Processing', `Models: ${OCR_MODELS.join(', ')}`);
        
        // Create progress callback for detailed logging
        const progressCallback = (msg) => {
          addProgressSubStep('OCR Processing', msg);
          log(`📝 ${msg}`);
        };
        
        ocrResult = await pdfProcessor.processPdfWithOCR(croppedFile, languages, progressCallback);
        ocrResult.isCropped = true;
        addProgressSubStep('OCR Processing', `✅ OCR completed on cropped area`);
        addProgressSubStep('OCR Processing', `Model used: ${ocrResult.model || 'unknown'}`);
        addProgressSubStep('OCR Processing', `Confidence: ${(ocrResult.confidence * 100).toFixed(1)}%`);
        log(`✅ OCR completed on cropped area`);
        log(`📊 Model used: ${ocrResult.model || 'unknown'}`);
        log(`📊 Confidence: ${(ocrResult.confidence * 100).toFixed(1)}%`);
  } else {
        log(`⚠️ Failed to extract cropped image, falling back to full PDF`);
        addProgressSubStep('OCR Processing', `⚠️ Failed to extract, falling back to full PDF`);
        updateProgress('OCR Processing', 'active', `Fallback: Processing full PDF...`);
        ocrResult = await pdfProcessor.processPdfWithOCR(currentPdfFile, languages);
      }
    } else {
      // Use full PDF
      updateProgress('OCR Processing', 'active', `Converting PDF to image format...`);
      addProgressSubStep('OCR Processing', `Processing full PDF document`);
      addProgressSubStep('OCR Processing', `File size: ${(currentPdfFile.size / 1024).toFixed(1)} KB`);
      log(`📄 Processing full PDF document`);
      log(`📄 File size: ${(currentPdfFile.size / 1024).toFixed(1)} KB`);
      
      updateProgress('OCR Processing', 'active', `Sending PDF to OCR engine...`);
      addProgressSubStep('OCR Processing', `Sending to Groq AI OCR...`);
      log(`📤 Sending PDF to Groq AI OCR...`);
      
      // Import OCR_MODELS for display
      const { OCR_MODELS } = await import('./groqAgent.js');
      log(`🤖 Calling Groq AI with vision models: ${OCR_MODELS.join(', ')}`);
      addProgressSubStep('OCR Processing', `Models: ${OCR_MODELS.join(', ')}`);
      
      updateProgress('OCR Processing', 'active', `Analyzing PDF with AI vision models...`);
      addProgressSubStep('OCR Processing', `Waiting for AI response...`);
      
      // Create progress callback for detailed logging
      const progressCallback = (msg) => {
        addProgressSubStep('OCR Processing', msg);
        log(`📝 ${msg}`);
      };
      
      ocrResult = await pdfProcessor.processPdfWithOCR(currentPdfFile, languages, progressCallback);
      addProgressSubStep('OCR Processing', `✅ OCR completed on full PDF`);
      addProgressSubStep('OCR Processing', `Model used: ${ocrResult.model || 'unknown'}`);
      addProgressSubStep('OCR Processing', `Confidence: ${(ocrResult.confidence * 100).toFixed(1)}%`);
      log(`✅ OCR completed on full PDF`);
      log(`📊 Model used: ${ocrResult.model || 'unknown'}`);
      log(`📊 Confidence: ${(ocrResult.confidence * 100).toFixed(1)}%`);
    }
    
    updateProgress('OCR Processing', 'completed', `${ocrResult.text.length} characters extracted${ocrResult.model ? ` (${ocrResult.model})` : ''}`);
    addProgressSubStep('OCR Processing', `Text length: ${ocrResult.text.length} characters`);
    log(`📝 OCR completed: ${ocrResult.text.length} characters extracted`);
    log(`📝 Text preview: ${ocrResult.text.substring(0, 200)}${ocrResult.text.length > 200 ? '...' : ''}`);
    
    // Step 3: Extract data
    updateProgress('Data Extraction', 'active', 'Extracting materials, standards, and technical data...');
    els.status.textContent = "⏳ Extracting data...";
    extractedData = await dataExtractor.extractAllData(ocrResult.text);
    updateProgress('Data Extraction', 'completed', `${extractedData.materials.length} materials, ${extractedData.standards.length} standards found`);
    log(`✅ Data extracted: ${extractedData.materials.length} materials, ${extractedData.standards.length} standards`);
    
    // Step 4: Translate if enabled
    if (userSettings.autoTranslate) {
      updateProgress('Translation', 'active', 'Translating to English with technical glossary...');
      els.status.textContent = "⏳ Translating...";
      translatedData = await translator.translateExtractedData(extractedData);
      updateProgress('Translation', 'completed', 'Translation completed');
      log("🌐 Translation completed");
    } else {
      translatedData = extractedData;
      updateProgress('Translation', 'completed', 'Skipped (disabled in settings)');
    }
    
    // Step 5: Find steel equivalents if enabled
    if (userSettings.findSteelEquivalents && extractedData.materials.length > 0) {
      updateProgress('Steel Equivalents', 'active', `Finding equivalents for ${extractedData.materials.length} material(s)...`);
      els.status.textContent = "⏳ Finding steel equivalents...";
      steelEquivData = {};
      for (let i = 0; i < extractedData.materials.length; i++) {
        const material = extractedData.materials[i];
        updateProgress('Steel Equivalents', 'active', `Looking up: ${material} (${i + 1}/${extractedData.materials.length})`);
        const equiv = await steelEquivalents.findSteelEquivalents(material);
        if (equiv) {
          steelEquivData[material] = equiv;
        }
      }
      updateProgress('Steel Equivalents', 'completed', `${Object.keys(steelEquivData).length} equivalents found`);
      log(`⚙️ Found ${Object.keys(steelEquivData).length} steel grade equivalents`);
    } else {
      updateProgress('Steel Equivalents', 'completed', 'Skipped (disabled or no materials)');
    }
    
    // Step 6: Display results
    updateProgress('Finalizing', 'active', 'Rendering results...');
    renderExtractedData();
    renderResults();
    updateProgress('Finalizing', 'completed', 'All done!');
    
    els.status.textContent = "✅ Processing complete";
    log("✅ PDF processing completed successfully");
    playTeleportFX();
    
  } catch (error) {
    if (progressSteps.length > 0) {
      const lastStep = progressSteps[progressSteps.length - 1];
      if (lastStep.status === 'active') {
        updateProgress(lastStep.id, 'error', error.message);
      } else {
        updateProgress('Error', 'error', error.message);
      }
    }
    els.status.textContent = `❌ Error: ${error.message}`;
    log(`❌ Processing error: ${error.message}`);
    playClick(250);
  }
});

// ========== RENDER EXTRACTED DATA ==========
function renderExtractedData() {
  if (!extractedData || !translatedData) return;
  
  let html = '<div style="padding: 10px;">';
  
  // Materials
  html += '<div style="margin-bottom: 15px; border-bottom: 1px solid var(--ui-color); padding-bottom: 10px;">';
  html += '<strong style="color: var(--ui-color);">Materials:</strong><br>';
  extractedData.materials.forEach((mat, i) => {
    html += `<div style="margin: 5px 0; padding: 5px; background: rgba(0,255,153,0.1); border-left: 2px solid var(--ui-color);">`;
    html += `<span>${mat}</span>`;
    if (translatedData.materials[i] && translatedData.materials[i] !== mat) {
      html += ` → <span style="opacity: 0.8;">${translatedData.materials[i]}</span>`;
    }
    if (steelEquivData[mat]) {
      html += `<div style="font-size: 0.75rem; margin-top: 3px; opacity: 0.7;">`;
      html += `ASTM: ${steelEquivData[mat].astm}, ISO: ${steelEquivData[mat].iso}, GB/T: ${steelEquivData[mat].gbt}`;
      html += `</div>`;
    }
    html += `</div>`;
  });
  html += '</div>';
  
  // Standards
  if (extractedData.standards.length > 0) {
    html += '<div style="margin-bottom: 15px; border-bottom: 1px solid var(--ui-color); padding-bottom: 10px;">';
    html += '<strong style="color: var(--ui-color);">Standards (GOST/OST/TU):</strong><br>';
    extractedData.standards.forEach((std, i) => {
      html += `<div style="margin: 5px 0;">${std}`;
      if (translatedData.standards[i] && translatedData.standards[i] !== std) {
        html += ` → ${translatedData.standards[i]}`;
      }
      html += `</div>`;
    });
    html += '</div>';
  }
  
  // Surface Roughness
  if (extractedData.raValues.length > 0) {
    html += '<div style="margin-bottom: 15px; border-bottom: 1px solid var(--ui-color); padding-bottom: 10px;">';
    html += '<strong style="color: var(--ui-color);">Surface Roughness (Ra):</strong><br>';
    html += extractedData.raValues.map(ra => `Ra ${ra}`).join(', ');
    html += '</div>';
  }
  
  // Fits
  if (extractedData.fits.length > 0) {
    html += '<div style="margin-bottom: 15px; border-bottom: 1px solid var(--ui-color); padding-bottom: 10px;">';
    html += '<strong style="color: var(--ui-color);">Fits:</strong><br>';
    html += extractedData.fits.join(', ');
    html += '</div>';
  }
  
  // Heat Treatment
  if (extractedData.heatTreatment.length > 0) {
    html += '<div style="margin-bottom: 15px;">';
    html += '<strong style="color: var(--ui-color);">Heat Treatment:</strong><br>';
    extractedData.heatTreatment.forEach((ht, i) => {
      html += `<div style="margin: 5px 0;">${ht}`;
      if (translatedData.heatTreatment[i] && translatedData.heatTreatment[i] !== ht) {
        html += ` → ${translatedData.heatTreatment[i]}`;
      }
      html += `</div>`;
    });
    html += '</div>';
  }
  
  html += '</div>';
  els.extractedData.innerHTML = html;
}

// ========== RENDER RESULTS ==========
function renderResults() {
  if (!translatedData) return;
  
  let html = '<div style="padding: 10px;">';
  html += '<div style="margin-bottom: 10px; border-bottom: 1px solid var(--ui-color); padding-bottom: 10px;">';
  html += '<strong style="color: var(--ui-color);">Processing Summary:</strong><br>';
  html += `<div style="margin-top: 5px; font-size: 0.85rem;">`;
  html += `✓ Materials found: ${extractedData.materials.length}<br>`;
  html += `✓ Standards found: ${extractedData.standards.length}<br>`;
  html += `✓ Surface roughness values: ${extractedData.raValues.length}<br>`;
  html += `✓ Fits found: ${extractedData.fits.length}<br>`;
  html += `✓ Heat treatment entries: ${extractedData.heatTreatment.length}<br>`;
  if (Object.keys(steelEquivData).length > 0) {
    html += `✓ Steel equivalents found: ${Object.keys(steelEquivData).length}<br>`;
  }
  html += `</div>`;
  html += '</div>';
  
  html += '<div style="margin-top: 10px;">';
  html += '<strong style="color: var(--ui-color);">Raw OCR Text:</strong><br>';
  html += `<div style="margin-top: 5px; font-size: 0.75rem; opacity: 0.8; max-height: 200px; overflow-y: auto; border: 1px solid var(--ui-color); padding: 5px;">`;
  html += translatedData.rawText.substring(0, 500);
  if (translatedData.rawText.length > 500) {
    html += '...';
  }
  html += `</div>`;
  html += '</div>';
  
  html += '</div>';
  els.resultsList.innerHTML = html;
}

// ========== EXPORT ==========
els.exportBtn.addEventListener("click", async () => {
  if (!extractedData || !translatedData) {
    els.status.textContent = "❌ No data to export. Process a PDF first.";
    log("❌ No data available for export");
    playClick(250);
    return;
  }

  els.status.textContent = "⏳ Exporting...";
  log("📥 Starting export...");
  playClick(400);
  
  try {
    const files = [];
    const timestamp = new Date().toISOString().split('T')[0];
    
    if (userSettings.exportDocx) {
      const docxBlob = await exporter.exportToDocx(extractedData, translatedData, steelEquivData);
      exporter.downloadFile(docxBlob, `drawing_analysis_${timestamp}.docx`);
      log("📄 DOCX exported");
    }
    
    if (userSettings.exportXlsx) {
      const xlsxBlob = await exporter.exportToXlsx(extractedData, translatedData, steelEquivData);
      exporter.downloadFile(xlsxBlob, `drawing_analysis_${timestamp}.xlsx`);
      log("📊 XLSX exported");
    }
    
    if (userSettings.exportPdf && currentPdfFile) {
      const pdfBlob = await exporter.exportToPdf(currentPdfFile, extractedData, translatedData, steelEquivData);
      exporter.downloadFile(pdfBlob, `drawing_analysis_${timestamp}.pdf`);
      log("📐 PDF with overlay exported");
    }
    
    els.status.textContent = "✅ Export complete";
    log("✅ All exports completed");
    playTeleportFX();
    
  } catch (error) {
    els.status.textContent = `❌ Export error: ${error.message}`;
    log(`❌ Export error: ${error.message}`);
    playClick(250);
  }
});

// ========== STEEL EQUIVALENTS DRAWER ==========
els.steelToggle.addEventListener("click", () => {
  els.steelDrawer.classList.toggle("open");
  playClick(400);
});

els.searchSteelBtn.addEventListener("click", async () => {
  const query = els.steelSearch.value.trim();
  if (!query) {
    els.steelStatus.textContent = "⚠️ Enter a steel grade";
    return;
  }
  
  els.steelStatus.textContent = "⏳ Searching...";
  
  // Try AI lookup first
  let result = null;
  try {
    const { findSteelEquivalents: aiFind } = await import('./groqAgent.js');
    result = await aiFind(query);
  } catch (error) {
    console.warn('AI search failed, using database:', error);
  }
  
  let results = [];
  if (result) {
    results = [result];
  } else {
    results = steelEquivalents.searchSteelEquivalents(query);
  }
  
  if (results.length === 0) {
    els.steelStatus.textContent = "❌ No equivalents found";
    els.steelResults.innerHTML = `<p style="opacity: 0.6; text-align: center; padding: 20px;">No steel grade equivalents found for "${query}"</p>`;
    playClick(250);
    return;
  }

  els.steelStatus.textContent = `✅ Found ${results.length} result(s)`;
  
  let html = '';
  results.forEach(result => {
    html += `<div style="border: 1px solid var(--ui-color); padding: 8px; margin-bottom: 8px; background: rgba(0,0,0,0.6);">`;
    html += `<strong>${result.grade}</strong><br>`;
    html += `<div style="font-size: 0.75rem; margin-top: 5px;">`;
    html += `GOST: ${result.gost || 'N/A'}<br>`;
    html += `ASTM: ${result.astm || 'N/A'}<br>`;
    html += `ISO: ${result.iso || 'N/A'}<br>`;
    html += `GB/T: ${result.gbt || 'N/A'}<br>`;
    html += `</div>`;
    if (result.description) {
      html += `<div style="font-size: 0.7rem; opacity: 0.7; margin-top: 3px;">${result.description}</div>`;
    }
    html += `</div>`;
  });
  
  els.steelResults.innerHTML = html;
    playTeleportFX();
});

// ========== TELEGRAM DRAWER ==========
els.telegramToggle.addEventListener("click", () => {
  els.telegramDrawer.classList.toggle("open");
  playClick(400);
});

els.testTelegramBtn.addEventListener("click", async () => {
  const botToken = els.telegramBotToken.value.trim();
  const chatId = els.telegramChatId.value.trim();
  
  if (!botToken || !chatId) {
    els.telegramStatus.textContent = "⚠️ Enter bot token and chat ID";
    playClick(250);
    return;
  }
  
  els.telegramStatus.textContent = "⏳ Testing connection...";
  try {
    await telegramService.testTelegramConnection(botToken, chatId);
    els.telegramStatus.textContent = "✅ Connection successful!";
    log("✅ Telegram connection test successful");
    playTeleportFX();
  } catch (error) {
    els.telegramStatus.textContent = `❌ Error: ${error.message}`;
    log(`❌ Telegram test failed: ${error.message}`);
    playClick(250);
  }
});

// Send to Telegram when processing is done
async function sendToTelegramIfConfigured() {
  const botToken = els.telegramBotToken.value.trim();
  const chatId = els.telegramChatId.value.trim();
  
  if (!botToken || !chatId || !extractedData || !translatedData) {
    return;
  }
  
  try {
    els.status.textContent = "⏳ Sending to Telegram...";
    const messageId = await telegramService.sendDraftForReview(botToken, chatId, extractedData, translatedData);
    log(`📱 Draft sent to Telegram (message ID: ${messageId})`);
    
    // Add to history
    let historyEntry = `<div style="border-bottom: 1px solid var(--ui-color); padding: 5px; margin-bottom: 5px;">`;
    historyEntry += `<div style="font-size: 0.75rem; opacity: 0.7;">${new Date().toLocaleString()}</div>`;
    historyEntry += `<div>Sent draft for review</div>`;
    historyEntry += `</div>`;
    els.telegramHistory.innerHTML = historyEntry + els.telegramHistory.innerHTML;
    
  } catch (error) {
    log(`❌ Telegram send error: ${error.message}`);
  }
}

// ========== MODAL ==========
function showModal(title, content) {
  els.modalTitleText.textContent = title;
  els.modalData.innerHTML = content;
  els.modal.classList.remove("hidden");
  playTeleportFX();
}

els.modalClose.addEventListener("click", () => {
  els.modal.classList.add("hidden");
  playClick(300);
});

els.modal.addEventListener("click", (e) => {
  if (e.target === els.modal) {
    els.modal.classList.add("hidden");
    playClick(250);
  }
});

els.modalApprove.addEventListener("click", () => {
  log("✅ Draft approved via modal");
  els.modal.classList.add("hidden");
  playTeleportFX();
});

els.modalReject.addEventListener("click", () => {
  log("❌ Draft rejected via modal");
  els.modal.classList.add("hidden");
  playClick(250);
});

els.modalSearch.addEventListener("input", (e) => {
  const val = e.target.value.toLowerCase();
  const content = els.modalData.innerHTML;
  // Simple filter - highlight matching text
  if (val) {
    const regex = new RegExp(`(${val})`, 'gi');
    els.modalData.innerHTML = content.replace(regex, '<mark style="background: var(--ui-color); color: #000;">$1</mark>');
        } else {
    els.modalData.innerHTML = content;
  }
});

// ========== CLOUD FOLDER DRAWER ==========
els.cloudFolderToggle.addEventListener("click", () => {
  els.cloudFolderDrawer.classList.toggle("open");
  playClick(400);
});

// Pagination state for cloud folder
let cloudFolderPagination = {
  url: '',
  offset: 0,
  limit: 50,
  hasMore: false,
  total: 0,
  loadedFiles: []
};

// Load cloud folder structure (with pagination)
async function loadCloudFolder(url, append = false) {
  if (!url) {
    els.cloudFolderStatus.textContent = '⚠️ Enter URL';
    return;
  }
  
  // Reset pagination if loading new folder
  if (!append || cloudFolderPagination.url !== url) {
    cloudFolderPagination = {
      url: url,
      offset: 0,
      limit: 50,
      hasMore: false,
      total: 0,
      loadedFiles: []
    };
    els.cloudFolderContent.innerHTML = '';
  }
  
  els.cloudFolderStatus.textContent = append 
    ? `⏳ Loading more files... (${cloudFolderPagination.offset} loaded)`
    : '⏳ Loading folder...';
  
  // Declare endpointUrl outside try block for error handling
  let endpointUrl = '';
  
  try {
    // Use backend proxy to fetch folder structure (CORS issue)
    // Note: getApiBaseUrl() already includes /api, so we don't add it again
    const apiUrl = getApiBaseUrl();
    endpointUrl = `${apiUrl}/cloud/folder`;
    
    // Force HTTPS if current page is HTTPS
    if (window.location.protocol === 'https:' && endpointUrl.startsWith('http:')) {
      endpointUrl = endpointUrl.replace('http:', 'https:');
    }
    
    console.log('Fetching from:', endpointUrl);
    console.log('API Base URL:', apiUrl);
    console.log('Request URL:', url);
    console.log('Pagination:', { offset: cloudFolderPagination.offset, limit: cloudFolderPagination.limit });
    
    // Add timeout and error handling
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 60000); // 1 minute timeout (reduced for pagination)
    
    const response = await fetch(endpointUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ 
        url,
        limit: cloudFolderPagination.limit,
        offset: cloudFolderPagination.offset
      }),
      signal: controller.signal
    });
    
    clearTimeout(timeoutId);
    
    console.log('Response status:', response.status);
    console.log('Response ok:', response.ok);
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error('Response error:', errorText);
      throw new Error(`HTTP ${response.status}: ${errorText.substring(0, 100)}`);
    }
    
    const data = await response.json();
    console.log('Response data:', data);
    console.log('Items count:', data.items?.length);
    
    // Update pagination state
    cloudFolderPagination.offset = data.pagination?.offset || cloudFolderPagination.offset;
    cloudFolderPagination.hasMore = data.pagination?.has_more || false;
    cloudFolderPagination.total = data.pagination?.total || 0;
    
    // Add new items to loaded items (items = folders + files)
    if (data.items && data.items.length > 0) {
      cloudFolderPagination.loadedFiles.push(...data.items);
      console.log('Total loaded items:', cloudFolderPagination.loadedFiles.length);
    }
    
    // Render all loaded items
    console.log('Rendering with items:', cloudFolderPagination.loadedFiles.length);
    renderCloudFolder({
      items: cloudFolderPagination.loadedFiles,
      pagination: data.pagination
    });
    
    const loadedCount = cloudFolderPagination.loadedFiles.length;
    const totalCount = cloudFolderPagination.total || loadedCount;
    const foldersCount = cloudFolderPagination.loadedFiles.filter(i => i.type === 'folder').length;
    const filesCount = cloudFolderPagination.loadedFiles.filter(i => i.type === 'file').length;
    els.cloudFolderStatus.textContent = `✓ Loaded ${foldersCount} folders, ${filesCount} files${totalCount > loadedCount ? ` (${totalCount} total)` : ''}${cloudFolderPagination.hasMore ? ' - more available' : ''}`;
  } catch (error) {
    console.error('Error loading cloud folder:', error);
    console.error('Error details:', {
      name: error.name,
      message: error.message,
      stack: error.stack
    });
    
    let errorMessage = error.message;
    if (error.name === 'AbortError') {
      errorMessage = 'Request timeout - folder is too large or server is slow. This may take a while...';
    } else if (error.message === 'Failed to fetch') {
      // Check for Mixed Content error
      if (window.location.protocol === 'https:' && endpointUrl && endpointUrl.startsWith('http:')) {
        errorMessage = 'Mixed Content Error: HTTPS page cannot access HTTP API. Please use HTTPS for API.';
  } else {
        errorMessage = 'Cannot connect to server. Check if backend is running and accessible.';
      }
    }
    
    els.cloudFolderStatus.textContent = `❌ Error: ${errorMessage}`;
    if (!append) {
      els.cloudFolderContent.innerHTML = `<div style="color: rgb(255, 100, 100); padding: 10px;">
        Failed to load folder.<br/>
        Error: ${errorMessage}<br/>
        <small>Check browser console (F12) for details</small><br/>
        <small>API URL: ${endpointUrl || 'N/A'}</small><br/>
        <small>Window API_BASE_URL: ${window.API_BASE_URL || 'N/A'}</small>
      </div>`;
    }
  }
}

// Load more files (pagination)
async function loadMoreCloudFiles() {
  if (!cloudFolderPagination.hasMore || !cloudFolderPagination.url) {
    return;
  }
  
  cloudFolderPagination.offset += cloudFolderPagination.limit;
  await loadCloudFolder(cloudFolderPagination.url, true);
}

function renderCloudFolder(data) {
  console.log('renderCloudFolder called with:', data);
  console.log('items length:', data?.items?.length);
  
  if (!data || !data.items || data.items.length === 0) {
    els.cloudFolderContent.innerHTML = '<div style="padding: 10px; opacity: 0.7;">No items found</div>';
    return;
  }
  
  let html = '';
  
  // Filter box
  html += `<div style="margin-bottom: 10px; padding: 5px;">
    <input type="text" id="cloudFolderFilter" placeholder="🔍 Filter by name..." style="
      width: 100%;
      padding: 5px;
      background: rgba(0, 0, 0, 0.5);
      border: 1px solid var(--ui-color);
      color: var(--ui-color);
      font-family: 'Share Tech Mono', monospace;
      font-size: 0.9rem;
    " />
  </div>`;
  
  // Render items (folders and files) - LAZY: folders are expandable
  data.items.forEach(item => {
    if (item.type === 'folder') {
      // Folder - make it expandable
      html += `<div class="cloud-folder-expandable" style="
        padding: 8px 5px;
        cursor: pointer;
        user-select: none;
        border-left: 3px solid transparent;
        transition: all 0.2s;
      " data-folder-url="${item.url}" data-folder-name="${item.name}" onmouseover="this.style.borderLeftColor='var(--ui-color)'; this.style.background='rgba(255,0,0,0.1)';" onmouseout="this.style.borderLeftColor='transparent'; this.style.background='transparent';">
        <span class="folder-icon">📁</span>
        <span class="folder-name">${item.name}</span>
        <span class="folder-expand" style="float: right; opacity: 0.5; transition: transform 0.2s;">▶</span>
        <div class="folder-files" style="display: none; margin-left: 20px; padding-left: 10px; border-left: 2px solid var(--ui-color);">
          <div style="padding: 5px; opacity: 0.7;">⏳ Loading files...</div>
        </div>
      </div>`;
    } else {
      // File - clickable
      const icon = item.name.match(/\.(pdf|png|jpg|jpeg)$/i) ? 
        (item.name.match(/\.pdf$/i) ? '📄' : '🖼️') : '📄';
      html += `<div class="cloud-file-item" data-url="${item.url || item.download_url}" data-name="${item.name}" style="
        padding: 8px 5px;
        cursor: pointer;
        transition: all 0.2s;
        border-left: 2px solid transparent;
      " onmouseover="this.style.borderLeftColor='var(--ui-color)'; this.style.background='rgba(255,0,0,0.1)';" onmouseout="this.style.borderLeftColor='transparent'; this.style.background='transparent';">
        ${icon} ${item.name}
      </div>`;
    }
  });
  
  // Add "Load More" button if there are more files
  if (data.pagination && data.pagination.has_more) {
    html += `<div style="margin-top: 15px; text-align: center;">
      <button id="loadMoreCloudFiles" style="
        background: var(--ui-color);
        color: var(--bg-color);
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        cursor: pointer;
        font-size: 12px;
        font-weight: bold;
      ">📥 Load More Files (${data.pagination.total - cloudFolderPagination.loadedFiles.length} remaining)</button>
    </div>`;
  }
  
  els.cloudFolderContent.innerHTML = html;
  
  // Add filter functionality
  const filterInput = els.cloudFolderContent.querySelector('#cloudFolderFilter');
  if (filterInput) {
    filterInput.addEventListener('input', (e) => {
      const filter = e.target.value.toLowerCase().trim();
      const allItems = els.cloudFolderContent.querySelectorAll('.cloud-folder-expandable, .cloud-file-item');
      
      allItems.forEach(item => {
        const name = item.textContent.toLowerCase();
        if (filter === '' || name.includes(filter)) {
          item.style.display = '';
        } else {
          item.style.display = 'none';
        }
      });
    });
  }
  
  // Add click handlers for files
  els.cloudFolderContent.querySelectorAll('.cloud-file-item').forEach(item => {
    item.addEventListener('click', async () => {
      const fileUrl = item.dataset.url;
      const fileName = item.dataset.name;
      await loadFileFromCloud(fileUrl, fileName);
  playClick(400);
    });
  });
  
  // Add click handlers for expandable folders (LAZY loading)
  els.cloudFolderContent.querySelectorAll('.cloud-folder-expandable').forEach(folder => {
    folder.addEventListener('click', async (e) => {
      // Don't expand if clicking on files inside
      if (e.target.closest('.folder-files')) return;
      
      const folderUrl = folder.dataset.folderUrl;
      const folderName = folder.dataset.folderName;
      const expandIcon = folder.querySelector('.folder-expand');
      const filesContainer = folder.querySelector('.folder-files');
      
      // Toggle expand
      if (filesContainer.style.display === 'none') {
        // Expand - load files LAZY
        expandIcon.textContent = '▼';
        expandIcon.style.transform = 'rotate(90deg)';
        filesContainer.style.display = 'block';
        
        // Check if already loaded
        if (filesContainer.querySelector('.cloud-file-item') || filesContainer.querySelector('.cloud-folder-expandable')) {
          return; // Already loaded
        }
        
        // Load files from folder
        filesContainer.innerHTML = '<div style="padding: 5px; opacity: 0.7;">⏳ Loading files...</div>';
        try {
          const apiUrl = getApiBaseUrl();
          const endpointUrl = `${apiUrl}/cloud/folder/files`;
          
          const response = await fetch(endpointUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder_url: folderUrl, folder_name: folderName })
          });
          
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          
          const data = await response.json();
          let filesHtml = '';
          
          if (data.items && data.items.length > 0) {
            data.items.forEach(item => {
              if (item.type === 'folder') {
                filesHtml += `<div class="cloud-folder-expandable" style="padding: 5px; cursor: pointer;" data-folder-url="${item.url}" data-folder-name="${item.name}">
                  <span>📁 ${item.name}</span>
                  <span class="folder-expand" style="float: right; opacity: 0.5;">▶</span>
                  <div class="folder-files" style="display: none; margin-left: 20px; padding-left: 10px; border-left: 2px solid var(--ui-color);">
                    <div style="padding: 5px; opacity: 0.7;">Loading...</div>
                  </div>
                </div>`;
} else {
                const icon = item.name.match(/\.(pdf|png|jpg|jpeg)$/i) ? 
                  (item.name.match(/\.pdf$/i) ? '📄' : '🖼️') : '📄';
                filesHtml += `<div class="cloud-file-item" data-url="${item.url || item.download_url}" data-name="${item.name}" style="padding: 5px; cursor: pointer;">
                  ${icon} ${item.name}
                </div>`;
              }
    });
  } else {
            filesHtml = '<div style="padding: 5px; opacity: 0.7;">No files</div>';
          }
          
          filesContainer.innerHTML = filesHtml;
          
          // Re-attach event listeners for nested items
          filesContainer.querySelectorAll('.cloud-file-item').forEach(item => {
            item.addEventListener('click', async () => {
              await loadFileFromCloud(item.dataset.url, item.dataset.name);
    playClick(400);
  });
          });
          
          // Re-attach folder expand listeners recursively
          // Create a named function to avoid using arguments.callee (strict mode)
          const attachFolderListeners = (folderElement) => {
            folderElement.addEventListener('click', async (e) => {
              e.stopPropagation();
              const folderUrl = folderElement.dataset.folderUrl;
              const folderName = folderElement.dataset.folderName;
              
              if (!folderUrl) return;
              
              const expandIcon = folderElement.querySelector('.folder-expand');
              const filesContainer = folderElement.querySelector('.folder-files');
              
              if (!expandIcon || !filesContainer) return;
              
              const isExpanded = expandIcon.style.transform === 'rotate(90deg)';
              
              if (!isExpanded) {
                // Expand and load files
                expandIcon.textContent = '▼';
                expandIcon.style.transform = 'rotate(90deg)';
                filesContainer.style.display = 'block';
                filesContainer.innerHTML = '<div style="padding: 5px; opacity: 0.7;">⏳ Loading files...</div>';
                
                try {
                  const apiUrl = getApiBaseUrl();
                  const response = await fetch(`${apiUrl}/cloud/folder/files`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ folder_url: folderUrl, folder_name: folderName })
                  });
                  
                  if (!response.ok) throw new Error(`HTTP ${response.status}`);
                  
                  const data = await response.json();
                  let filesHtml = '';
                  
                  if (data.items && data.items.length > 0) {
                    data.items.forEach(item => {
                      const icon = item.type === 'folder' ? '📁' : 
                        (item.name.match(/\.(pdf|png|jpg|jpeg)$/i) ? 
                          (item.name.match(/\.pdf$/i) ? '📄' : '🖼️') : '📄');
                      const itemClass = item.type === 'folder' ? 'cloud-folder-expandable' : 'cloud-file-item';
                      filesHtml += `<div class="${itemClass}" data-${item.type === 'folder' ? 'folder' : ''}url="${item.url || item.download_url}" data-${item.type === 'folder' ? 'folder' : ''}name="${item.name}" style="padding: 5px; cursor: pointer; transition: all 0.2s;" onmouseover="this.style.background='rgba(255,0,0,0.1)'" onmouseout="this.style.background='transparent'">
                        ${icon} ${item.name}
                      </div>`;
  });
} else {
                    filesHtml = '<div style="padding: 5px; opacity: 0.7;">No files</div>';
                  }
                  
                  filesContainer.innerHTML = filesHtml;
                  
                  // Re-attach event listeners for nested items
                  filesContainer.querySelectorAll('.cloud-file-item').forEach(item => {
                    item.addEventListener('click', async () => {
                      await loadFileFromCloud(item.dataset.url, item.dataset.name);
      playClick(400);
    });
                  });
                  
                  // Recursively attach folder listeners
                  filesContainer.querySelectorAll('.cloud-folder-expandable').forEach(nestedFolder => {
                    attachFolderListeners(nestedFolder);
                  });
                } catch (error) {
                  filesContainer.innerHTML = `<div style="padding: 5px; color: rgb(255, 100, 100);">❌ Error loading folder</div>`;
                  console.error('Error loading folder files:', error);
                }
              } else {
                // Collapse
                expandIcon.textContent = '▶';
                expandIcon.style.transform = 'rotate(0deg)';
                filesContainer.style.display = 'none';
              }
    playClick(400);
  });
          };
          
          filesContainer.querySelectorAll('.cloud-folder-expandable').forEach(nestedFolder => {
            attachFolderListeners(nestedFolder);
          });
          
        } catch (error) {
          filesContainer.innerHTML = `<div style="padding: 5px; color: rgb(255, 100, 100);">❌ Error loading folder</div>`;
          console.error('Error loading folder files:', error);
        }
} else {
        // Collapse
        expandIcon.textContent = '▶';
        expandIcon.style.transform = 'rotate(0deg)';
        filesContainer.style.display = 'none';
      }
      playClick(400);
    });
  });
  
  // Add click handler for "Load More" button
  const loadMoreBtn = els.cloudFolderContent.querySelector('#loadMoreCloudFiles');
  if (loadMoreBtn) {
    loadMoreBtn.addEventListener('click', async () => {
      loadMoreBtn.disabled = true;
      loadMoreBtn.textContent = '⏳ Loading...';
      await loadMoreCloudFiles();
      playClick(400);
    });
  }
}

async function loadFileFromCloud(url, fileName) {
  try {
    els.cloudFolderStatus.textContent = `⏳ Loading ${fileName}...`;
    
    // Fetch file through backend proxy
    // Note: getApiBaseUrl() already includes /api, so we don't add it again
    const apiUrl = getApiBaseUrl();
    const endpointUrl = `${apiUrl}/cloud/file`;
    console.log('Fetching file from:', endpointUrl);
    
    const response = await fetch(endpointUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ url, fileName })
    });
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    const blob = await response.blob();
    
    // Validate blob
    if (!blob || blob.size === 0) {
      throw new Error('Downloaded file is empty');
    }
    
    // Check if blob is actually a PDF (check first bytes)
    if (fileName.match(/\.pdf$/i)) {
      const firstBytes = await blob.slice(0, 4).arrayBuffer();
      const pdfHeader = new Uint8Array(firstBytes);
      const isPdf = pdfHeader[0] === 0x25 && pdfHeader[1] === 0x50 && pdfHeader[2] === 0x44 && pdfHeader[3] === 0x46; // %PDF
      
      if (!isPdf) {
        console.warn('File does not appear to be a valid PDF (missing %PDF header)');
        log(`⚠️ Warning: File may not be a valid PDF`);
      }
      
      const file = new File([blob], fileName, { type: 'application/pdf' });
      
      // Use the same rendering approach as local file selection for consistency
      currentPdfFile = file;
      els.cloudFolderStatus.textContent = `⏳ Rendering ${fileName}...`;
      
      try {
        const preview = await pdfProcessor.renderPdfPreview(file, els.pdfCanvas);
        
        // Show preview (same logic as local file selection)
        if (typeof preview === 'string' && preview.startsWith('data:')) {
          // Image data URL - canvas was rendered successfully
          els.pdfPreview.innerHTML = `<img src="${preview}" style="max-width: 100%; height: auto;" />`;
          els.pdfCanvas.style.display = 'none';
        } else if (typeof preview === 'string') {
          // Object URL - use iframe fallback
          els.pdfPreview.innerHTML = `<iframe src="${preview}" style="width: 100%; height: 100%; border: none;"></iframe>`;
          els.pdfCanvas.style.display = 'none';
        } else {
          // Canvas was rendered directly, show it
          els.pdfPreview.innerHTML = '';
          els.pdfCanvas.style.display = 'block';
          if (!els.pdfCanvas.parentElement || els.pdfCanvas.parentElement !== els.pdfPreview) {
            els.pdfPreview.appendChild(els.pdfCanvas);
          }
        }
        
        els.pdfPreviewPlaceholder.style.display = 'none';
        els.pdfPreview.classList.remove('hidden');
        els.togglePdf.textContent = '📄 Hide Preview';
        
        els.cloudFolderStatus.textContent = `✓ Loaded ${fileName}`;
        log(`✓ Loaded PDF from cloud: ${fileName} (${(blob.size / 1024).toFixed(1)} KB)`);
        playTeleportFX();
      } catch (error) {
        console.error('Error rendering PDF from cloud:', error);
        els.cloudFolderStatus.textContent = `❌ Error rendering ${fileName}`;
        log(`❌ Error rendering PDF: ${error.message}`);
        // Fallback to handlePdfFile for error handling
        await handlePdfFile(file);
      }
    } 
    // Handle image files (convert to PDF-like canvas)
    else if (fileName.match(/\.(png|jpg|jpeg)$/i)) {
      const img = new Image();
      const imgUrl = URL.createObjectURL(blob);
      img.onload = () => {
        // Create a canvas and draw the image
        const canvas = document.createElement('canvas');
        canvas.width = img.width;
        canvas.height = img.height;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0);
        
        // Render directly on PDF canvas
        renderImageOnCanvas(canvas);
        els.cloudFolderStatus.textContent = `✓ Loaded ${fileName}`;
        log(`✓ Loaded image from cloud: ${fileName}`);
        URL.revokeObjectURL(imgUrl);
      };
      img.onerror = () => {
        els.cloudFolderStatus.textContent = `❌ Error loading ${fileName}`;
        URL.revokeObjectURL(imgUrl);
      };
      img.src = imgUrl;
    }
    
    playTeleportFX();
  } catch (error) {
    console.error('Error loading file from cloud:', error);
    els.cloudFolderStatus.textContent = `❌ Error loading ${fileName}`;
    log(`❌ Error loading file: ${error.message}`);
  }
}

async function handlePdfFile(file) {
  currentPdfFile = file;
  
  try {
    // Validate file before rendering
    if (!file || file.size === 0) {
      throw new Error('PDF file is empty');
    }
    
    // Render PDF on canvas
    const preview = await pdfProcessor.renderPdfPreview(file, els.pdfCanvas);
    
    // Clear preview and show it
    els.pdfPreviewPlaceholder.style.display = 'none';
    els.pdfPreview.classList.remove('hidden');
    els.togglePdf.textContent = '📄 Hide Preview';
    
    // If renderPdfPreview returned a URL (fallback), use iframe
    if (typeof preview === 'string' && !preview.startsWith('data:')) {
      // Object URL - use iframe with PDF.js viewer or direct PDF
      els.pdfPreview.innerHTML = `<iframe src="${preview}" style="width: 100%; height: 100%; border: none;" onerror="this.parentElement.innerHTML='<p style=\\'opacity: 0.6; text-align: center; padding: 20px;\\'>Failed to load PDF. File may be corrupted. Size: ${(file.size / 1024).toFixed(1)} KB</p>'"></iframe>`;
      els.pdfCanvas.style.display = 'none';
      log(`✓ PDF loaded (iframe fallback): ${file.name}`);
    } else if (typeof preview === 'string' && preview.startsWith('data:')) {
      // Image data URL - show as image (canvas was rendered successfully)
      els.pdfPreview.innerHTML = '';
      els.pdfCanvas.style.display = 'block';
      // Ensure canvas is in the preview container
      if (!els.pdfCanvas.parentElement || els.pdfCanvas.parentElement !== els.pdfPreview) {
        els.pdfPreview.appendChild(els.pdfCanvas);
      }
      // Also show as image for better compatibility
      const img = document.createElement('img');
      img.src = preview;
      img.style.cssText = 'max-width: 100%; height: auto; display: block;';
      els.pdfPreview.innerHTML = '';
      els.pdfPreview.appendChild(img);
      els.pdfCanvas.style.display = 'none';
      log(`✓ PDF loaded (canvas rendered): ${file.name}`);
    } else {
      // Canvas was rendered directly, show it
      els.pdfPreview.innerHTML = '';
      els.pdfCanvas.style.display = 'block';
      // Ensure canvas is in the preview container
      if (!els.pdfCanvas.parentElement || els.pdfCanvas.parentElement !== els.pdfPreview) {
        els.pdfPreview.appendChild(els.pdfCanvas);
      }
      log(`✓ PDF loaded (canvas direct): ${file.name}`);
    }
    
    playTeleportFX();
  } catch (error) {
    console.error('Error rendering PDF:', error);
    const errorMsg = error.message.includes('Invalid PDF') || error.message.includes('PDF structure') 
      ? `Invalid or corrupted PDF file: ${error.message}` 
      : `Error loading PDF: ${error.message}`;
    els.pdfPreview.innerHTML = `<p style="opacity: 0.6; text-align: center; padding: 20px;">${errorMsg}<br/>File: ${file.name} (${(file.size / 1024).toFixed(1)} KB)</p>`;
    els.pdfPreview.classList.remove('hidden');
    els.pdfPreviewPlaceholder.style.display = 'none';
    log(`❌ ${errorMsg}`);
  }
}

function renderImageOnCanvas(sourceCanvas) {
  // Scale canvas to fit preview while maintaining aspect ratio
  const maxWidth = 1200;
  const maxHeight = 800;
  let canvasWidth = sourceCanvas.width;
  let canvasHeight = sourceCanvas.height;
  
  // Calculate scale to fit
  const scale = Math.min(maxWidth / canvasWidth, maxHeight / canvasHeight, 1.0);
  canvasWidth = Math.floor(canvasWidth * scale);
  canvasHeight = Math.floor(canvasHeight * scale);
  
  // Set canvas size
  els.pdfCanvas.width = canvasWidth;
  els.pdfCanvas.height = canvasHeight;
  
  // Draw scaled image
  const ctx = els.pdfCanvas.getContext('2d');
  ctx.drawImage(sourceCanvas, 0, 0, canvasWidth, canvasHeight);
  
  // Show canvas in preview
  els.pdfPreview.innerHTML = '';
  els.pdfCanvas.style.display = 'block';
  els.pdfPreview.appendChild(els.pdfCanvas);
  els.pdfPreviewPlaceholder.style.display = 'none';
  els.pdfPreview.classList.remove('hidden');
  els.togglePdf.textContent = '📄 Hide Preview';
}

els.loadCloudFolderBtn.addEventListener("click", async () => {
  const url = els.cloudFolderUrl.value.trim();
  await loadCloudFolder(url);
  playClick(400);
});

// Auto-load on Enter
els.cloudFolderUrl.addEventListener("keypress", async (e) => {
  if (e.key === 'Enter') {
    const url = els.cloudFolderUrl.value.trim();
    await loadCloudFolder(url);
  }
});

// ========== PROGRESS DRAWER ==========
els.progressToggle.addEventListener("click", () => {
  els.progressDrawer.classList.toggle("open");
  playClick(400);
});

// ========== LOG DRAWER ==========
els.logToggle.addEventListener("click", () => {
  els.logDrawer.classList.toggle("open");
  playClick(400);
});

// ========== SETTINGS ==========
const settingsOverlay = document.getElementById("settingsOverlay");
const settingsBtn = document.getElementById("settingsBtn");
const saveSettings = document.getElementById("saveSettings");
const cancelSettings = document.getElementById("cancelSettings");

settingsBtn.addEventListener("click", () => {
  const ocrLanguage = document.getElementById("ocrLanguage");
  if (ocrLanguage) ocrLanguage.value = userSettings.ocrLanguage || "rus+eng";
  
  const humToggle = document.getElementById("humToggle");
  if (humToggle) humToggle.checked = userSettings.humEnabled;
  
  const autoTranslate = document.getElementById("autoTranslate");
  if (autoTranslate) autoTranslate.checked = userSettings.autoTranslate;
  
  const findSteelEquivalents = document.getElementById("findSteelEquivalents");
  if (findSteelEquivalents) findSteelEquivalents.checked = userSettings.findSteelEquivalents;
  
  const exportDocx = document.getElementById("exportDocx");
  if (exportDocx) exportDocx.checked = userSettings.exportDocx;
  
  const exportXlsx = document.getElementById("exportXlsx");
  if (exportXlsx) exportXlsx.checked = userSettings.exportXlsx;
  
  const exportPdf = document.getElementById("exportPdf");
  if (exportPdf) exportPdf.checked = userSettings.exportPdf;
  
  settingsOverlay.classList.remove("hidden");
  playClick(500);
  log("⚙️ Settings opened");
});

cancelSettings.addEventListener("click", () => {
  settingsOverlay.classList.add("hidden");
  playClick(350);
  log("❌ Settings closed (cancel)");
});

saveSettings.addEventListener("click", () => {
  userSettings.color = els.colorPicker.value;
  userSettings.humEnabled = document.getElementById("humToggle")?.checked ?? true;
  userSettings.ocrLanguage = document.getElementById("ocrLanguage")?.value || "rus+eng";
  userSettings.autoTranslate = document.getElementById("autoTranslate")?.checked ?? true;
  userSettings.findSteelEquivalents = document.getElementById("findSteelEquivalents")?.checked ?? true;
  userSettings.exportDocx = document.getElementById("exportDocx")?.checked ?? true;
  userSettings.exportXlsx = document.getElementById("exportXlsx")?.checked ?? true;
  userSettings.exportPdf = document.getElementById("exportPdf")?.checked ?? true;
  
  document.documentElement.style.setProperty("--ui-color", userSettings.color);
  if (userSettings.humEnabled) startHum();
  else stopHum();
  
  settingsOverlay.classList.add("hidden");
  log("💾 Settings saved");
  playTeleportFX();
});

settingsOverlay.addEventListener("click", (e) => {
  if (e.target === settingsOverlay) {
    settingsOverlay.classList.add("hidden");
    playClick(250);
  }
});

// Color picker
els.colorPicker.addEventListener("input", (e) => {
  document.documentElement.style.setProperty("--ui-color", e.target.value);
  playClick(420);
  log(`🎨 Theme color changed to ${e.target.value}`);
});

// ========== LANGUAGE TOGGLE ==========
const langToggle = document.getElementById("langToggle");
let currentLang = "en";

const translations = {
  en: {
    title: "📐 RETRO DRAWING ANALYZER",
    idle: "💤 Idle — waiting for input",
    selectPdf: "📎 Select PDF",
    process: "▶ Process Drawing",
    hidePreview: "📄 Hide Preview",
    showPreview: "📄 Show Preview",
    telegramChatId: "Telegram Chat ID (optional)",
    settings: "⚙️ Settings",
    extractedData: "EXTRACTED DATA",
    processingResults: "PROCESSING RESULTS",
    export: "📥 Export",
    steelEquivalents: "⚙️ STEEL EQUIVALENTS",
    telegram: "📱 TELEGRAM",
    logs: "📟 LOGS",
    searchSteel: "🔍 Search",
    searchSteelPlaceholder: "Search steel grade (e.g., 45ХНМФА)",
    testConnection: "📤 Test Connection",
    botToken: "Bot Token",
    telegramNotifications: "📱 TELEGRAM NOTIFICATIONS",
    approve: "✅ Approve",
    reject: "❌ Reject",
    close: "✖ Close",
    details: "Details:",
    filter: "🔍 Filter...",
  },
  ru: {
    title: "📐 РЕТРО АНАЛИЗАТОР ЧЕРТЕЖЕЙ",
    idle: "💤 Ожидание — ожидание ввода",
    selectPdf: "📎 Выбрать PDF",
    process: "▶ Обработать чертеж",
    hidePreview: "📄 Скрыть предпросмотр",
    showPreview: "📄 Показать предпросмотр",
    telegramChatId: "ID чата Telegram (необязательно)",
    settings: "⚙️ Настройки",
    extractedData: "ИЗВЛЕЧЕННЫЕ ДАННЫЕ",
    processingResults: "РЕЗУЛЬТАТЫ ОБРАБОТКИ",
    export: "📥 Экспорт",
    steelEquivalents: "⚙️ ЭКВИВАЛЕНТЫ СТАЛИ",
    telegram: "📱 ТЕЛЕГРАМ",
    logs: "📟 ЛОГИ",
    searchSteel: "🔍 Поиск",
    searchSteelPlaceholder: "Поиск марки стали (например, 45ХНМФА)",
    testConnection: "📤 Проверить соединение",
    botToken: "Токен бота",
    telegramNotifications: "📱 УВЕДОМЛЕНИЯ TELEGRAM",
    approve: "✅ Одобрить",
    reject: "❌ Отклонить",
    close: "✖ Закрыть",
    details: "Детали:",
    filter: "🔍 Фильтр...",
  },
};

function applyTranslation(lang) {
  currentLang = lang;
  const t = translations[lang];
  
  // Update title
  const h1 = document.querySelector("h1");
  if (h1) h1.textContent = t.title;
  
  // Update flag icon
  const flags = { en: "🇬🇧", ru: "🇷🇺" };
  if (langToggle) langToggle.textContent = flags[lang];
  
  // Update status line if it's idle
  const statusEl = document.getElementById("statusLine");
  if (statusEl) {
    const currentText = statusEl.textContent;
    if (currentText.includes("Idle") || currentText.includes("Ожидание") || 
        currentText === translations.en.idle || currentText === translations.ru.idle) {
      statusEl.textContent = t.idle;
    }
  }
  
  // Update buttons and controls
  const selectPdfBtn = document.getElementById("selectPdfBtn");
  if (selectPdfBtn) selectPdfBtn.textContent = t.selectPdf;
  
  const processBtn = document.getElementById("processBtn");
  if (processBtn) processBtn.textContent = t.process;
  
  const togglePdf = document.getElementById("togglePdf");
  if (togglePdf && !els.pdfPreview.classList.contains("hidden")) {
    togglePdf.textContent = t.hidePreview;
  } else if (togglePdf) {
    togglePdf.textContent = t.showPreview;
  }
  
  const telegramChatId = document.getElementById("telegramChatId");
  if (telegramChatId) telegramChatId.placeholder = t.telegramChatId;
  
  const settingsBtn = document.getElementById("settingsBtn");
  if (settingsBtn) settingsBtn.textContent = t.settings;
  
  // Update panel headers
  const extractedPanel = document.querySelector("#panel-extracted h2");
  if (extractedPanel) {
    const expandSpan = extractedPanel.querySelector(".expand") || document.createElement("span");
    if (!extractedPanel.querySelector(".expand")) {
      expandSpan.className = "expand";
      expandSpan.textContent = "⤡";
    }
    extractedPanel.innerHTML = `${t.extractedData} <span class="expand">⤡</span>`;
  }
  
  const resultsPanel = document.querySelector("#panel-results h2");
  if (resultsPanel) {
    const expandSpan = resultsPanel.querySelector(".expand") || document.createElement("span");
    if (!resultsPanel.querySelector(".expand")) {
      expandSpan.className = "expand";
      expandSpan.textContent = "⤡";
    }
    resultsPanel.innerHTML = `${t.processingResults} <span class="expand">⤡</span>`;
  }
  
  // Update export button
  const exportBtn = document.getElementById("exportBtn");
  if (exportBtn) exportBtn.textContent = t.export;
  
  // Update drawer toggles
  const steelToggle = document.getElementById("steelToggle");
  if (steelToggle) steelToggle.textContent = t.steelEquivalents;
  
  const telegramToggle = document.getElementById("telegramToggle");
  if (telegramToggle) telegramToggle.textContent = t.telegram;
  
  const logToggle = document.getElementById("logToggle");
  if (logToggle) logToggle.textContent = t.logs;
  
  // Update drawer headers
  const steelDrawerTitle = document.querySelector("#steelDrawer h2");
  if (steelDrawerTitle) steelDrawerTitle.textContent = t.steelEquivalents;
  
  const telegramDrawerTitle = document.querySelector("#telegramDrawer h2");
  if (telegramDrawerTitle) telegramDrawerTitle.textContent = t.telegramNotifications;
  
  const logDrawerTitle = document.querySelector("#logDrawer h2");
  if (logDrawerTitle) logDrawerTitle.textContent = "LOG TERMINAL";
  
  // Update steel drawer elements
  const steelSearch = document.getElementById("steelSearch");
  if (steelSearch) steelSearch.placeholder = t.searchSteelPlaceholder;
  
  const searchSteelBtn = document.getElementById("searchSteelBtn");
  if (searchSteelBtn) searchSteelBtn.textContent = t.searchSteel;
  
  // Update telegram drawer elements
  const telegramBotToken = document.getElementById("telegramBotToken");
  if (telegramBotToken) telegramBotToken.placeholder = t.botToken;
  
  const testTelegramBtn = document.getElementById("testTelegramBtn");
  if (testTelegramBtn) testTelegramBtn.textContent = t.testConnection;
  
  // Update modal elements
  const modalSearch = document.getElementById("modalSearch");
  if (modalSearch) modalSearch.placeholder = t.filter;
  
  const modalApprove = document.getElementById("modalApprove");
  if (modalApprove) modalApprove.textContent = t.approve;
  
  const modalReject = document.getElementById("modalReject");
  if (modalReject) modalReject.textContent = t.reject;
  
  const modalClose = document.getElementById("modalClose");
  if (modalClose) modalClose.textContent = t.close;
  
  // Update settings modal if it's open
  const settingsOverlay = document.getElementById("settingsOverlay");
  if (settingsOverlay && !settingsOverlay.classList.contains("hidden")) {
    const settingsTitle = document.querySelector("#settingsContent h2");
    if (settingsTitle) settingsTitle.textContent = t.settings;
  }
}

langToggle.addEventListener("click", () => {
  const langOrder = ["en", "ru"];
  const currentIndex = langOrder.indexOf(currentLang);
  const nextIndex = (currentIndex + 1) % langOrder.length;
  const newLang = langOrder[nextIndex];
  
  applyTranslation(newLang);
  playClick(450);
  log(`🌐 Language switched to ${newLang.toUpperCase()}`);
});

// ========== START HUM ==========
if (userSettings.humEnabled) {
  startHum();
  log("🟢 CRT hum started");
}

// Initial translation - run after DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => applyTranslation(currentLang));
} else {
  applyTranslation(currentLang);
}
