# LCM 搜索功能说明

## ✅ LCM 已实现的搜索功能

lossless-claw 提供以下工具：

| 工具 | 功能 | 搜索类型 | 是否需要 Embedding |
|------|------|---------|-------------------|
| `lcm_grep` | 搜索历史消息和摘要 | **全文搜索 (FTS5)** | ❌ 否 |
| `lcm_describe` | 查看摘要详情 | - | ❌ 否 |
| `lcm_expand` | 展开摘要获取原始消息 | - | ❌ 否 |

## 🔍 搜索类型对比

### LCM 当前的 `lcm_grep` (全文搜索)

```javascript
// 搜索关键词
await lcm_grep({ pattern: "机器学习", mode: "full_text" })

// 匹配结果：
// - "我想学习机器学习" ✅
// - "机器学习的优势" ✅
// - "ML 技术" ❌ (不包含"机器学习"这个词)
```

**特点：**
- ✅ 使用 SQLite FTS5 全文搜索
- ✅ 快速、准确
- ✅ 支持正则表达式
- ❌ 无法理解语义相似度

### 向量搜索 (未实现)

```javascript
// 如果实现向量搜索
await vector_search({ query: "机器学习", topK: 5 })

// 匹配结果：
// - "我想学习机器学习" ✅
// - "ML 技术" ✅ (语义相似)
// - "神经网络训练" ✅ (语义相似)
// - "深度学习算法" ✅ (语义相似)
```

**特点：**
- ✅ 理解语义关系
- ✅ 可以找到同义词、相关概念
- ❌ 需要 embedding 模型
- ❌ 需要向量数据库
- ❌ LCM 当前**未实现**

## ❓ 那为什么配置中有 embedding 字段？

### 原因 1：与 ReMeLight 配置兼容

`LCMMemoryManager` 需要实现与 `ReMeLightMemoryManager` 相同的接口：

```python
# BaseMemoryManager 要求的方法
class BaseMemoryManager:
    @abstractmethod
    def get_embedding_config(self) -> dict:
        """返回 embedding 配置"""
```

这样上层代码可以统一处理两种 memory manager，无需关心后端实现。

### 原因 2：为未来扩展预留

虽然当前 lossless-claw 不使用 embedding，但未来可能：
- 添加语义搜索功能
- 支持向量相似度匹配
- 与 ReMeLight 共享 embedding 缓存

### 原因 3：配置一致性

CoPaw 的配置系统中，`EmbeddingConfig` 是标准配置项：

```python
class AgentRunningConfig:
    embedding_config: EmbeddingConfig = Field(...)
    memory_manager_backend: Literal["remelight", "lcm"] = Field(...)
```

无论使用哪种 memory manager，配置结构保持一致。

## 📊 功能对比表

| 功能 | ReMeLight | LCM (lossless-claw) |
|------|-----------|---------------------|
| **消息存储** | SQLite + 向量索引 | SQLite |
| **搜索方式** | 向量搜索 + 全文搜索 | 全文搜索 (FTS5) |
| **摘要方式** | 扁平化摘要 | DAG 层次化摘要 |
| **需要 Embedding** | ✅ 是 | ❌ 否 (但配置中保留) |
| **语义理解** | ✅ 支持 | ❌ 不支持 |
| **关键词搜索** | ✅ 支持 | ✅ 支持 |
| **正则搜索** | ❌ 不支持 | ✅ 支持 |
| **摘要展开** | ❌ 不支持 | ✅ 支持 (`lcm_expand`) |
| **摘要详情** | ❌ 不支持 | ✅ 支持 (`lcm_describe`) |

## 🎯 实际使用建议

### 使用 LCM 的场景
- 需要**完整的对话历史**（不丢失任何消息）
- 需要**层次化摘要**（从细节到概览）
- 主要使用**关键词搜索**
- 需要**展开摘要查看原始消息**

### 使用 ReMeLight 的场景
- 需要**语义搜索**（理解含义而非关键词）
- 需要**向量相似度匹配**
- 可以接受**有损压缩**（只保留重要内容）

## 💡 总结

1. **LCM 当前不使用 embedding** - 搜索基于 FTS5 全文搜索
2. **Embedding 配置是为了接口兼容性** - 与 ReMeLight 保持一致
3. **未来可能扩展** - 预留 embedding 配置便于后续添加语义搜索
4. **两种方案互补** - LCM 擅长完整性和层次化，ReMeLight 擅长语义理解

## 📝 配置示例

虽然 LCM 不使用 embedding，但配置文件仍保留该字段：

```json
{
  "embedding": {
    "backend": "openai",
    "apiKey": "sk-xxx",
    "modelName": "text-embedding-3-small",
    // ... 其他配置
  }
}
```

**这是正常的！** 这个配置：
- ✅ 让 `get_embedding_config()` 可以返回有效值
- ✅ 保持与 ReMeLight 的配置结构一致
- ✅ 为未来可能的功能扩展做准备
- ⚠️ 当前不会被 lossless-claw 实际使用
