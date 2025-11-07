// Steel Grade Equivalents Lookup
// Maps Russian steel grades to GB/T, ASTM, ISO equivalents

/**
 * Steel grade equivalents database
 */
const STEEL_EQUIVALENTS = {
  '45': {
    gost: 'ГОСТ 1050-2013',
    astm: '1045',
    iso: 'C45',
    gbt: 'GB/T 699-2015 45',
    description: 'Medium carbon steel'
  },
  '40Х': {
    gost: 'ГОСТ 4543-2016',
    astm: '4140',
    iso: '42CrMo4',
    gbt: 'GB/T 3077-2015 40Cr',
    description: 'Chromium steel'
  },
  '45ХНМФА': {
    gost: 'ГОСТ 4543-2016',
    astm: '4340',
    iso: '40NiCrMo7',
    gbt: 'GB/T 3077-2015 40CrNiMoA',
    description: 'Nickel-chromium-molybdenum steel'
  },
  '30ХГСА': {
    gost: 'ГОСТ 4543-2016',
    astm: '4130',
    iso: '25CrMo4',
    gbt: 'GB/T 3077-2015 30CrMnSiA',
    description: 'Chromium-manganese-silicon steel'
  },
  '12Х18Н10Т': {
    gost: 'ГОСТ 5632-2014',
    astm: '321',
    iso: 'X6CrNiTi18-10',
    gbt: 'GB/T 20878-2007 12Cr18Ni9Ti',
    description: 'Austenitic stainless steel'
  },
  '08Х18Н10': {
    gost: 'ГОСТ 5632-2014',
    astm: '304',
    iso: 'X5CrNi18-10',
    gbt: 'GB/T 20878-2007 06Cr19Ni10',
    description: 'Austenitic stainless steel'
  },
  '20': {
    gost: 'ГОСТ 1050-2013',
    astm: '1020',
    iso: 'C20',
    gbt: 'GB/T 699-2015 20',
    description: 'Low carbon steel'
  },
  '65Г': {
    gost: 'ГОСТ 14959-2016',
    astm: '1065',
    iso: 'C67',
    gbt: 'GB/T 1222-2016 65Mn',
    description: 'Manganese spring steel'
  }
};

/**
 * Normalize steel grade name for lookup
 */
function normalizeSteelGrade(grade) {
  // Remove common prefixes and whitespace
  return grade
    .replace(/^(сталь|Ст\.?|марка|Марка)\s*/i, '')
    .replace(/\s+/g, '')
    .toUpperCase()
    .replace(/[А-Я]/g, char => {
      // Convert Cyrillic to Latin where applicable
      const map = {
        'А': 'A', 'В': 'B', 'Е': 'E', 'К': 'K', 'М': 'M', 'Н': 'H',
        'О': 'O', 'Р': 'P', 'С': 'C', 'Т': 'T', 'У': 'Y', 'Х': 'X'
      };
      return map[char] || char;
    });
}

/**
 * Find equivalents for a steel grade
 * Uses AI first, falls back to database
 */
export async function findSteelEquivalents(grade) {
  // Try AI lookup first
  try {
    const { findSteelEquivalents: aiFind } = await import('./groqAgent.js');
    const aiResult = await aiFind(grade);
    if (aiResult) {
      return aiResult;
    }
  } catch (error) {
    console.warn('AI steel lookup failed, using database:', error);
  }
  
  // Fallback to database
  const normalized = normalizeSteelGrade(grade);
  
  // Direct match
  if (STEEL_EQUIVALENTS[grade]) {
    return STEEL_EQUIVALENTS[grade];
  }
  
  // Try normalized match
  for (const [key, value] of Object.entries(STEEL_EQUIVALENTS)) {
    if (normalizeSteelGrade(key) === normalized) {
      return value;
    }
  }
  
  // Partial match (e.g., "45" in "Сталь 45")
  for (const [key, value] of Object.entries(STEEL_EQUIVALENTS)) {
    if (normalized.includes(key) || key.includes(normalized.replace(/\D/g, ''))) {
      return value;
    }
  }
  
  return null;
}

/**
 * Search steel equivalents by any standard
 */
export function searchSteelEquivalents(query) {
  const normalized = normalizeSteelGrade(query);
  const results = [];
  
  for (const [grade, equiv] of Object.entries(STEEL_EQUIVALENTS)) {
    if (
      normalized.includes(grade) ||
      grade.includes(normalized) ||
      equiv.astm.toLowerCase().includes(query.toLowerCase()) ||
      equiv.gbt.toLowerCase().includes(query.toLowerCase()) ||
      equiv.iso.toLowerCase().includes(query.toLowerCase()) ||
      equiv.gost.toLowerCase().includes(query.toLowerCase())
    ) {
      results.push({
        grade: grade,
        ...equiv
      });
    }
  }
  
  return results;
}

