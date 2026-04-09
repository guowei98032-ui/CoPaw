/**
 * LCM HTTP Server - Thin wrapper for lossless-claw package
 * 
 * Run with: npx tsx index.js
 * tsx handles TypeScript imports automatically.
 * 
 * Configuration:
 *   - Loads from lcm-config.json (in same directory)
 *   - Falls back to environment variables if config file not found
 */

import express from 'express';
import { createLcmDependencies, createLcmDatabase } from './lcm-adapter.js';
import { readFileSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

const app = express();
app.use(express.json({ limit: '50mb' }));

// ============================================================
// Load Configuration
// ============================================================

/**
 * Load LCM configuration from file or environment variables.
 * @returns {object} LCM configuration object
 */
function loadLcmConfig() {
  const configPath = join(__dirname, 'lcm-config.json');
  
  // Try to load from config file first
  if (existsSync(configPath)) {
    try {
      const fileConfig = JSON.parse(readFileSync(configPath, 'utf-8'));
      console.log('[LCM] Configuration loaded from:', configPath);
      return fileConfig;
    } catch (e) {
      console.warn('[LCM] Failed to load config file:', e.message);
      console.warn('[LCM] Falling back to environment variables');
    }
  }
  
  // Fallback to environment variables
  console.log('[LCM] No config file found, using environment variables');
  return {
    enabled: true,
    server: {
      host: process.env.LCM_HOST || 'localhost',
      port: parseInt(process.env.LCM_PORT || '3721'),
    },
    database: {
      basePath: process.env.LCM_DATABASE_PATH || './data',
      defaultDbName: 'lcm.db',
    },
    llm: {
      provider: process.env.LCM_PROVIDER || 'openai',
      model: process.env.LCM_MODEL || 'gpt-4',
      apiKey: process.env.LCM_API_KEY || process.env.OPENAI_API_KEY,
      baseUrl: process.env.LCM_BASE_URL,
      timeout: parseInt(process.env.LCM_TIMEOUT || '30000'),
    },
    embedding: {
      backend: process.env.EMBEDDING_BACKEND || 'openai',
      apiKey: process.env.EMBEDDING_API_KEY || process.env.OPENAI_API_KEY,
      baseUrl: process.env.EMBEDDING_BASE_URL,
      modelName: process.env.EMBEDDING_MODEL_NAME || 'text-embedding-3-small',
      dimensions: parseInt(process.env.EMBEDDING_DIMENSIONS || '1536'),
      enableCache: process.env.EMBEDDING_ENABLE_CACHE !== 'false',
      maxCacheSize: parseInt(process.env.EMBEDDING_MAX_CACHE_SIZE || '3000'),
      maxInputLength: parseInt(process.env.EMBEDDING_MAX_INPUT_LENGTH || '8192'),
      maxBatchSize: parseInt(process.env.EMBEDDING_MAX_BATCH_SIZE || '10'),
    },
    compaction: {
      contextThreshold: parseFloat(process.env.LCM_CONTEXT_THRESHOLD || '0.75'),
      freshTailCount: parseInt(process.env.LCM_FRESH_TAIL_COUNT || '32'),
      maxContextTokens: parseInt(process.env.LCM_MAX_CONTEXT_TOKENS || '128000'),
      autoCompact: process.env.LCM_AUTO_COMPACT !== 'false',
    },
    logging: {
      level: process.env.LCM_LOG_LEVEL || 'info',
      debug: process.env.LCM_DEBUG === 'true',
    },
  };
}

const lcmConfig = loadLcmConfig();

// ============================================================
// Import and Initialize LCM Engine
// ============================================================

let LcmContextEngine = null;
let lcmAvailable = false;
let defaultDeps = null;

try {
  // Import engine from TypeScript source
  const engineModule = await import('@martian-engineering/lossless-claw/src/engine.ts');
  LcmContextEngine = engineModule.LcmContextEngine;
  
  lcmAvailable = !!LcmContextEngine;
  console.log('[LCM] lossless-claw package loaded successfully');
  console.log('[LCM] LcmContextEngine type:', typeof LcmContextEngine);

    // Create default dependencies from config
  const dbPath = join(lcmConfig.database.basePath, lcmConfig.database.defaultDbName);
  
  // Build legacyParams for summarizer with correct structure
  const legacyParams = {
    provider: lcmConfig.summary?.provider || lcmConfig.llm?.provider || 'openai',
    model: lcmConfig.summary?.model || lcmConfig.llm?.model || 'gpt-4',
    config: {
      plugins: {
        entries: {
          "lossless-claw": {
            config: {
              summaryProvider: lcmConfig.summary?.provider || lcmConfig.llm?.provider,
              summaryModel: lcmConfig.summary?.model || lcmConfig.llm?.model,
            }
          }
        }
      },
      agents: {
        defaults: {
          model: lcmConfig.llm?.model,
          compaction: {
            model: lcmConfig.summary?.model || lcmConfig.llm?.model,
          }
        }
      }
    }
  };
  
  defaultDeps = createLcmDependencies({
    llmConfig: {
      provider: lcmConfig.llm.provider,
      model: lcmConfig.llm.model,
      apiKey: lcmConfig.llm.apiKey,
      baseUrl: lcmConfig.llm.baseUrl,
      providerApi: lcmConfig.llm.baseUrl, // Explicitly pass providerApi for DashScope
    },
    summaryConfig: lcmConfig.summary ? {
      provider: lcmConfig.summary.provider,
      model: lcmConfig.summary.model,
      apiKey: lcmConfig.summary.apiKey,
      baseUrl: lcmConfig.summary.baseUrl,
      providerApi: lcmConfig.summary.baseUrl, // Explicitly pass providerApi for DashScope
    } : undefined,
    pluginConfig: {
      databasePath: dbPath,
      contextThreshold: lcmConfig.compaction.contextThreshold,
      freshTailCount: lcmConfig.compaction.freshTailCount,
    },
    legacyParams: legacyParams,
  });
  
  console.log('[LCM] Dependencies created, databasePath:', defaultDeps.config.databasePath);
  console.log('[LCM] LLM Provider:', lcmConfig.llm.provider);
  console.log('[LCM] LLM Model:', lcmConfig.llm.model);
} catch (e) {
  console.warn('[LCM] lossless-claw import failed:', e.message);
  console.warn('[LCM] Server will run in stub mode for development');
  console.error(e.stack);
}

// ============================================================
// Engine Instance Management
// ============================================================

const engines = new Map(); // sessionId -> engine instance
const databases = new Map(); // sessionId -> database connection

/**
 * Get or create engine for session
 */
async function getEngine(sessionId, config = {}) {
  if (!lcmAvailable || !LcmContextEngine) {
    throw new Error('lossless-claw engine not available');
  }

  if (engines.has(sessionId)) {
    return engines.get(sessionId);
  }

  // Resolve database path first (before creating deps)
  const dbPath = config.dbPath || defaultDeps?.config?.databasePath || `./data/lcm-${sessionId}.db`;
  
  // Merge config with default dependencies
  // Use defaultDeps.llmConfig and defaultDeps.summaryConfig as fallback for all LLM settings
  const defaultLlmConfig = defaultDeps?.llmConfig || {};
  const defaultSummaryConfig = defaultDeps?.summaryConfig || {};
  
  const deps = createLcmDependencies({
    llmConfig: {
      provider: config.provider || defaultLlmConfig.provider || 'openai',
      model: config.model || defaultLlmConfig.model || 'gpt-4',
      apiKey: config.apiKey || defaultLlmConfig.apiKey,
      baseUrl: config.baseUrl || defaultLlmConfig.baseUrl || defaultLlmConfig.providerApi,
      providerApi: config.baseUrl || defaultLlmConfig.baseUrl || defaultLlmConfig.providerApi,
    },
    summaryConfig: config.summaryProvider || config.summaryModel ? {
      provider: config.summaryProvider || defaultSummaryConfig.provider || defaultLlmConfig.provider || 'openai',
      model: config.summaryModel || defaultSummaryConfig.model || defaultLlmConfig.model || 'gpt-4',
      apiKey: config.apiKey || defaultSummaryConfig.apiKey || defaultLlmConfig.apiKey,
      baseUrl: config.baseUrl || defaultSummaryConfig.baseUrl || defaultLlmConfig.baseUrl || defaultLlmConfig.providerApi,
      providerApi: config.baseUrl || defaultSummaryConfig.baseUrl || defaultLlmConfig.baseUrl || defaultLlmConfig.providerApi,
    } : {
      provider: defaultSummaryConfig.provider || defaultLlmConfig.provider || 'openai',
      model: defaultSummaryConfig.model || defaultLlmConfig.model || 'gpt-4',
      apiKey: defaultSummaryConfig.apiKey || defaultLlmConfig.apiKey,
      baseUrl: defaultSummaryConfig.baseUrl || defaultLlmConfig.baseUrl || defaultLlmConfig.providerApi,
      providerApi: defaultSummaryConfig.baseUrl || defaultLlmConfig.baseUrl || defaultLlmConfig.providerApi,
    },
    pluginConfig: {
      databasePath: dbPath,
      contextThreshold: config.contextThreshold || defaultDeps?.config?.contextThreshold || 0.75,
      freshTailCount: config.freshTailCount || defaultDeps?.config?.freshTailCount || 32,
    },
    // 关键：传递 legacyParams 从 defaultDeps
    legacyParams: defaultDeps?.legacyParams || {},
  });

  try {
    // Create database connection
    console.log(`[LCM] Creating database at: ${dbPath}`);
    const database = createLcmDatabase(dbPath);
    databases.set(sessionId, database);
    
    // Create engine with dependencies AND database connection
    const engine = new LcmContextEngine(deps, database);
    
    // Note: bootstrap requires OpenClaw sessionFile (JSONL format).
    // For standalone use, we skip bootstrap and rely on lazy init.
    // The engine will initialize DB schema on first ingest/assemble.
    console.log(`[LCM] Engine created for session: ${sessionId} (lazy bootstrap)`);
    
    engines.set(sessionId, engine);
    
    return engine;
  } catch (e) {
    console.error(`[LCM] Failed to create engine:`, e.message);
    console.error(e.stack);
    throw e;
  }
}

/**
 * Close and remove engine for session
 */
async function closeEngine(sessionId) {
  if (engines.has(sessionId)) {
    const engine = engines.get(sessionId);
    try {
      if (engine.close) await engine.close();
    } catch (e) {
      console.warn(`[LCM] Close error for ${sessionId}:`, e.message);
    }
    engines.delete(sessionId);
    console.log(`[LCM] Engine closed for session: ${sessionId}`);
  }
}

// ============================================================
// HTTP API Routes
// ============================================================

// Health check
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    lcmAvailable,
    activeSessions: engines.size,
    timestamp: new Date().toISOString(),
    config: {
      databasePath: defaultDeps?.config?.databasePath,
      contextThreshold: defaultDeps?.config?.contextThreshold,
      freshTailCount: defaultDeps?.config?.freshTailCount,
      provider: lcmConfig?.llm?.provider,
      model: lcmConfig?.llm?.model,
      autoCompact: lcmConfig?.compaction?.autoCompact,
    }
  });
});

