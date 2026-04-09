# ✅ LCM "no summary model candidates resolved" 问题最终解决方案

## 🎉 问题状态：**已完全解决**

**测试时间**: 2026-04-03  
**测试者**: 大呙（大 guowei）  
**最终测试**: ✅ 所有测试通过，无错误日志

---

## 📋 问题现象

运行 LCM 服务器时，在**服务器控制台**出现以下错误：

```
[lcm] createLcmSummarize: no summary model candidates resolved
[lcm] resolveSummarize: createLcmSummarizeFromLegacyParams returned undefined
[lcm] resolveSummarize: FALLING BACK TO EMERGENCY TRUNCATION
```

---

## 🔍 根本原因

### 问题 1: 配置未正确传递
`lossless-claw` 的 `resolveSummaryCandidates()` 函数从以下 5 个来源查找 model：
1. 环境变量 `LCM_SUMMARY_MODEL`
2. 插件配置 `plugins.entries["lossless-claw"].config.summaryModel`
3. OpenClaw `agents.defaults.compaction.model`
4. OpenClaw `agents.defaults.model`
5. Legacy params `provider` 和 `model`

**问题**: 虽然 `lcm-config.json` 有配置，但**没有正确构造并传递给** `lossless-claw` 的 summarizer。

### 问题 2: compact 路由未传递 legacyParams
`engine.compact()` 方法需要从 `params.legacyParams` 获取配置，但 `/compact` 路由**没有传递**这个参数。

---

## ✅ 最终解决方案

### 修改 1: index.js - 构造完整的 legacyParams

**文件**: `C:\workspace\CoPaw\lcm-server\index.js`

```javascript
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
  llmConfig: { ... },
  summaryConfig: { ... },
  pluginConfig: { ... },
  legacyParams: legacyParams, // ← 关键：传递 legacyParams
});
```

### 修改 2: lcm-adapter.js - 存储并传递 legacyParams

**文件**: `C:\workspace\CoPaw\lcm-server\lcm-adapter.js`

```javascript
export function createLcmDependencies(options = {}) {
  const { llmConfig = {}, pluginConfig = {}, summaryConfig = {}, legacyParams = {} } = options;
  
  // ... 其他代码 ...
  
  return {
    config,
    complete,
    callGateway,
    resolveModel,
    getApiKey,
    requireApiKey,
    // ... 其他依赖 ...
    // 关键：存储 legacyParams 供 engine 使用
    legacyParams,
  };
}
```

### 修改 3: index.js - compact 路由传递 legacyParams

**文件**: `C:\workspace\CoPaw\lcm-server\index.js`

```javascript
app.post('/compact', async (req, res) => {
  const engine = await getEngine(sessionId);
  
  // 关键：从 engine.deps 获取 legacyParams 并传递给 compact
  const legacyParams = engine.deps?.legacyParams || {};
  
  result = await engine.compact({
    sessionId,
    sessionKey: sessionId,
    sessionFile: `data/${sessionId}.jsonl`,
    tokenBudget: tokenBudget,
    force: mode === 'force',
    legacyParams: legacyParams, // ← 关键：传递 legacyParams
  });
});
```

### 修改 4: lcm-config.json - 添加 summary 配置

**文件**: `C:\workspace\CoPaw\lcm-server\lcm-config.json`

```json
{
  "summary": {
    "provider": "openai",
    "model": "qwen3.5-plus",
    "apiKey": "sk-sp-4fe2f039355645e18038499216be4fa5",
    "baseUrl": "https://coding.dashscope.aliyuncs.com/v1"
  }
}
```

---

## 🧪 验证测试

### 测试 1: 配置验证
```bash
node test_summary_config.js
```
**结果**: ✅ 通过
```
✅ Configuration is present
   Using: lcm-config.json (model: qwen3.5-plus)

✅ Code modifications are in place
```

### 测试 2: 服务器启动
```bash
npm start
```
**结果**: ✅ 无错误日志
```
[LCM] Configuration loaded from: ...
[LCM] lossless-claw package loaded successfully
[LCM] LLM Provider: openai
[LCM] LLM Model: qwen3.5-plus
[LCM] ✅ Engine ready, waiting for sessions
```

**不再出现** ❌:
```
[lcm] createLcmSummarize: no summary model candidates resolved
[lcm] resolveSummarize: FALLING BACK TO EMERGENCY TRUNCATION
```

### 测试 3: 强制压缩测试
```bash
python test_force_compact.py
```
**结果**: ✅ 通过
```
✅✅✅ COMPACTION SUCCESSFUL! ✅✅✅
   - Compacted: True
   - Reason: compacted
   - OK: True

🎉 Summary model is working correctly!
🎉 No 'no summary model candidates' error!
```

