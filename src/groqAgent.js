// Groq AI Agent with Multiple Fallbacks
// Handles OCR, translation, data extraction with fallback models

const GROQ_API_KEY = import.meta.env.VITE_GROQ_API_KEY || '';
const GROQ_API_BASE = 'https://api.groq.com/openai/v1';

// Model priority list with fallbacks
export const OCR_MODELS = [
  'groq/compound',           // Best for complex tasks
  'llama-3.3-70b-versatile', // High quality
  'llama-3.1-8b-instant',    // Fast fallback
];

const TRANSLATION_MODELS = [
  'llama-3.3-70b-versatile', // Best quality
  'llama-3.1-8b-instant',    // Fast
  'openai/gpt-oss-20b',      // Fallback
];

const EXTRACTION_MODELS = [
  'groq/compound',           // Best for structured extraction
  'llama-3.3-70b-versatile',
  'llama-3.1-8b-instant',
];

/**
 * Call Groq API with fallback models
 */
async function callGroqAPI(models, messages, options = {}, progressCallback = null) {
  if (!GROQ_API_KEY) {
    throw new Error('Groq API key not configured. Set VITE_GROQ_API_KEY in .env');
  }

  let lastError = null;
  
  for (let i = 0; i < models.length; i++) {
    const model = models[i];
    try {
      if (progressCallback) {
        progressCallback(`Trying model ${i + 1}/${models.length}: ${model}...`);
      }
      
      const requestBody = {
        model: model,
        messages: messages,
        temperature: options.temperature || 0.3,
        max_tokens: options.max_tokens || 4096,
        ...options
      };
      
      if (progressCallback) {
        progressCallback(`Sending request to ${model}...`);
      }
      
      const response = await fetch(`${GROQ_API_BASE}/chat/completions`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${GROQ_API_KEY}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody)
      });

      if (progressCallback) {
        progressCallback(`Received response from ${model} (status: ${response.status})...`);
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const errorMsg = errorData.error?.message || `HTTP ${response.status}`;
        if (progressCallback) {
          progressCallback(`❌ ${model} failed: ${errorMsg}`);
        }
        throw new Error(errorMsg);
      }

      if (progressCallback) {
        progressCallback(`Parsing response from ${model}...`);
      }
      
      const data = await response.json();
      if (data.choices && data.choices[0] && data.choices[0].message) {
        if (progressCallback) {
          progressCallback(`✅ Success with ${model}`);
          if (data.usage) {
            progressCallback(`📊 Tokens: ${data.usage.prompt_tokens} input + ${data.usage.completion_tokens} output = ${data.usage.total_tokens} total`);
          }
        }
        return {
          content: data.choices[0].message.content,
          model: model,
          usage: data.usage
        };
      }
      
      throw new Error('Invalid response format');
    } catch (error) {
      lastError = error;
      if (progressCallback && i < models.length - 1) {
        progressCallback(`⚠️ ${model} failed, trying next model...`);
      }
      console.warn(`Model ${model} failed:`, error.message);
      // Continue to next model
      continue;
    }
  }
  
  throw new Error(`All models failed. Last error: ${lastError?.message || 'Unknown error'}`);
}

/**
 * Convert file to image data URL
 */
async function fileToImageData(file) {
  if (file.type && file.type.startsWith('image/')) {
    // Already an image
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  } else {
    // PDF - convert to image
    return await pdfToImageData(file);
  }
}

/**
 * Process PDF with OCR using AI
 */
export async function processPdfOCR(file, languages = ['rus', 'eng'], progressCallback = null) {
  try {
    // Convert PDF to image/base64
    const imageData = await pdfToImageData(file);
    
    const langStr = languages.join(' + ');
    const messages = [
      {
        role: 'system',
        content: `You are an expert OCR system for technical engineering drawings. Extract ALL text from the image, preserving exact formatting, numbers, and technical terms. Support ${langStr} languages. Return ONLY the extracted text, no explanations.`
      },
      {
        role: 'user',
        content: [
          {
            type: 'text',
            text: `Extract all text from this engineering drawing PDF. Languages: ${langStr}. Include: materials, standards (GOST/OST/TU), surface roughness (Ra), fits, heat treatment, dimensions, and all technical annotations.`
          },
          {
            type: 'image_url',
            image_url: {
              url: imageData
            }
          }
        ]
      }
    ];

    const result = await callGroqAPI(OCR_MODELS, messages, {
      max_tokens: 8192
    });

    return {
      text: result.content,
      confidence: 0.9,
      language: languages.join('+'),
      pages: 1,
      model: result.model
    };
  } catch (error) {
    console.error('OCR processing error:', error);
    throw new Error(`OCR failed: ${error.message}`);
  }
}