// Initialize engine for session
app.post('/init', async (req, res) => {
  try {
    const { sessionId, config = {} } = req.body;
    
    if (!sessionId) {
      return res.status(400).json({ error: 'sessionId required' });
    }

    const engine = await getEngine(sessionId, config);
    
    res.json({
      success: true,
      sessionId,
      lcmAvailable,
      message: 'Engine initialized',
    });
  } catch (error) {
    console.error('[LCM] Init error:', error);
    res.status(500).json({ error: error.message, stack: error.stack });
  }
});

// Ingest messages
app.post('/ingest', async (req, res) => {
  try {
    const { sessionId, messages } = req.body;
    
    if (!sessionId) {
      return res.status(400).json({ error: 'sessionId required' });
    }

    const engine = await getEngine(sessionId);
    const msgArray = Array.isArray(messages) ? messages : [messages];
    const results = [];

    for (const msg of msgArray) {
      try {
        // Convert content to proper format
        let content = msg.content;
        if (typeof content === 'string') {
          content = [{ type: 'text', text: content }];
        } else if (!Array.isArray(content)) {
          content = [{ type: 'text', text: JSON.stringify(content) }];
        }
        
        // Convert to OpenClaw/AgentMessage format
        const agentMsg = {
          id: msg.id || generateId(),
          role: msg.role || 'user',
          content: content,
          // Optional fields
          ...(msg.name && { name: msg.name }),
          ...(msg.tool_calls && { toolCalls: msg.tool_calls }),
          ...(msg.tool_call_id && { toolCallId: msg.tool_call_id }),
        };
        
        const result = await engine.ingest({
          sessionId: sessionId,
          message: agentMsg,
        });
        results.push(result);
      } catch (e) {
        console.warn('[LCM] Ingest error:', e.message);
        results.push({ error: e.message });
      }
    }

    res.json({
      success: true,
      ingested: results.length,
      results,
    });
  } catch (error) {
    console.error('[LCM] Ingest error:', error);
    res.status(500).json({ error: error.message });
  }
});

