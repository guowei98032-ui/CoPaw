# LCM Server Configuration Guide

## 配置说明

LCM Server 现在支持从配置文件加载设置，不再依赖环境变量。

## 快速开始

### 1. 创建配置文件

复制示例配置文件：

```bash
cd C:\workspace\CoPaw\lcm-server
copy lcm-config.example.json lcm-config.json
```

### 2. 编辑配置

编辑 `lcm-config.json`，填入你的 API 密钥和其他设置：

```json
{
  "server": {
    "host": "localhost",
    "port": 3721
  },
  "llm": {
    "provider": "openai",
    "model": "gpt-4",
    "apiKey": "sk-your-actual-api-key-here",
    "baseUrl": "https://api.openai.com/v1"
  },
  "compaction": {
    "contextThreshold": 0.75,
    "freshTailCount": 32,
    "maxContextTokens": 128000
  }
}
```

### 3. 启动服务

```bash
npm install
npm start
```

## 配置项说明

### server - 服务器设置
| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| host | string | localhost | 服务器监听地址 |
| port | number | 3721 | 服务器端口 |

### database - 数据库设置
| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| basePath | string | ./data | 数据库文件存储目录 |
| defaultDbName | string | lcm.db | 默认数据库文件名 |

### llm - LLM 设置
| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| provider | string | openai | LLM 提供商 (openai/azure/custom) |
| model | string | gpt-4 | 模型名称 |
| apiKey | string | - | API 密钥（必填） |
| baseUrl | string | - | API 基础 URL |
| timeout | number | 30000 | 请求超时（毫秒） |

### embedding - Embedding 模型设置
用于语义搜索、向量相似度匹配等功能。

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| backend | string | openai | Embedding 后端 (openai 等) |
| apiKey | string | - | API 密钥 |
| baseUrl | string | - | API 基础 URL |
| modelName | string | text-embedding-3-small | Embedding 模型名称 |
| dimensions | number | 1536 | Embedding 维度 |
| enableCache | boolean | true | 是否启用缓存 |
| maxCacheSize | number | 3000 | 最大缓存大小 |
| maxInputLength | number | 8192 | 最大输入长度 |
| maxBatchSize | number | 10 | 最大批次大小 |

**阿里云 DashScope 示例：**
```json
"embedding": {
  "backend": "openai",
  "apiKey": "sk-your-dashscope-key",
  "baseUrl": "https://dashscope.aliyuncs.com/api/v1",
  "modelName": "text-embedding-v2",
  "dimensions": 1536
}
```

### compaction - 压缩设置
| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| contextThreshold | float | 0.75 | 触发压缩的上下文使用率阈值 |
| freshTailCount | int | 32 | 保护的最近消息数量 |
| maxContextTokens | int | 128000 | 最大上下文 token 数 |
| autoCompact | boolean | true | 是否自动压缩 |

### logging - 日志设置
| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| level | string | info | 日志级别 (debug/info/warn/error) |
| debug | boolean | false | 是否启用调试模式 |

## 环境变量回退

如果找不到 `lcm-config.json` 文件，系统会回退到使用环境变量：

```bash
# LLM 配置
LCM_HOST=localhost
LCM_PORT=3721
LCM_PROVIDER=openai
LCM_MODEL=gpt-4
LCM_API_KEY=sk-xxx
LCM_BASE_URL=https://api.openai.com/v1
LCM_TIMEOUT=30000

# Embedding 配置
EMBEDDING_BACKEND=openai
EMBEDDING_API_KEY=sk-xxx
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_MODEL_NAME=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
EMBEDDING_ENABLE_CACHE=true
EMBEDDING_MAX_CACHE_SIZE=3000
EMBEDDING_MAX_INPUT_LENGTH=8192
EMBEDDING_MAX_BATCH_SIZE=10

# 压缩配置
LCM_CONTEXT_THRESHOLD=0.75
LCM_FRESH_TAIL_COUNT=32
LCM_MAX_CONTEXT_TOKENS=128000
LCM_AUTO_COMPACT=true
```

## 安全提示

⚠️ **重要：** `lcm-config.json` 包含敏感的 API 密钥，已添加到 `.gitignore`，不会被提交到版本控制。

请勿将包含真实 API 密钥的配置文件分享给他人！

## 测试配置

启动服务后，访问健康检查端点验证配置：

```bash
curl http://localhost:3721/health
```

响应示例：
```json
{
  "status": "healthy",
  "lcmAvailable": true,
  "config": {
    "provider": "openai",
    "model": "gpt-4",
    "databasePath": "./data/lcm.db"
  }
}
```