/**
 * Process image with OCR using AI (for cropped areas)
 */
export async function processImageOCR(file, languages = ['rus', 'eng'], progressCallback = null) {
  try {
    // Convert image to base64
    const imageData = await fileToImageData(file);
    
    const langStr = languages.join(' + ');
    const messages = [
      {
        role: 'system',
        content: `You are an expert OCR system for technical engineering drawings. Extract ALL text from this cropped area of the drawing, preserving exact formatting, numbers, and technical terms. Support ${langStr} languages. Return ONLY the extracted text, no explanations.`
      },
      {
        role: 'user',
        content: [
          {
            type: 'text',
            text: `Extract all text from this cropped area of the engineering drawing. Languages: ${langStr}. Focus on: materials, standards (GOST/OST/TU), surface roughness (Ra), fits, heat treatment, dimensions, and all technical annotations visible in this area.`
          },
          {
            type: 'image_url',
            image_url: {
              url: imageData
            }
          }
        ]
      }
    ];

    const result = await callGroqAPI(OCR_MODELS, messages, {
      max_tokens: 8192
    }, progressCallback);

    return {
      text: result.content,
      confidence: 0.9,
      language: languages.join('+'),
      pages: 1,
      model: result.model,
      isCropped: true
    };
  } catch (error) {
    console.error('Image OCR processing error:', error);
    throw new Error(`Image OCR failed: ${error.message}`);
  }
}

/**
 * Convert PDF file to image data URL for vision models
 */
async function pdfToImageData(file) {
  try {
    // Try to use PDF.js from npm package first
    let pdfjs = null;
    try {
      const pdfjsModule = await import('pdfjs-dist');
      if (pdfjsModule && typeof pdfjsModule.getDocument === 'function') {
        pdfjs = pdfjsModule;
      } else if (pdfjsModule.default && typeof pdfjsModule.default.getDocument === 'function') {
        pdfjs = pdfjsModule.default;
      }
    } catch (importError) {
      // Fallback to CDN
      if (typeof window !== 'undefined') {
        pdfjs = window.pdfjsLib || window.pdfjs || null;
      }
    }
    
    if (pdfjs && typeof pdfjs.getDocument === 'function') {
      const arrayBuffer = await file.arrayBuffer();
      const pdf = await pdfjs.getDocument({ data: arrayBuffer }).promise;
      const page = await pdf.getPage(1);
      const viewport = page.getViewport({ scale: 2.0 });
      
      const canvas = document.createElement('canvas');
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      
      const context = canvas.getContext('2d');
      await page.render({
        canvasContext: context,
        viewport: viewport
      }).promise;
      
      return canvas.toDataURL('image/png');
    }
  } catch (e) {
    console.warn('PDF.js not available for image conversion:', e);
  }
  
  // Fallback: return file as base64 (may not work for all models)
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      // Convert to base64 data URL
      const base64 = btoa(String.fromCharCode(...new Uint8Array(reader.result)));
      resolve(`data:application/pdf;base64,${base64}`);
    };
    reader.onerror = reject;
    reader.readAsArrayBuffer(file);
  });
}

/**
 * Translate text to English with technical glossary
 */
export async function translateTechnicalText(text, fromLang = 'ru') {
  try {
    const messages = [
      {
        role: 'system',
        content: `You are a technical translation expert specializing in engineering and manufacturing terminology. Translate technical Russian text to English, preserving:
- Technical terms (use standard English equivalents)
- Standards (GOST → GOST, preserve numbers)
- Material grades (e.g., Сталь 45 → Steel 45)
- Dimensions and tolerances (keep exact numbers)
- Surface roughness values (Ra, Rz)
- Fit designations (H7/f7)
- Heat treatment terms

Return ONLY the translated text, no explanations or notes.`
      },
      {
        role: 'user',
        content: `Translate this technical text from ${fromLang} to English:\n\n${text}`
      }
    ];

    const result = await callGroqAPI(TRANSLATION_MODELS, messages, {
      temperature: 0.2,
      max_tokens: 4096
    });

    return result.content;
  } catch (error) {
    console.error('Translation error:', error);
    throw new Error(`Translation failed: ${error.message}`);
  }
}