// After turn processing (check compaction trigger)
// For standalone use, this is a simplified version that checks if compaction is needed
app.post('/after-turn', async (req, res) => {
  try {
    const { sessionId, messages, prePromptMessageCount = 0 } = req.body;
    
    if (!sessionId) {
      return res.status(400).json({ error: 'sessionId required' });
    }

    const engine = await getEngine(sessionId);
    
    // If messages provided, call afterTurn properly
    if (messages && Array.isArray(messages)) {
      try {
        await engine.afterTurn({
          sessionId,
          sessionKey: sessionId,
          sessionFile: `data/${sessionId}.jsonl`, // stub file path
          messages,
          prePromptMessageCount,
        });
        res.json({ success: true, message: 'After-turn processed' });
      } catch (e) {
        console.warn('[LCM] afterTurn error:', e.message);
        res.json({ success: false, error: e.message });
      }
    } else {
      // Without messages, just check compaction trigger
      try {
        const trigger = await engine.evaluateLeafTrigger?.(sessionId);
        res.json({ 
          success: true, 
          shouldCompact: trigger?.shouldCompact || false,
          reason: trigger?.reason 
        });
      } catch (e) {
        // evaluateLeafTrigger might not exist, return simple success
        res.json({ success: true, message: 'Engine ready (no compaction check available)' });
      }
    }
  } catch (error) {
    console.error('[LCM] After-turn error:', error);
    res.status(500).json({ error: error.message });
  }
});

