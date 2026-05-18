import axios, { AxiosInstance } from 'axios';

export interface ChatRequest {
  query: string;
  model?: string;
  liveMode?: boolean;
}

export interface ChatResponse {
  response: string;
  latency: string;
  agent?: string;
}

export class JarvisClient {
  private client: AxiosInstance;
  private debug: boolean = false;

  constructor(baseURL: string, debug: boolean = false) {
    this.debug = debug;
    this.client = axios.create({
      baseURL,
      timeout: 90000,
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    // Add request interceptor for logging
    this.client.interceptors.request.use((config) => {
      if (this.debug) {
        console.log(`📤 [${config.method?.toUpperCase()}] ${config.url}`, {
          baseURL: config.baseURL,
          timeout: config.timeout,
        });
      }
      return config;
    });

    // Add response interceptor for logging
    this.client.interceptors.response.use(
      (response) => {
        if (this.debug) {
          console.log(`📥 [${response.status}] ${response.config.url}`, {
            data: response.data,
          });
        }
        return response;
      },
      (error) => {
        if (this.debug) {
          console.error(`❌ [${error.code}] ${error.message}`, {
            url: error.config?.url,
            method: error.config?.method,
            error: error.response?.data || error.message,
          });
        }
        return Promise.reject(error);
      }
    );
  }

  async chat(request: ChatRequest): Promise<ChatResponse> {
    try {
      const formData = new FormData();
      formData.append('query', request.query);
      if (request.model) {
        formData.append('model', request.model);
      }

      if (this.debug) {
        console.log('💬 Sending chat request:', {
          query: request.query,
          model: request.model,
        });
      }

      const response = await this.client.post('/chat', formData);

      if (this.debug) {
        console.log('✅ Chat response received:', response.data);
      }

      return response.data;
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail ||
                       error.message ||
                       'Unknown error';
      if (this.debug) {
        console.error('❌ Chat error:', errorMsg);
      }
      throw new Error(`Chat error: ${errorMsg}`);
    }
  }

  async *chatStream(request: ChatRequest) {
    const formData = new FormData();
    formData.append('query', request.query);
    if (request.model) {
      formData.append('model', request.model);
    }

    if (this.debug) {
      console.log('🔴 Starting stream for query:', request.query);
    }

    try {
      const url = `${this.client.defaults.baseURL}/chat/stream`;
      const response = await fetch(url, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(`Stream error: ${response.status} - ${errorData.detail || response.statusText}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');

        // Process all complete lines
        for (let i = 0; i < lines.length - 1; i++) {
          const line = lines[i].trim();
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim();
            if (data && data !== '[DONE]') {
              try {
                const parsed = JSON.parse(data);
                if (parsed.type === 'token') {
                  yield parsed.data;
                } else if (parsed.type === 'done') {
                  yield '[DONE]';
                  return;
                }
              } catch (e) {
                if (this.debug) console.error('Parse error:', e, 'Line:', line);
              }
            }
          }
        }

        // Keep incomplete line in buffer
        buffer = lines[lines.length - 1];
      }

      yield '[DONE]';
    } catch (error: any) {
      const errorMsg = error.message || 'Unknown stream error';
      if (this.debug) {
        console.error('❌ Stream error:', errorMsg);
      }
      throw new Error(`Stream error: ${errorMsg}`);
    }
  }

  async getModels(): Promise<string[]> {
    try {
      const response = await this.client.get('/api/models');
      return response.data.models || [];
    } catch {
      return ['gemini/gemini-2.0-flash', 'claude-3-5-sonnet', 'llama2', 'mistral'];
    }
  }

  async getHealth() {
    const response = await this.client.get('/health');
    return response.data;
  }

  async clearChat() {
    const response = await this.client.post('/clear');
    return response.data;
  }

  setBaseURL(url: string) {
    this.client.defaults.baseURL = url;
  }
}

let clientInstance: JarvisClient | null = null;

export function getClient(baseURL?: string, debug: boolean = false): JarvisClient {
  if (!clientInstance || debug) {
    clientInstance = new JarvisClient(baseURL || 'http://localhost:8501', debug);
  }
  if (baseURL) {
    clientInstance.setBaseURL(baseURL);
  }
  return clientInstance;
}

export function setDebugMode(enabled: boolean) {
  if (clientInstance) {
    clientInstance['debug'] = enabled;
  }
}
