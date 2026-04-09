/**
 * LCM Dependencies Adapter
 * 
 * Provides stub/adapter implementations for LcmDependencies,
 * allowing lossless-claw to run without OpenClaw core.
 */

import { resolveLcmConfig } from '@martian-engineering/lossless-claw/src/db/config.ts';
import { createLcmDatabaseConnection } from '@martian-engineering/lossless-claw/src/db/connection.ts';
import { homedir } from 'node:os';
import { join } from 'node:path';

// ============================================================
// LLM Completion Adapter
// ============================================================

/**
 * Create a completion function that calls external LLM API.
 * Supports OpenAI-compatible APIs including Alibaba DashScope.
 */
export function createCompleteFn(llmConfig = {}) {
  const {
    provider = 'openai',
    model = 'gpt-4',
    apiKey = process.env.OPENAI_API_KEY || process.env.LLM_API_KEY,
    baseUrl = process.env.LLM_BASE_URL || 'https://api.openai.com/v1',
    providerApi, // Additional provider API endpoint override
  } = llmConfig;

  // Use providerApi if available (for DashScope and other providers)
  const effectiveBaseUrl = providerApi || baseUrl;

  // DEBUG: Log the configuration
  console.error('[DEBUG createCompleteFn] Config:', JSON.stringify({
    provider,
    model,
    apiKey: apiKey ? '***' + apiKey.slice(-8) : 'none',
    baseUrl: effectiveBaseUrl,
    providerApi,
  }, null, 2));

  return async ({ messages, system, maxTokens, temperature = 0.2 }) => {
    if (!apiKey) {
      return {
        content: [{ type: 'text', text: '[Error: No API key configured]' }],
        error: { kind: 'auth', message: 'No API key configured' }
      };
    }

    try {
      const formattedMessages = [];
      
      if (system) {
        formattedMessages.push({ role: 'system', content: system });
      }
      
      for (const msg of messages) {
        formattedMessages.push({
          role: msg.role,
          content: typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content)
        });
      }

      const requestUrl = `${effectiveBaseUrl}/chat/completions`;
      
      // DEBUG: Log the request
      console.error('[DEBUG createCompleteFn] Request:', JSON.stringify({
        url: requestUrl,
        model,
        messagesCount: formattedMessages.length,
        maxTokens,
        temperature,
      }, null, 2));

      const response = await fetch(requestUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${apiKey}`,
        },
        body: JSON.stringify({
          model,
          messages: formattedMessages,
          max_tokens: maxTokens,
          temperature,
        }),
      });

      // DEBUG: Log response status
      console.error('[DEBUG createCompleteFn] Response status:', response.status);

      if (!response.ok) {
        const errorText = await response.text();
        console.error('[DEBUG createCompleteFn] Error response:', errorText);
        return {
          content: [{ type: 'text', text: `[API Error: ${response.status}]` }],
          error: { kind: 'api', message: errorText, statusCode: response.status }
        };
      }

      const data = await response.json();
      const text = data.choices?.[0]?.message?.content || '';
      
      return {
        content: [{ type: 'text', text }],
      };
    } catch (e) {
      console.error('[DEBUG createCompleteFn] Exception:', e.message);
      return {
        content: [{ type: 'text', text: `[Error: ${e.message}]` }],
        error: { kind: 'network', message: e.message }
      };
    }
  };
}

// ============================================================
// Gateway RPC Adapter (Stub for subagent operations)
// ============================================================

/**
 * Create a gateway call function.
 * For standalone use, we stub subagent operations.
 */
export function createCallGatewayFn() {
  return async ({ method, params, timeoutMs }) => {
    // Stub for subagent-related gateway calls
    console.log(`[LCM Adapter] Gateway call: ${method}`, params);
    
    if (method === 'spawnSubagent') {
      return { 
        success: false, 
        error: 'Subagent spawning not available in standalone mode' 
      };
    }
    
    if (method === 'getSessionInfo') {
      return { 
        sessionId: params?.sessionKey?.split(':')?.[1] || params?.sessionId 
      };
    }
    
    return { success: true, result: {} };
  };
}

// ============================================================
// Model Resolution Adapter
// ============================================================

/**
 * Create model resolution function.
 */
export function createResolveModelFn(defaultProvider = 'openai', defaultModel = 'gpt-4') {
  return (modelRef, providerHint) => {
    if (modelRef?.includes(':')) {
      const [provider, model] = modelRef.split(':');
      return { provider, model };
    }
    return {
      provider: providerHint || defaultProvider,
      model: modelRef || defaultModel,
    };
  };
}

// ============================================================
// API Key Adapter
// ============================================================

/**
 * Create API key functions.
 */
export function createApiKeyFns(llmConfig = {}) {
  const apiKey = llmConfig.apiKey || process.env.OPENAI_API_KEY || process.env.LLM_API_KEY;

  const getApiKey = async (provider, model, options = {}) => {
    // Check for provider-specific env vars
    const providerKey = process.env[`${provider.toUpperCase()}_API_KEY`];
    if (providerKey) return providerKey;
    
    // Fall back to general API key
    return apiKey;
  };

  const requireApiKey = async (provider, model, options = {}) => {
    const key = await getApiKey(provider, model, options);
    if (!key) {
      throw new Error(`No API key available for ${provider}/${model}`);
    }
    return key;
  };

  return { getApiKey, requireApiKey };
}

// ============================================================
// Session Key Adapter
// ============================================================

/**
 * Create session key parsing functions.
 */
export function createSessionKeyFns() {
  const parseAgentSessionKey = (sessionKey) => {
    if (!sessionKey) return null;
    const parts = sessionKey.split(':');
    if (parts.length >= 2) {
      return { agentId: parts[0], suffix: parts.slice(1).join(':') };
    }
    return { agentId: sessionKey, suffix: '' };
  };

  const isSubagentSessionKey = (sessionKey) => {
    if (!sessionKey) return false;
    return sessionKey.includes(':subagent:') || sessionKey.startsWith('subagent:');
  };

  const normalizeAgentId = (id) => {
    if (!id) return 'default';
    return id.replace(/[^a-zA-Z0-9_-]/g, '_');
  };

  const resolveSessionIdFromSessionKey = async (sessionKey) => {
    if (!sessionKey) return undefined;
    const parsed = parseAgentSessionKey(sessionKey);
    return parsed?.suffix || sessionKey;
  };

  return {
    parseAgentSessionKey,
    isSubagentSessionKey,
    normalizeAgentId,
    resolveSessionIdFromSessionKey,
  };
}

// ============================================================
// Agent Operations Adapter
// ============================================================

/**
 * Create agent-related helper functions.
 */
export function createAgentOpsFns() {
  const buildSubagentSystemPrompt = ({ task, context, constraints }) => {
    return `You are a sub-agent tasked with: ${task}

Context:
${context || 'No additional context provided'}

Constraints:
${constraints || 'Follow standard protocols'}

Complete the task and provide a concise response.`;
  };

  const readLatestAssistantReply = (messages) => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i]?.role === 'assistant') {
        const content = messages[i]?.content;
        if (typeof content === 'string') return content;
        if (Array.isArray(content)) {
          const textBlock = content.find(b => b?.type === 'text');
          return textBlock?.text;
        }
      }
    }
    return undefined;
  };

  const resolveAgentDir = () => {
    return process.env.AGENT_DIR || join(homedir(), '.copaw', 'agents');
  };

  return {
    buildSubagentSystemPrompt,
    readLatestAssistantReply,
    resolveAgentDir,
  };
}

// ============================================================
// Logger
// ============================================================

/**
 * Create a logger compatible with OpenClaw's log interface.
 */
export function createLogger(prefix = '[LCM]') {
  return {
    info: (...args) => console.log(prefix, ...args),
    warn: (...args) => console.warn(prefix, '⚠️', ...args),
    error: (...args) => console.error(prefix, '❌', ...args),
    debug: (...args) => {
      if (process.env.LCM_DEBUG === 'true') {
        console.log(prefix, '[debug]', ...args);
      }
    },
  };
}

// ============================================================
// Database Connection Factory
// ============================================================

/**
 * Create a SQLite database connection for LCM.
 * 
 * @param {string} dbPath - Path to the database file
 * @returns {DatabaseSync} Database connection
 */
export function createLcmDatabase(dbPath) {
  return createLcmDatabaseConnection(dbPath);
}

// ============================================================
// Full Dependencies Factory
// ============================================================

/**
 * Create all dependencies needed by LcmContextEngine.
 * 
 * @param {object} options - Configuration options
 * @param {object} options.llmConfig - LLM configuration (provider, model, apiKey, baseUrl)
 * @param {object} options.pluginConfig - LCM plugin config overrides
 * @param {object} options.summaryConfig - Summary-specific LLM configuration (optional)
 * @param {object} options.legacyParams - Legacy params for summarizer (provider, model, config)
 * @returns {LcmDependencies} Complete dependencies object
 */
export function createLcmDependencies(options = {}) {
  const { llmConfig = {}, pluginConfig = {}, summaryConfig = {}, legacyParams = {} } = options;
  
  // Resolve LCM config from env vars + plugin config
  const config = resolveLcmConfig(process.env, pluginConfig);
  
  // Use summary-specific config if available, otherwise fall back to llmConfig
  const effectiveSummaryConfig = {
    provider: summaryConfig.provider || legacyParams.provider || llmConfig.provider || 'openai',
    model: summaryConfig.model || legacyParams.model || llmConfig.model || 'gpt-4',
    apiKey: summaryConfig.apiKey || llmConfig.apiKey,
    baseUrl: summaryConfig.baseUrl || llmConfig.baseUrl,
    providerApi: summaryConfig.providerApi || llmConfig.providerApi,
  };
  
  // DEBUG: Log effectiveSummaryConfig
  console.error('[DEBUG createLcmDependencies] effectiveSummaryConfig:', JSON.stringify({
    provider: effectiveSummaryConfig.provider,
    model: effectiveSummaryConfig.model,
    baseUrl: effectiveSummaryConfig.baseUrl,
    providerApi: effectiveSummaryConfig.providerApi,
  }, null, 2));
  
  // Create all adapter functions
  const complete = createCompleteFn(effectiveSummaryConfig);
  const callGateway = createCallGatewayFn();
  const resolveModel = createResolveModelFn(
    effectiveSummaryConfig.provider,
    effectiveSummaryConfig.model
  );
  const { getApiKey, requireApiKey } = createApiKeyFns(effectiveSummaryConfig);
  const sessionKeyFns = createSessionKeyFns();
  const agentOpsFns = createAgentOpsFns();
  const log = createLogger();

  return {
    config,
    complete,
    callGateway,
    resolveModel,
    getApiKey,
    requireApiKey,
    parseAgentSessionKey: sessionKeyFns.parseAgentSessionKey,
    isSubagentSessionKey: sessionKeyFns.isSubagentSessionKey,
    normalizeAgentId: sessionKeyFns.normalizeAgentId,
    buildSubagentSystemPrompt: agentOpsFns.buildSubagentSystemPrompt,
    readLatestAssistantReply: agentOpsFns.readLatestAssistantReply,
    resolveAgentDir: agentOpsFns.resolveAgentDir,
    resolveSessionIdFromSessionKey: sessionKeyFns.resolveSessionIdFromSessionKey,
    agentLaneSubagent: 'subagent',
    log,
    // Store legacyParams for engine to use
    legacyParams,
    // Store llmConfig for getEngine to access providerApi
    llmConfig,
    // Store summaryConfig for getEngine to access
    summaryConfig,
  };
}

export default createLcmDependencies;