// Get assembled context (GET - for simple retrieval)
app.get('/context/:sessionId', async (req, res) => {
  try {
    const { sessionId } = req.params;
    const engine = await getEngine(sessionId);
    
    // GET version returns stored messages without live message augmentation
    try {
      const retrieval = engine.getRetrieval();
      // Get recent messages from the conversation
      const conversation = await engine.conversationStore?.getConversationForSession({
        sessionId,
        sessionKey: sessionId,
      });
      
      if (!conversation) {
        return res.json({
          success: true,
          messages: [],
          estimatedTokens: 0,
        });
      }
      
      // Get context items (summaries + recent messages)
      const contextItems = await engine.summaryStore?.getContextItems(conversation.conversationId) || [];
      
      res.json({
        success: true,
        conversationId: conversation.conversationId,
        contextItemsCount: contextItems.length,
        contextItems,
      });
    } catch (e) {
      console.warn('[LCM] GET context error:', e.message);
      res.json({ success: false, error: e.message, messages: [] });
    }
  } catch (error) {
    console.error('[LCM] Get context error:', error);
    res.status(500).json({ error: error.message });
  }
});

// Assemble context (POST - with live messages for model input)
app.post('/context/:sessionId', async (req, res) => {
  try {
    const { sessionId } = req.params;
    const { messages = [], tokenBudget } = req.body;
    
    const engine = await getEngine(sessionId);
    
    try {
      // Assemble context: combines stored summaries with live messages
      const result = await engine.assemble({
        sessionId,
        sessionKey: sessionId,
        messages,
        tokenBudget,
      });
      
      res.json({
        success: true,
        messages: result.messages,
        estimatedTokens: result.estimatedTokens,
        contextItems: result.contextItems,
      });
    } catch (e) {
      console.warn('[LCM] assemble error:', e.message);
      res.json({ 
        success: false, 
        error: e.message,
        // Return original messages on error
        messages,
      });
    }
  } catch (error) {
    console.error('[LCM] Get context error:', error);
    res.status(500).json({ error: error.message });
  }
});

// Run compaction manually
app.post('/compact', async (req, res) => {
  try {
    const { sessionId, mode = 'incremental', tokenBudget = 128000 } = req.body;
    
    if (!sessionId) {
      return res.status(400).json({ error: 'sessionId required' });
    }

    const engine = await getEngine(sessionId);
    
    // Get legacyParams from the engine's deps (set during initialization)
    const legacyParams = engine.deps?.legacyParams || {};
    
    let result = {};
    try {
      // Run compaction
      // Note: compact requires sessionFile, tokenBudget, etc.
      // For standalone use, we provide minimal required params
      result = await engine.compact({
        sessionId,
        sessionKey: sessionId,
        sessionFile: `data/${sessionId}.jsonl`, // stub file path
        tokenBudget: tokenBudget,
        force: mode === 'force',
        legacyParams: legacyParams, // Pass legacyParams for summarizer
      });
    } catch (e) {
      console.warn('[LCM] Compact error:', e.message);
      result = { error: e.message };
    }
    
    res.json({
      success: true,
      mode,
      result,
    });
  } catch (error) {
    console.error('[LCM] Compact error:', error);
    res.status(500).json({ error: error.message });
  }
});

