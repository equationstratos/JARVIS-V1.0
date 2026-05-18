// Model definitions and categories

export interface Model {
  id: string;
  name: string;
  provider: 'api' | 'ollama';
  description: string;
  contextWindow?: number;
  maxTokens?: number;
  costPer1kTokens?: {
    input: number;
    output: number;
  };
}

export const API_MODELS: Model[] = [
  {
    id: 'gemini/gemini-2.0-flash',
    name: 'Gemini 2.0 Flash',
    provider: 'api',
    description: 'Latest Gemini model, fastest for most tasks',
    contextWindow: 1000000,
    maxTokens: 8000,
  },
  {
    id: 'claude-3-5-sonnet',
    name: 'Claude 3.5 Sonnet',
    provider: 'api',
    description: 'Anthropic latest model, excellent reasoning',
    contextWindow: 200000,
    maxTokens: 4096,
  },
  {
    id: 'gpt-4-turbo',
    name: 'GPT-4 Turbo',
    provider: 'api',
    description: 'OpenAI GPT-4 with vision capabilities',
    contextWindow: 128000,
    maxTokens: 4096,
  },
  {
    id: 'mistral/mistral-7b',
    name: 'Mistral 7B',
    provider: 'api',
    description: 'Small and efficient model',
    contextWindow: 32000,
    maxTokens: 8000,
  },
  {
    id: 'groq/mixtral-8x7b',
    name: 'Mixtral 8x7B',
    provider: 'api',
    description: 'Mixture of Experts, very fast',
    contextWindow: 32000,
    maxTokens: 4096,
  },
];

export const OLLAMA_MODELS: Model[] = [
  {
    id: 'ollama/llama3',
    name: 'Llama 3',
    provider: 'ollama',
    description: 'Meta Llama 3, latest version (recommended)',
    contextWindow: 8192,
    maxTokens: 4096,
  },
  {
    id: 'ollama/llama2',
    name: 'Llama 2',
    provider: 'ollama',
    description: 'Meta Llama 2, 7B/13B/70B versions',
    contextWindow: 4096,
    maxTokens: 2048,
  },
  {
    id: 'ollama/mistral',
    name: 'Mistral',
    provider: 'ollama',
    description: 'Mistral 7B, locally optimized',
    contextWindow: 32000,
    maxTokens: 8000,
  },
  {
    id: 'ollama/neural-chat',
    name: 'Neural Chat',
    provider: 'ollama',
    description: 'Intel Neural Chat, conversation focused',
    contextWindow: 4096,
    maxTokens: 2048,
  },
  {
    id: 'ollama/dolphin-mixtral',
    name: 'Dolphin Mixtral',
    provider: 'ollama',
    description: 'High-quality Mistral variant',
    contextWindow: 32000,
    maxTokens: 4096,
  },
  {
    id: 'ollama/codellama',
    name: 'Code Llama',
    provider: 'ollama',
    description: 'Specialized for code generation',
    contextWindow: 100000,
    maxTokens: 4096,
  },
];

export function getModelInfo(modelId: string): Model | undefined {
  return [...API_MODELS, ...OLLAMA_MODELS].find((m) => m.id === modelId);
}

export function isOllamaModel(modelId: string): boolean {
  return OLLAMA_MODELS.some((m) => m.id === modelId);
}

export function isApiModel(modelId: string): boolean {
  return API_MODELS.some((m) => m.id === modelId);
}
