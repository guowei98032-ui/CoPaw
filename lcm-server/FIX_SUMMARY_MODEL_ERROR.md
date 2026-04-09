# LCM "no summary model candidates resolved" 问题修复报告

## 📋 问题描述

运行 LCM 服务器时出现以下错误：

```
[lcm] createLcmSummarize: no summary model candidates resolved
[lcm] resolveSummarize: createLcmSummarizeFromLegacyParams returned undefined
[lcm] resolveSummarize: FALLING BACK TO EMERGENCY TRUNCATION
```

## 🔍 问题根源

### 1. 错误含义

`lossless-claw` 包在创建 summarizer 时，需要从以下 5 个来源解析 summary model：

1. **环境变量**: `LCM_SUMMARY_MODEL` 和 `LCM_SUMMARY_PROVIDER`
2. **插件配置**: `plugins.entries["lossless-claw"].config.summaryModel`
3. **OpenClaw 配置**: `agents.defaults.compaction.model`
4. **OpenClaw 默认**: `agents.defaults.model`
5. **Legacy 参数**: 从 `legacyParams.model` 和 `legacyParams.provider`

如果**所有来源都返回空**，则报错 "no summary model candidates resolved"。

### 2. 具体原因

你的 `lcm-config.json` 中配置了：
```json
{
  "llm": {
    "provider": "openai",
    "model": "qwen3.5-plus",
    ...
  }
}
```

但是这个配置**没有正确传递**给 `lossless-claw` 的 summarizer，因为：

1. `lcm-config.json` 中的 `llm` 配置用于**普通 LLM 调用**
2. Summarizer 需要**独立的 summary 配置**或**环境变量**
3. Python 客户端传递的配置格式不匹配（`api_key` vs `apiKey`）

---

## ✅ 解决方案

### 方案 1：添加 summary 配置到 lcm-config.json（推荐）

**修改后的配置：**

```json
{
  "$schema": "./lcm-config.schema.json",
  "enabled": true,
  "server": {
    "host": "localhost",
    "port": 3721
  },
  "database": {
    "basePath": "./data",
    "defaultDbName": "lcm.db"
  },
  "llm": {
    "provider": "openai",
    "model": "qwen3.5-plus",
    "apiKey": "sk-sp-4fe2f039355645e18038499216be4fa5",
    "baseUrl": "https://coding.dashscope.aliyuncs.com/v1",
    "timeout": 30000
  },
  "summary": {
    "provider": "openai",
    "model": "qwen3.5-plus",
    "apiKey": "sk-sp-4fe2f039355645e18038499216be4fa5",
    "baseUrl": "https://coding.dashscope.aliyuncs.com/v1"
  },
  "embedding": {
    "backend": "openai",
    "apiKey": "sk-sp-4fe2f039355645e18038499216be4fa5",
    "baseUrl": "https://dashscope.aliyuncs.com/api/v1",
    "modelName": "text-embedding-v2",
    "dimensions": 1536,
    "enableCache": true,
    "maxCacheSize": 3000,
    "maxInputLength": 8192,
    "maxBatchSize": 10
  },
  "compaction": {
    "contextThreshold": 0.75,
    "freshTailCount": 32,
    "maxContextTokens": 128000,
    "autoCompact": true
  },
  "logging": {
    "level": "info",
    "debug": false
  }
}
```

### 方案 2：设置环境变量

```bash
# Windows CMD
set LCM_SUMMARY_MODEL=qwen3.5-plus
set LCM_SUMMARY_PROVIDER=openai
cd C:\workspace\CoPaw\lcm-server
npm start

# Windows PowerShell
$env:LCM_SUMMARY_MODEL="qwen3.5-plus"
$env:LCM_SUMMARY_PROVIDER="openai"
cd C:\workspace\CoPaw\lcm-server
npm start
```

### 方案 3：修改代码支持配置传递

已修改以下文件：

#### 1. `lcm-adapter.js`
- 添加 `summaryConfig` 参数支持
- 优先使用 summary-specific 配置

#### 2. `index.js`
- 从 config 读取 `summary` 配置
- 传递给 `createLcmDependencies`

#### 3. `lcm_memory_manager.py`
- `_get_llm_config()` 添加 `summary_model` 和 `summary_provider`

---

## 🧪 验证方法

### 1. 重启 LCM 服务器

```bash
cd C:\workspace\CoPaw\lcm-server
npm start
```

### 2. 检查启动日志

