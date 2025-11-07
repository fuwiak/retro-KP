// Translation Service with Technical Glossary
// Translates Russian technical terms to English

/**
 * Technical glossary for engineering/drawing terms
 */
const TECHNICAL_GLOSSARY = {
  // Materials
  'сталь': 'steel',
  'Сталь': 'Steel',
  'Ст.': 'Steel',
  'марка': 'grade',
  'Марка': 'Grade',
  
  // Standards
  'ГОСТ': 'GOST',
  'ОСТ': 'OST',
  'ТУ': 'TU',
  
  // Surface roughness
  'шероховатость': 'surface roughness',
  'Шероховатость': 'Surface Roughness',
  'Ra': 'Ra',
  'Rz': 'Rz',
  
  // Fits
  'посадка': 'fit',
  'Посадка': 'Fit',
  
  // Heat treatment
  'термообработка': 'heat treatment',
  'Термообработка': 'Heat Treatment',
  'закалка': 'hardening',
  'Закалка': 'Hardening',
  'отпуск': 'tempering',
  'Отпуск': 'Tempering',
  'нормализация': 'normalization',
  'Нормализация': 'Normalization',
  'отжиг': 'annealing',
  'Отжиг': 'Annealing',
  
  // Common phrases
  'Материал': 'Material',
  'материал': 'material',
  'Размер': 'Size',
  'размер': 'size',
  'Допуск': 'Tolerance',
  'допуск': 'tolerance',
  'Размеры': 'Dimensions',
  'размеры': 'dimensions',
  'Чертеж': 'Drawing',
  'чертеж': 'drawing',
  'Деталь': 'Part',
  'деталь': 'part'
};

/**
 * Translate text using Groq AI with technical glossary
 */
export async function translateToEnglish(text, useGlossary = true) {
  try {
    // First apply technical glossary
    let translated = text;
    if (useGlossary) {
      for (const [ru, en] of Object.entries(TECHNICAL_GLOSSARY)) {
        const regex = new RegExp(`\\b${ru.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'gi');
        translated = translated.replace(regex, en);
      }
    }
    
    // Use Groq AI for translation
    try {
      const { translateTechnicalText } = await import('./groqAgent.js');
      const aiTranslated = await translateTechnicalText(translated, 'ru');
      return aiTranslated;
    } catch (groqError) {
      console.warn('Groq translation failed, trying API fallback:', groqError);
      
      // Fallback to API
      const { API_BASE_URL } = await import('./config.js');
      try {
        const response = await fetch(`${API_BASE_URL}/translate`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            text: translated,
            from: 'ru',
            to: 'en'
          })
        });
        
        if (response.ok) {
          const result = await response.json();
          return result.translatedText || translated;
        }
      } catch (apiError) {
        console.warn('Translation API also failed, using glossary only');
      }
    }
    
    return translated;
  } catch (error) {
    console.error('Translation error:', error);
    return text; // Return original if translation fails
  }
}

/**
 * Translate extracted data structure
 */
export async function translateExtractedData(data) {
  const translated = {
    materials: await Promise.all(data.materials.map(m => translateToEnglish(m))),
    standards: await Promise.all(data.standards.map(s => translateToEnglish(s))),
    raValues: data.raValues, // Numbers don't need translation
    fits: data.fits, // Already in standard format
    heatTreatment: await Promise.all(data.heatTreatment.map(h => translateToEnglish(h))),
    rawText: await translateToEnglish(data.rawText)
  };
  
  return translated;
}