// Search tool: lcm_grep
app.post('/grep', async (req, res) => {
  try {
    const { sessionId, pattern, query, mode = 'regex', scope = 'both', limit = 50 } = req.body;
    
    // Accept both 'pattern' and 'query' for flexibility
    const searchPattern = pattern || query;
    
    if (!sessionId || !searchPattern) {
      return res.status(400).json({ error: 'sessionId and pattern (or query) required' });
    }

    const engine = await getEngine(sessionId);
    
    try {
      const retrieval = engine.getRetrieval();
      const result = await retrieval.grep({
        query: searchPattern,
        mode,
        scope,
        limit,
      });
      
      res.json({
        success: true,
        pattern: searchPattern,
        mode,
        scope,
        totalMatches: result.totalMatches,
        messages: result.messages,
        summaries: result.summaries,
      });
    } catch (e) {
      console.warn('[LCM] Grep error:', e.message);
      res.json({ success: false, error: e.message });
    }
  } catch (error) {
    console.error('[LCM] Grep error:', error);
    res.status(500).json({ error: error.message });
  }
});

// Describe tool: get summary/file details
app.post('/describe', async (req, res) => {
  try {
    const { sessionId, summaryId, fileId } = req.body;
    
    if (!sessionId) {
      return res.status(400).json({ error: 'sessionId required' });
    }

    // TODO: Implement describe functionality
    res.json({
      success: false,
      error: 'Describe not yet implemented',
      hint: 'Use /grep to search for content',
    });
  } catch (error) {
    console.error('[LCM] Describe error:', error);
    res.status(500).json({ error: error.message });
  }
});

// Expand tool: expand a summary
app.post('/expand', async (req, res) => {
  try {
    const { sessionId, summaryId, query } = req.body;
    
    if (!sessionId || !summaryId) {
      return res.status(400).json({ error: 'sessionId and summaryId required' });
    }

    // TODO: Implement expand functionality
    res.json({
      success: false,
      error: 'Expand not yet implemented',
      hint: 'Use /grep to search for content',
    });
  } catch (error) {
    console.error('[LCM] Expand error:', error);
    res.status(500).json({ error: error.message });
  }
});

// Close session
app.post('/close', async (req, res) => {
  try {
    const { sessionId } = req.body;
    
    if (sessionId) {
      await closeEngine(sessionId);
    } else {
      for (const [sid] of engines) {
        await closeEngine(sid);
      }
    }
    
    res.json({
      success: true,
      message: sessionId ? `Session ${sessionId} closed` : 'All sessions closed',
    });
  } catch (error) {
    console.error('[LCM] Close error:', error);
    res.status(500).json({ error: error.message });
  }
});

// Get session stats
app.get('/stats/:sessionId', async (req, res) => {
  try {
    const { sessionId } = req.params;
    
    if (!engines.has(sessionId)) {
      return res.json({ sessionId, active: false });
    }

    const engine = engines.get(sessionId);
    
    let stats = { sessionId, active: true };
    try {
      stats = await engine.getInfo?.({ sessionKey: sessionId }) || stats;
    } catch (e) {
      console.warn('[LCM] Stats error:', e.message);
    }
    
    res.json(stats);
  } catch (error) {
    console.error('[LCM] Stats error:', error);
    res.status(500).json({ error: error.message });
  }
});

// ============================================================
// Helpers
// ============================================================

function generateId() {
  return 'msg_' + Math.random().toString(36).substring(2, 11);
}

// ============================================================
// Start server
// ============================================================

const PORT = lcmConfig?.server?.port || process.env.LCM_PORT || 3721;
app.listen(PORT, () => {
  console.log(`[LCM] Server running on port ${PORT}`);
  console.log(`[LCM] Health check: http://localhost:${PORT}/health`);
  console.log(`[LCM] Config file: ${existsSync(join(__dirname, 'lcm-config.json')) ? 'loaded' : 'not found (using env vars)'}`);
  
  if (!lcmAvailable) {
    console.log('');
    console.log('[LCM] ⚠️  lossless-claw engine not available');
    console.log('');
  } else {
    console.log('[LCM] ✅ Engine ready, waiting for sessions');
  }
});