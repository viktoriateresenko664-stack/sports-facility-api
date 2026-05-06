
export const sanitizeText = (text) => {
  if (!text || typeof text !== 'string') return '';
  if (typeof text === 'number') return String(text);
  
  return text
    // HTML спецсимволы
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;')
    // JavaScript протоколы
    .replace(/javascript:/gi, '')
    .replace(/vbscript:/gi, '')
    .replace(/data:/gi, '')
    // Обработчики событий
    .replace(/on\w+=/gi, '')
    .replace(/onerror=/gi, '')
    .replace(/onload=/gi, '')
    // Спецсимволы
    .replace(/\\/g, '&#92;')
    .replace(/`/g, '&#96;');
};

export const sanitizeAttribute = (value) => {
  if (!value) return '';
  return String(value).replace(/[&<>"'/]/g, (match) => {
    const escapeMap = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#x27;',
      '/': '&#x2F;'
    };
    return escapeMap[match];
  });
};

// Проверка на потенциально опасный контент (логирование)

export const hasXSSRisk = (text) => {
  if (!text || typeof text !== 'string') return false;
  const dangerousPatterns = [
    /<script/i,
    /javascript:/i,
    /on\w+=/i,
    /eval\(/i,
    /expression\(/i
  ];
  return dangerousPatterns.some(pattern => pattern.test(text));
};