**正确的日志应该显示：**
```
[LCM] Configuration loaded from: C:\workspace\CoPaw\lcm-server\lcm-config.json
[LCM] lossless-claw package loaded successfully
[LCM] LLM Provider: openai
[LCM] LLM Model: qwen3.5-plus
[LCM] Dependencies created, databasePath: ./data/lcm.db
[LCM] Server running on port 3721
[LCM] ✅ Engine ready, waiting for sessions
```

**错误日志（修复前）：**
```
[LCM] lossless-claw package loaded successfully
...
[lcm] createLcmSummarize: no summary model candidates resolved
[lcm] resolveSummarize: FALLING BACK TO EMERGENCY TRUNCATION
```

### 3. 测试健康检查

```bash
curl http://localhost:3721/health
```

**预期响应：**
```json
{
  "status": "healthy",
  "lcmAvailable": true,
  "activeSessions": 0,
  "timestamp": "2026-04-03T...",
  "config": {
    "databasePath": "./data/lcm.db",
    "contextThreshold": 0.75,
    "freshTailCount": 32,
    "provider": "openai",
    "model": "qwen3.5-plus",
    "autoCompact": true
  }
}
```

### 4. 测试完整功能

运行 Python 测试脚本：

```bash
cd C:\workspace\CoPaw\lcm-server
python test_full_functionality.py
```

---

## 📝 技术细节

### lossless-claw 的模型解析流程

```
resolveSummaryCandidates()
  ├─ 检查 LCM_SUMMARY_MODEL 环境变量
  ├─ 检查插件配置 summaryModel
  ├─ 检查 agents.defaults.compaction.model
  ├─ 检查 agents.defaults.model
  └─ 检查 legacyParams.model
  
  ↓
  
对每个候选调用 deps.resolveModel(modelRef, providerHint)
  ├─ 如果 modelRef 包含 ':' → 分割为 provider:model
  └─ 否则使用 providerHint 或 defaultProvider
  
  ↓
  
如果所有候选都失败 → 返回空数组 → 报错 "no summary model candidates resolved"
```

### 配置优先级

```
1. 环境变量 (最高优先级)
   LCM_SUMMARY_MODEL, LCM_SUMMARY_PROVIDER
   
2. 插件配置
   plugins.entries["lossless-claw"].config.summaryModel
   
3. OpenClaw agents.defaults.compaction.model
   
4. OpenClaw agents.defaults.model
   
5. Legacy runtime/session model (最低优先级)
```

---

## 🎯 最佳实践建议

### 1. 使用独立的 summary 配置

建议为 summarization 使用**独立的配置块**，与普通 LLM 调用分离：

```json
{
  "llm": { ... },      // 用于普通对话
  "summary": { ... },  // 用于压缩/摘要
  "embedding": { ... } // 用于向量嵌入
}
```

### 2. 使用 provider:model 格式

在配置中使用 `provider:model` 格式，避免歧义：

```json
{
  "summary": {
    "model": "openai:qwen3.5-plus"  // 明确指定 provider
  }
}
```

### 3. 启用调试日志

在 `lcm-config.json` 中启用 debug 模式查看详细解析过程：

```json
{
  "logging": {
    "level": "debug",
    "debug": true
  }
}
```

### 4. 验证 API 密钥

确保 API 密钥有效且有足够的配额：

```bash
curl -X POST https://coding.dashscope.aliyuncs.com/v1/chat/completions \
  -H "Authorization: Bearer sk-sp-4fe2f039355645e18038499216be4fa5" \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3.5-plus","messages":[{"role":"user","content":"test"}]}'
```

---

## 📚 相关文件

- **配置文件**: `C:\workspace\CoPaw\lcm-server\lcm-config.json`
- **服务器入口**: `C:\workspace\CoPaw\lcm-server\index.js`
- **适配器**: `C:\workspace\CoPaw\lcm-server\lcm-adapter.js`
- **Python 管理器**: `C:\workspace\CoPaw\src\copaw\agents\memory\lcm_memory_manager.py`
- **Python 客户端**: `C:\workspace\CoPaw\src\copaw\agents\memory\lcm_client.py`
- **lossless-claw 源码**: `C:\workspace\CoPaw\lcm-server\node_modules\@martian-engineering\lossless-claw\src\summarize.ts`

---

## 🔗 参考资料

- [lossless-claw README](./node_modules/@martian-engineering/lossless-claw/README.md)
- [LCM 设计文档](./docs/lcm-design.md)
- [OpenClaw Plugin Spec](./node_modules/@martian-engineering/lossless-claw/openclaw.plugin.json)

---

**修复完成时间**: 2026-04-03  
**修复者**: 大呙（大 guowei）
