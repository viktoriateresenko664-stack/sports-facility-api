
class QueryCache {
  constructor(ttl = 60000) { // 60 секунд по умолчанию
    this.cache = new Map();
    this.defaultTtl = ttl;
  }
  
  async getOrFetch(key, fetcher, ttl = this.defaultTtl) {
    const cached = this.cache.get(key);
    
    if (cached && Date.now() - cached.timestamp < ttl) {
      console.log(`[Cache] HIT: ${key}`);
      return cached.data;
    }
    
    console.log(`[Cache] MISS: ${key}`);
    const data = await fetcher();
    
    this.cache.set(key, {
      data,
      timestamp: Date.now(),
      ttl
    });
    
    return data;
  }
  
  invalidate(pattern) {
    let invalidatedCount = 0;
    
    for (const [key] of this.cache) {
      if (typeof pattern === 'string' && key.includes(pattern)) {
        this.cache.delete(key);
        invalidatedCount++;
      } else if (pattern instanceof RegExp && pattern.test(key)) {
        this.cache.delete(key);
        invalidatedCount++;
      }
    }
    
    console.log(`[Cache] Invalidated ${invalidatedCount} keys matching: ${pattern}`);
    return invalidatedCount;
  }
  
  // Полная очистка кэша
  clear() {
    const size = this.cache.size;
    this.cache.clear();
    console.log(`[Cache] Cleared ${size} entries`);
  }
}

export const queryCache = new QueryCache();