/**
 * Extract structured data from OCR text using AI
 */
export async function extractStructuredData(ocrText) {
  try {
    const messages = [
      {
        role: 'system',
        content: `You are an expert at extracting technical data from engineering drawings. Extract and return JSON with this exact structure:
{
  "materials": ["array of material grades"],
  "standards": ["array of GOST/OST/TU standards"],
  "raValues": [array of surface roughness Ra values as numbers],
  "fits": ["array of fit designations like H7/f7"],
  "heatTreatment": ["array of heat treatment specifications"]
}

Extract ALL instances. Return ONLY valid JSON, no explanations.`
      },
      {
        role: 'user',
        content: `Extract technical data from this OCR text:\n\n${ocrText}`
      }
    ];

    const result = await callGroqAPI(EXTRACTION_MODELS, messages, {
      temperature: 0.1,
      max_tokens: 4096,
      response_format: { type: 'json_object' }
    });

    try {
      const data = JSON.parse(result.content);
      return {
        materials: Array.isArray(data.materials) ? data.materials : [],
        standards: Array.isArray(data.standards) ? data.standards : [],
        raValues: Array.isArray(data.raValues) ? data.raValues.map(Number).filter(n => !isNaN(n)) : [],
        fits: Array.isArray(data.fits) ? data.fits : [],
        heatTreatment: Array.isArray(data.heatTreatment) ? data.heatTreatment : [],
        rawText: ocrText
      };
    } catch (parseError) {
      // Fallback: try to extract JSON from text
      const jsonMatch = result.content.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        return JSON.parse(jsonMatch[0]);
      }
      throw new Error('Failed to parse AI response as JSON');
    }
  } catch (error) {
    console.error('Data extraction error:', error);
    throw new Error(`Data extraction failed: ${error.message}`);
  }
}

/**
 * Find steel grade equivalents using AI
 */
export async function findSteelEquivalents(steelGrade) {
  try {
    const messages = [
      {
        role: 'system',
        content: `You are a materials engineering expert. For a given Russian steel grade (GOST), find international equivalents. Return JSON:
{
  "gost": "original GOST standard",
  "astm": "ASTM equivalent or N/A",
  "iso": "ISO equivalent or N/A",
  "gbt": "GB/T equivalent or N/A",
  "description": "brief description in English"
}

Return ONLY valid JSON, no explanations.`
      },
      {
        role: 'user',
        content: `Find international equivalents for this steel grade: ${steelGrade}`
      }
    ];

    const result = await callGroqAPI(EXTRACTION_MODELS, messages, {
      temperature: 0.2,
      max_tokens: 2048,
      response_format: { type: 'json_object' }
    });

    const data = JSON.parse(result.content);
    return {
      grade: steelGrade,
      ...data
    };
  } catch (error) {
    console.error('Steel equivalent lookup error:', error);
    return null;
  }
}

/**
 * Generate export document content using AI
 */
export async function generateExportContent(data, translations, steelEquivalents) {
  try {
    const messages = [
      {
        role: 'system',
        content: `You are a technical documentation expert. Generate a well-structured technical report from extracted drawing data. Format it professionally with clear sections.`
      },
      {
        role: 'user',
        content: `Generate a technical report from this data:
Materials: ${translations.materials.join(', ')}
Standards: ${translations.standards.join(', ')}
Surface Roughness: Ra ${data.raValues.join(', ')}
Fits: ${data.fits.join(', ')}
Heat Treatment: ${translations.heatTreatment.join(', ')}

${Object.keys(steelEquivalents).length > 0 ? `Steel Equivalents:\n${JSON.stringify(steelEquivalents, null, 2)}` : ''}

Create a professional technical report in English.`
      }
    ];

    const result = await callGroqAPI(['llama-3.3-70b-versatile', 'llama-3.1-8b-instant'], messages, {
      temperature: 0.3,
      max_tokens: 4096
    });

    return result.content;
  } catch (error) {
    console.error('Export content generation error:', error);
    throw new Error(`Export generation failed: ${error.message}`);
  }
}

