# LCM Embedding 配置更新说明

## ✅ 更新内容

已为 LCM 服务添加完整的 Embedding 模型配置支持，与 ReMeLight Memory Manager 保持一致。

## 📁 修改的文件

### 1. Node.js 服务端
- **`lcm-config.json`** - 添加 embedding 配置段
- **`lcm-config.example.json`** - 示例文件同步更新
- **`index.js`** - 支持从配置文件和环境变量加载 embedding 配置
- **`CONFIG.md`** - 添加 embedding 配置项说明文档

### 2. Python 客户端
- **`lcm_memory_manager.py`** - 添加 `get_embedding_config()` 方法

## 🔧 Embedding 配置结构

```json
{
  "embedding": {
    "backend": "openai",
    "apiKey": "sk-your-api-key",
    "baseUrl": "https://api.openai.com/v1",
    "modelName": "text-embedding-3-small",
    "dimensions": 1536,
    "enableCache": true,
    "maxCacheSize": 3000,
    "maxInputLength": 8192,
    "maxBatchSize": 10
  }
}
```

## 📊 配置项说明

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| backend | string | openai | Embedding 后端类型 |
| apiKey | string | - | API 密钥 |
| baseUrl | string | - | API 基础 URL |
| modelName | string | text-embedding-3-small | 模型名称 |
| dimensions | number | 1536 | Embedding 维度 |
| enableCache | boolean | true | 启用缓存 |
| maxCacheSize | number | 3000 | 最大缓存数 |
| maxInputLength | number | 8192 | 最大输入长度 |
| maxBatchSize | number | 10 | 最大批次大小 |

## 🌐 提供商示例

### OpenAI
```json
{
  "backend": "openai",
  "apiKey": "sk-xxx",
  "baseUrl": "https://api.openai.com/v1",
  "modelName": "text-embedding-3-small",
  "dimensions": 1536
}
```

### 阿里云 DashScope
```json
{
  "backend": "openai",
  "apiKey": "sk-sp-xxx",
  "baseUrl": "https://dashscope.aliyuncs.com/api/v1",
  "modelName": "text-embedding-v2",
  "dimensions": 1536
}
```

## 🔑 环境变量回退

如果未使用配置文件，可通过环境变量配置：

```bash
EMBEDDING_BACKEND=openai
EMBEDDING_API_KEY=sk-xxx
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_MODEL_NAME=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
EMBEDDING_ENABLE_CACHE=true
EMBEDDING_MAX_CACHE_SIZE=3000
EMBEDDING_MAX_INPUT_LENGTH=8192
EMBEDDING_MAX_BATCH_SIZE=10
```

## 🐍 Python 使用

```python
from copaw.agents.memory import LCMMemoryManager

manager = LCMMemoryManager(
    working_dir="C:/workspace/CoPaw/data",
    agent_id="default"
)

# 获取 embedding 配置（与 ReMeLight 兼容）
emb_config = manager.get_embedding_config()
print(emb_config)
# 输出:
# {
#   "backend": "openai",
#   "api_key": "sk-xxx",
#   "base_url": "...",
#   "model_name": "text-embedding-v2",
#   "dimensions": 1536,
#   ...
# }
```

## ✅ 验证配置

重启服务后检查健康状态：

```bash
curl http://localhost:3721/health
```

配置已加载会显示：
```json
{
  "status": "healthy",
  "lcmAvailable": true,
  "config": {
    "provider": "openai",
    "model": "qwen3.5-plus",
    ...
  }
}
```

## 📝 注意事项

1. **API 密钥安全**: `lcm-config.json` 已添加到 `.gitignore`，不会被提交
2. **与 ReMeLight 兼容**: `get_embedding_config()` 返回的格式与 ReMeLightMemoryManager 一致
3. **未来扩展**: Embedding 配置为后续语义搜索、向量相似度等功能预留

## 🎯 下一步

当前 embedding 配置已就绪，未来可以：
- 实现语义搜索功能
- 支持向量相似度匹配
- 与 ReMeLight 共享 embedding 缓存
- 支持多种 embedding 后端切换
