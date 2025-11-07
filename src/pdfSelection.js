// PDF Selection Module
// Provides rectangle and text selection functionality similar to react-pdf-selection
// Built on top of PDF.js

import * as pdfjsModule from 'pdfjs-dist';

let pdfjsLib = null;
let currentPdf = null;
let currentPage = null;
let viewport = null;

/**
 * Get PDF.js library
 */
async function getPdfJs() {
  if (!pdfjsLib) {
    // Try npm package first
    if (pdfjsModule && typeof pdfjsModule.getDocument === 'function') {
      pdfjsLib = pdfjsModule;
    } else if (pdfjsModule.default && typeof pdfjsModule.default.getDocument === 'function') {
      pdfjsLib = pdfjsModule.default;
    }
    // Fallback to CDN
    else if (typeof window !== 'undefined') {
      pdfjsLib = window.pdfjsLib || window.pdfjs || null;
    }
    
    // Configure worker (must be async)
    if (pdfjsLib && pdfjsLib.GlobalWorkerOptions) {
      try {
        // Use worker from npm package via Vite
        const workerModule = await import('pdfjs-dist/build/pdf.worker.min.mjs?url');
        pdfjsLib.GlobalWorkerOptions.workerSrc = workerModule.default || workerModule;
        console.log('PDF.js worker configured from npm package');
      } catch (workerError) {
        // Fallback to URL constructor
        try {
          pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
            'pdfjs-dist/build/pdf.worker.min.mjs',
            import.meta.url
          ).href;
          console.log('PDF.js worker configured using URL constructor');
        } catch (urlError) {
          // Final fallback to CDN
          try {
            pdfjsLib.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version || '4.0.379'}/pdf.worker.min.js`;
            console.log('PDF.js worker fallback to CDN');
          } catch (cdnError) {
            console.warn('Could not configure PDF.js worker:', cdnError);
          }
        }
      }
    }
  }
  return pdfjsLib;
}

/**
 * Initialize PDF for selection
 */
export async function initPdfSelection(file, pageNumber = 1) {
  try {
    const pdfjs = await getPdfJs();
    if (!pdfjs) {
      throw new Error('PDF.js not available');
    }

    const arrayBuffer = await file.arrayBuffer();
    currentPdf = await pdfjs.getDocument({ data: arrayBuffer }).promise;
    currentPage = await currentPdf.getPage(pageNumber);
    viewport = currentPage.getViewport({ scale: 2.0 });

    return {
      pdf: currentPdf,
      page: currentPage,
      viewport: viewport,
      numPages: currentPdf.numPages
    };
  } catch (error) {
    console.error('Error initializing PDF selection:', error);
    throw error;
  }
}

/**
 * Create rectangle selection on canvas
 */
export class RectangleSelection {
  constructor(canvas, options = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.options = {
      color: options.color || 'rgba(255, 0, 0, 0.3)',
      borderColor: options.borderColor || 'rgb(255, 0, 0)',
      borderWidth: options.borderWidth || 2,
      minWidth: options.minWidth || 10,
      minHeight: options.minHeight || 10,
      ...options
    };

    this.isSelecting = false;
    this.startX = 0;
    this.startY = 0;
    this.currentX = 0;
    this.currentY = 0;
    this.selection = null;

    this.setupEventListeners();
  }

  setupEventListeners() {
    this.canvas.addEventListener('mousedown', this.onMouseDown.bind(this));
    this.canvas.addEventListener('mousemove', this.onMouseMove.bind(this));
    this.canvas.addEventListener('mouseup', this.onMouseUp.bind(this));
    this.canvas.addEventListener('mouseleave', this.onMouseLeave.bind(this));
  }

  onMouseDown(e) {
    console.log('RectangleSelection onMouseDown:', { isSelecting: this.isSelecting, canvasWidth: this.canvas.width, canvasHeight: this.canvas.height });
    if (!this.isSelecting) {
      const rect = this.canvas.getBoundingClientRect();
      const scaleX = this.canvas.width / rect.width;
      const scaleY = this.canvas.height / rect.height;

      this.isSelecting = true;
      this.startX = (e.clientX - rect.left) * scaleX;
      this.startY = (e.clientY - rect.top) * scaleY;
      this.currentX = this.startX;
      this.currentY = this.startY;
      console.log('RectangleSelection: Selection started at', this.startX, this.startY);
    }
  }

  onMouseMove(e) {
    if (this.isSelecting) {
      const rect = this.canvas.getBoundingClientRect();
      const scaleX = this.canvas.width / rect.width;
      const scaleY = this.canvas.height / rect.height;

      this.currentX = (e.clientX - rect.left) * scaleX;
      this.currentY = (e.clientY - rect.top) * scaleY;
      this.drawSelection();
    }
  }

  onMouseUp(e) {
    if (this.isSelecting) {
      this.isSelecting = false;
      this.finalizeSelection();
    }
  }

  onMouseLeave(e) {
    if (this.isSelecting) {
      this.isSelecting = false;
      this.finalizeSelection();
    }
  }

  drawSelection() {
    // Return selection bounds for rendering on overlay canvas
    // Don't draw directly on source canvas
    const x = Math.min(this.startX, this.currentX);
    const y = Math.min(this.startY, this.currentY);
    const width = Math.abs(this.currentX - this.startX);
    const height = Math.abs(this.currentY - this.startY);
    
    // Store current selection for rendering
    this.currentSelection = { x, y, width, height };
    
    // Trigger callback if provided
    if (this.options.onSelectionUpdate) {
      this.options.onSelectionUpdate(this.currentSelection);
    }
  }
  
  getCurrentSelection() {
    return this.currentSelection;
  }

  finalizeSelection() {
    const x = Math.min(this.startX, this.currentX);
    const y = Math.min(this.startY, this.currentY);
    const width = Math.abs(this.currentX - this.startX);
    const height = Math.abs(this.currentY - this.startY);

    if (width >= this.options.minWidth && height >= this.options.minHeight) {
      this.selection = {
        x: x,
        y: y,
        width: width,
        height: height,
        type: 'rectangle'
      };

      if (this.options.onSelection) {
        this.options.onSelection(this.selection);
      }
    } else {
      this.selection = null;
    }
  }

  clear() {
    this.selection = null;
    this.isSelecting = false;
  }

  getSelection() {
    return this.selection;
  }
}

/**
 * Extract text from selected area in PDF
 */
export async function extractTextFromSelection(file, selection, pageNumber = 1) {
  try {
    const pdfjs = await getPdfJs();
    if (!pdfjs || !currentPage || !viewport) {
      // Reinitialize if needed
      await initPdfSelection(file, pageNumber);
    }

    const textContent = await currentPage.getTextContent();
    const selectedText = [];

    // Convert canvas coordinates to PDF coordinates
    const pdfX = (selection.x / viewport.width) * viewport.width;
    const pdfY = (selection.y / viewport.height) * viewport.height;
    const pdfWidth = (selection.width / viewport.width) * viewport.width;
    const pdfHeight = (selection.height / viewport.height) * viewport.height;

    // Find text items within selection bounds
    for (const item of textContent.items) {
      if (item.transform) {
        // Transform matrix gives position
        const x = item.transform[4];
        const y = item.transform[5];

        if (x >= pdfX && x <= pdfX + pdfWidth &&
            y >= pdfY - pdfHeight && y <= pdfY) {
          selectedText.push(item.str);
        }
      }
    }

    return selectedText.join(' ');
  } catch (error) {
    console.error('Error extracting text from selection:', error);
    return '';
  }
}

/**
 * Extract selected area as image
 */
export function extractSelectionAsImage(sourceCanvas, selection) {
  if (!selection || !sourceCanvas) return null;

  const { x, y, width, height } = selection;

  // Create new canvas for cropped area
  const croppedCanvas = document.createElement('canvas');
  croppedCanvas.width = width;
  croppedCanvas.height = height;

  const ctx = croppedCanvas.getContext('2d');
  ctx.drawImage(
    sourceCanvas,
    x, y, width, height,
    0, 0, width, height
  );

  return croppedCanvas.toDataURL('image/png');
}

/**
 * Get selection coordinates in PDF page coordinates
 */
export function getPdfCoordinates(selection, viewport) {
  if (!selection || !viewport) return null;

  return {
    x: (selection.x / viewport.width) * viewport.width,
    y: (selection.y / viewport.height) * viewport.height,
    width: (selection.width / viewport.width) * viewport.width,
    height: (selection.height / viewport.height) * viewport.height,
    page: 1 // Default to page 1 for now
  };
}

/**
 * Render selection overlay on separate canvas
 */
export function renderSelectionOverlay(overlayCanvas, sourceCanvas, selection) {
  if (!overlayCanvas || !sourceCanvas || !selection) return;

  const ctx = overlayCanvas.getContext('2d');
  
  // Match dimensions
  overlayCanvas.width = sourceCanvas.width;
  overlayCanvas.height = sourceCanvas.height;

  // Clear previous
  ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);

  // Draw selection rectangle
  const { x, y, width, height } = selection;
  
  // Fill
  ctx.fillStyle = 'rgba(255, 0, 0, 0.2)';
  ctx.fillRect(x, y, width, height);

  // Border
  ctx.strokeStyle = 'rgb(255, 0, 0)';
  ctx.lineWidth = 3;
  ctx.setLineDash([]);
  ctx.strokeRect(x, y, width, height);

  // Corner handles
  const handleSize = 8;
  ctx.fillStyle = 'rgb(255, 0, 0)';
  
  // Top-left
  ctx.fillRect(x - handleSize/2, y - handleSize/2, handleSize, handleSize);
  // Top-right
  ctx.fillRect(x + width - handleSize/2, y - handleSize/2, handleSize, handleSize);
  // Bottom-left
  ctx.fillRect(x - handleSize/2, y + height - handleSize/2, handleSize, handleSize);
  // Bottom-right
  ctx.fillRect(x + width - handleSize/2, y + height - handleSize/2, handleSize, handleSize);
}

