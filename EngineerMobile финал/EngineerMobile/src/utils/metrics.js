
import AsyncStorage from '@react-native-async-storage/async-storage';

const STORAGE_KEY = '@app_metrics';

class MetricsCollector {
  constructor() {
    this.requests = [];
    this.loadFromStorage();
  }

  async saveToStorage() {
    try {
      const toStore = this.requests.slice(-500);
      await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(toStore));
    } catch (error) {
      console.warn('Failed to save metrics:', error);
    }
  }

  async loadFromStorage() {
    try {
      const data = await AsyncStorage.getItem(STORAGE_KEY);
      if (data) {
        this.requests = JSON.parse(data);
      }
    } catch (error) {
      console.warn('Failed to load metrics:', error);
    }
  }

  startRequest(url, method) {
    const request = {
      url,
      method,
      startTime: Date.now(),
      timestamp: new Date().toISOString(),
    };
    this.requests.push(request);
    return request;
  }

  endRequest(request, status, duration) {
    request.status = status;
    request.duration = duration;
    this.saveToStorage();
    this.logToConsole(request);
  }

  endRequestError(request, error) {
    request.error = error;
    request.duration = Date.now() - request.startTime;
    this.saveToStorage();
    this.logToConsole(request);
  }

  logToConsole(request) {
    const status = request.error ? 'ERROR' : request.status;
    const duration = request.duration;
    const slow = duration > 1000 ? '[SLOW] ' : '';
    
    console.log(
      `[METRIC] ${slow}${request.method} ${request.url} | ${duration}ms | ${status}`
    );
  }

  printHeatmap() {
    const heatmap = {};
    
    for (const req of this.requests) {
      const key = `${req.method} ${req.url}`;
      if (!heatmap[key]) {
        heatmap[key] = {
          count: 0,
          totalDuration: 0,
          errors: 0,
        };
      }
      
      heatmap[key].count++;
      if (req.duration) heatmap[key].totalDuration += req.duration;
      if (req.error) heatmap[key].errors++;
    }
    
    console.log('\n Тепловая карта');
    console.log(`Vsego zaprosov: ${this.requests.length}`);
    console.log('');
    
    const sorted = Object.entries(heatmap).sort((a, b) => b[1].count - a[1].count);
    
    for (const [endpoint, data] of sorted.slice(0, 10)) {
      const avgDuration = Math.round(data.totalDuration / data.count);
      const errorRate = data.errors > 0 ? ` | oshibki: ${data.errors}` : '';
      console.log(`${endpoint}`);
      console.log(`  zaprosov: ${data.count} | srednee: ${avgDuration}ms${errorRate}`);
      console.log('');
    }
    
    console.log('-------------------------------------------\n');
  }

  async clear() {
    this.requests = [];
    await AsyncStorage.removeItem(STORAGE_KEY);
    console.log('[METRIC] Metrics cleared');
  }
}

export const metrics = new MetricsCollector();
