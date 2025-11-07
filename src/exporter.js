// Export functionality for DOCX, XLSX, PDF
// Creates formatted documents with extracted and translated data

import { API_BASE_URL } from './config.js';

/**
 * Generate DOCX export
 */
export async function exportToDocx(data, translations, steelEquivalents = {}) {
  try {
    const response = await fetch(`${API_BASE_URL}/export/docx`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        extractedData: data,
        translations: translations,
        steelEquivalents: steelEquivalents
      })
    });
    
    if (!response.ok) {
      throw new Error(`DOCX export failed: ${response.statusText}`);
    }
    
    const blob = await response.blob();
    return blob;
  } catch (error) {
    console.warn('DOCX export API not available, creating mock file:', error);
    // Fallback: create a simple text file
    const content = formatDataAsText(data, translations, steelEquivalents);
    return new Blob([content], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });
  }
}

/**
 * Generate XLSX export
 */
export async function exportToXlsx(data, translations, steelEquivalents = {}) {
  try {
    const response = await fetch(`${API_BASE_URL}/export/xlsx`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        extractedData: data,
        translations: translations,
        steelEquivalents: steelEquivalents
      })
    });
    
    if (!response.ok) {
      throw new Error(`XLSX export failed: ${response.statusText}`);
    }
    
    const blob = await response.blob();
    return blob;
  } catch (error) {
    console.warn('XLSX export API not available, creating mock file:', error);
    // Fallback: create CSV
    const content = formatDataAsCSV(data, translations, steelEquivalents);
    return new Blob([content], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
  }
}

/**
 * Generate PDF export with English overlay
 */
export async function exportToPdf(originalPdf, data, translations, steelEquivalents = {}) {
  try {
    const formData = new FormData();
    formData.append('pdf', originalPdf);
    formData.append('data', JSON.stringify({
      extractedData: data,
      translations: translations,
      steelEquivalents: steelEquivalents
    }));
    
    const response = await fetch(`${API_BASE_URL}/export/pdf`, {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      throw new Error(`PDF export failed: ${response.statusText}`);
    }
    
    const blob = await response.blob();
    return blob;
  } catch (error) {
    console.warn('PDF export API not available:', error);
    throw error;
  }
}

/**
 * Format data as text (fallback)
 */
function formatDataAsText(data, translations, steelEquivalents) {
  let content = 'DRAWING ANALYSIS REPORT\n';
  content += '='.repeat(50) + '\n\n';
  
  content += 'EXTRACTED DATA:\n';
  content += '-'.repeat(50) + '\n';
  content += `Materials: ${translations.materials.join(', ')}\n`;
  content += `Standards: ${translations.standards.join(', ')}\n`;
  content += `Surface Roughness (Ra): ${data.raValues.join(', ')}\n`;
  content += `Fits: ${data.fits.join(', ')}\n`;
  content += `Heat Treatment: ${translations.heatTreatment.join(', ')}\n\n`;
  
  if (Object.keys(steelEquivalents).length > 0) {
    content += 'STEEL GRADE EQUIVALENTS:\n';
    content += '-'.repeat(50) + '\n';
    for (const [grade, equiv] of Object.entries(steelEquivalents)) {
      if (equiv) {
        content += `${grade}: GOST ${equiv.gost || 'N/A'}, ASTM ${equiv.astm || 'N/A'}, ISO ${equiv.iso || 'N/A'}, GB/T ${equiv.gbt || 'N/A'}\n`;
      }
    }
    content += '\n';
  }
  
  content += 'TRANSLATED TEXT:\n';
  content += '-'.repeat(50) + '\n';
  content += translations.rawText;
  
  return content;
}

/**
 * Format data as CSV (fallback for XLSX)
 */
function formatDataAsCSV(data, translations, steelEquivalents) {
  let content = 'Category,Original,English\n';
  
  translations.materials.forEach((m, i) => {
    content += `Material,${data.materials[i] || ''},${m}\n`;
  });
  
  translations.standards.forEach((s, i) => {
    content += `Standard,${data.standards[i] || ''},${s}\n`;
  });
  
  data.raValues.forEach(ra => {
    content += `Surface Roughness,Ra ${ra},Ra ${ra}\n`;
  });
  
  data.fits.forEach(fit => {
    content += `Fit,${fit},${fit}\n`;
  });
  
  translations.heatTreatment.forEach((h, i) => {
    content += `Heat Treatment,${data.heatTreatment[i] || ''},${h}\n`;
  });
  
  return content;
}

/**
 * Download file
 */
export function downloadFile(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