### 测试 4: 调试参数测试
```bash
python test_debug_params.py
```
**结果**: ✅ 通过
```
Compact result: {
    "ok": true,
    "compacted": false,
    "reason": "already under target"
}
```

---

## 📁 修改的文件清单

| 文件 | 修改内容 | 状态 |
|------|---------|------|
| `lcm-server/lcm-config.json` | 添加 `summary` 配置块 | ✅ |
| `lcm-server/index.js` | 构造并传递 `legacyParams` | ✅ |
| `lcm-server/lcm-adapter.js` | 存储和传递 `legacyParams` | ✅ |
| `lcm-server/index.js` | `/compact` 路由传递 `legacyParams` | ✅ |

**新增测试工具**:
- `test_summary_config.js` ✅
- `test_force_compact.py` ✅
- `test_debug_params.py` ✅
- `test_server_errors.bat` ✅

---

## 🎯 关键技术点

### 1. lossless-claw 的配置解析流程

```
resolveSummaryCandidates(params)
  ├─ 读取 params.legacyParams.provider
  ├─ 读取 params.legacyParams.model
  ├─ 读取 params.legacyParams.config.plugins.entries["lossless-claw"].config.summaryModel
  ├─ 读取 params.legacyParams.config.agents.defaults.compaction.model
  └─ 尝试 deps.resolveModel() 解析
  
  ↓
  
如果所有来源都返回空 → 报错 "no summary model candidates resolved"
```

### 2. 配置传递链路

```
lcm-config.json
  ↓
index.js: loadLcmConfig()
  ↓
index.js: createLcmDependencies({ legacyParams })
  ↓
lcm-adapter.js: createLcmDependencies() → deps.legacyParams
  ↓
engine.ts: constructor(deps) → this.deps.legacyParams
  ↓
engine.ts: compact() → params.legacyParams
  ↓
engine.ts: resolveSummarize({ legacyParams })
  ↓
summarize.ts: createLcmSummarizeFromLegacyParams({ legacyParams })
  ↓
summarize.ts: resolveSummaryCandidates({ legacyParams })
  ↓
✅ 成功解析 model candidates
```

### 3. legacyParams 的正确结构

```javascript
{
  provider: "openai",
  model: "qwen3.5-plus",
  config: {
    plugins: {
      entries: {
        "lossless-claw": {
          config: {
            summaryProvider: "openai",
            summaryModel: "qwen3.5-plus"
          }
        }
      }
    },
    agents: {
      defaults: {
        model: "qwen3.5-plus",
        compaction: {
          model: "qwen3.5-plus"
        }
      }
    }
  }
}
```

---

## 🚀 如何使用

### 启动服务器
```bash
cd C:\workspace\CoPaw\lcm-server
npm start
```

### 验证运行
```bash
# 健康检查
curl http://localhost:3721/health

# 运行测试
python test_force_compact.py

# 检查错误
test_server_errors.bat
```

### 预期日志
```
✅ [LCM] Configuration loaded from: ...
✅ [LCM] lossless-claw package loaded successfully
✅ [LCM] LLM Provider: openai
✅ [LCM] LLM Model: qwen3.5-plus
✅ [LCM] ✅ Engine ready, waiting for sessions
```

**不再出现** ❌:
```
[lcm] createLcmSummarize: no summary model candidates resolved
```

---

## ✅ 验证清单

- [x] `lcm-config.json` 包含 `summary` 配置块
- [x] `index.js` 构造完整的 `legacyParams` 对象
- [x] `lcm-adapter.js` 存储 `legacyParams` 到 `deps`
- [x] `index.js` 的 `/compact` 路由传递 `legacyParams`
- [x] 服务器启动无错误日志
- [x] 健康检查返回正常
- [x] 强制压缩测试通过
- [x] Summary model 正常工作
- [x] 不再出现 "no summary model candidates" 错误

---

## 🎓 经验总结

1. **配置结构必须匹配**: `lossless-claw` 期望特定嵌套结构的 `legacyParams`
2. **传递链路要完整**: 从配置加载到最终使用，每个环节都要正确传递
3. **调试输出很重要**: 添加 `console.error` 调试输出帮助定位问题
4. **测试覆盖关键路径**: 强制压缩测试验证了完整的 summarizer 流程

---

**修复完成**: 2026-04-03  
**修复者**: 大呙（大 guowei）  
**测试状态**: ✅ 全部通过  
**生产就绪**: ✅ 可以部署
