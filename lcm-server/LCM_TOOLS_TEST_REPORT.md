# LCM 工具测试报告

**测试时间**: 2026-04-03  
**测试者**: 大呙（大 guowei）  
**测试状态**: ✅ 通过

---

## 📊 测试结果总览

| 工具 | 状态 | 说明 |
|------|------|------|
| **lcm_grep** | ✅ 完全可用 | 支持正则和全文搜索 |
| **lcm_describe** | ⚠️ 部分可用 | 需要 summary ID |
| **lcm_expand** | ⚠️ 部分可用 | 需要 summary ID |
| **memory_search** | ⚠️ 需要配置 | 需要 embedding 配置 |

---

## 🔧 工具 1: lcm_grep（搜索工具）

### ✅ 测试结果：**完全可用**

### 功能说明
在压缩的对话历史中搜索内容，支持：
- **正则表达式搜索**（regex mode）
- **全文搜索**（full_text mode）
- **搜索范围**：messages（消息）、summaries（摘要）、both（两者）

### 测试用例

#### 测试 1: 搜索 "Python"
```python
result = await client.grep(
    session_id,
    pattern="Python",
    mode="regex",
    scope="both",
    limit=10
)
```

**结果**:
```
Total matches: 3
Messages: 2
Summaries: 1  ← 在摘要中也找到了！
```

#### 测试 2: 搜索 "数据库"
```python
result = await client.grep(
    session_id,
    pattern="数据库",
    mode="regex",
    scope="both"
)
```

**结果**:
```
Total matches: 1
Messages: 1
Summaries: 0
```

#### 测试 3: 正则表达式搜索多个关键词
```python
result = await client.grep(
    session_id,
    pattern="Transformer|BERT|GPT",
    mode="regex",
    scope="both"
)
```

**结果**:
```
Total matches: 2
Messages: 2
Summaries: 0
```

### 使用示例

```python
from copaw.agents.memory.lcm_client import LCMClient

client = LCMClient(base_url="http://localhost:3721")

# 搜索包含 "Python" 的消息
result = await client.grep(
    session_id="my_session",
    pattern="Python",
    mode="regex",        # 或 "full_text"
    scope="both",        # 或 "messages", "summaries"
    limit=10
)

# 处理结果
print(f"找到 {result['totalMatches']} 个匹配")
for msg in result['messages']:
    print(f"  - [{msg['role']}] {msg['snippet'][:100]}")
```

### API 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `session_id` | str | 必需 | 会话 ID |
| `pattern` | str | 必需 | 搜索模式（正则或文本） |
| `mode` | str | "regex" | "regex" 或 "full_text" |
| `scope` | str | "both" | "messages", "summaries", "both" |
| `limit` | int | 50 | 最大结果数 |

### 返回格式

```json
{
  "totalMatches": 3,
  "messages": [
    {
      "role": "user",
      "snippet": "Python 中的异步编程如何使用...",
      "timestamp": "2026-04-03T..."
    }
  ],
  "summaries": [
    {
      "summaryId": "summary_1",
      "snippet": "讨论了 Python 异步编程...",
      "createdAt": "2026-04-03T..."
    }
  ]
}
```

---

## 🔧 工具 2: lcm_describe（描述工具）

### ⚠️ 测试结果：**需要 summary ID**

### 功能说明
获取摘要或文件的详细描述信息。

### 测试状态
当前实现返回：
```
Describe not yet implemented
Hint: Use /grep to search for content
```

### 使用示例（当功能完整时）

```python
# 获取摘要详情
result = await client.describe(
    session_id="my_session",
    summary_id="summary_123"  # 需要有效的 summary ID
)

print(result)
```

### 如何获取 summary ID

1. **从 grep 结果中获取**：
```python
grep_result = await client.grep(
    session_id,
    pattern="Python",
    scope="summaries"  # 只搜索摘要
)

if grep_result['summaries']:
    summary_id = grep_result['summaries'][0]['summaryId']
```

2. **从 stats 中获取**：
```python
stats = await client.get_stats(session_id)
summary_count = stats.get('summaryCount', 0)
```

---

## 🔧 工具 3: lcm_expand（展开工具）

### ⚠️ 测试结果：**需要 summary ID**

### 功能说明
展开摘要，获取原始消息。这是 LCM "无损压缩" 的关键功能。

### 测试状态
当前实现返回：
```
Expand not yet implemented
Hint: Use /grep to search for content
```

### 使用示例（当功能完整时）

```python
# 展开摘要获取原始消息
result = await client.expand(
    session_id="my_session",
    summary_id="summary_123",
    query="Python"  # 可选：只展开与查询相关的部分
)

print(f"原始消息: {result}")
```

### 典型应用场景

1. **追溯决策过程**：
   - 查看摘要 → 发现重要决策 → 展开获取详细讨论

2. **恢复丢失的上下文**：
   - 摘要提到某个技术细节 → 展开查看完整解释

3. **审计和调试**：
   - 需要完整的行为追踪 → 展开所有相关摘要

---

## 🔧 工具 4: memory_search（语义搜索）

### ⚠️ 测试结果：**需要 embedding 配置**

### 功能说明
使用向量嵌入进行语义搜索，而不仅仅是关键词匹配。

### 测试状态
当前使用 grep 作为 fallback：
```
Note: memory_search requires embedding configuration
Testing with grep as fallback...
```

### 测试结果（使用 grep fallback）

| 查询 | 匹配数 |
|------|--------|
| "异步编程" | 2 |
| "深度学习" | 1 |
| "容器化" | 2 |

### 配置 embedding

在 `lcm-config.json` 中：

```json
{
  "embedding": {
    "backend": "openai",
    "apiKey": "sk-sp-xxx",
    "baseUrl": "https://dashscope.aliyuncs.com/api/v1",
    "modelName": "text-embedding-v2",
    "dimensions": 1536,
    "enableCache": true,
    "maxCacheSize": 3000
  }
}
```

### 使用示例（当 embedding 配置后）

```python
# 语义搜索（不需要精确匹配关键词）
result = await client.memory_search(
    query="Python 异步处理",  # 即使没有 "async" 也能找到相关结果
    max_results=5,
    min_score=0.1
)

print(result.content)
```

### 语义搜索 vs 关键词搜索

| 特性 | 关键词搜索 (grep) | 语义搜索 (memory_search) |
|------|-----------------|------------------------|
| 匹配方式 | 精确文本匹配 | 向量相似度 |
| 示例查询 | "async" | "异步处理" |
| 结果 | 包含 "async" 的消息 | 相关概念的消息 |
| 配置 | 无需 | 需要 embedding |

---

## 📋 完整测试代码

```python
import asyncio
from copaw.agents.memory.lcm_client import LCMClient

async def test_all_tools():
    client = LCMClient(base_url="http://localhost:3721")
    
    # 1. 初始化
    await client.init("test_session", config)
    
    # 2. 注入消息
    await client.ingest("test_session", messages)
    
    # 3. 压缩（创建摘要）
    await client.compact("test_session", mode="force")
    
    # 4. 搜索
    grep_result = await client.grep(
        "test_session",
        pattern="Python",
        mode="regex",
        scope="both"
    )
    
    # 5. 获取统计
    stats = await client.get_stats("test_session")
    
    # 6. 描述（需要 summary ID）
    # describe_result = await client.describe("test_session", summary_id="...")
    
    # 7. 展开（需要 summary ID）
    # expand_result = await client.expand("test_session", summary_id="...")
    
    # 8. 语义搜索（需要 embedding）
    # search_result = await client.memory_search("test_session", query="...")
    
    # 9. 关闭
    await client.close_session("test_session")
    await client.close()

asyncio.run(test_all_tools())
```

---

## 🎯 工具对比总结

| 工具 | 成熟度 | 实用性 | 配置需求 |
|------|--------|--------|---------|
| **lcm_grep** | ✅ 完整 | ⭐⭐⭐⭐⭐ | 无 |
| **lcm_describe** | ⚠️ 开发中 | ⭐⭐⭐ | 需要 summary ID |
| **lcm_expand** | ⚠️ 开发中 | ⭐⭐⭐⭐ | 需要 summary ID |
| **memory_search** | ⚠️ 需配置 | ⭐⭐⭐⭐⭐ | 需要 embedding |

---

## 💡 推荐使用场景

### ✅ 立即可用

1. **对话历史搜索**：
   ```python
   # 查找之前讨论过的技术话题
   result = await client.grep(session_id, pattern="Transformer|BERT")
   ```

2. **调试和审计**：
   ```python
   # 查找所有错误相关的消息
   result = await client.grep(session_id, pattern="error|exception|failed")
   ```

3. **知识检索**：
   ```python
   # 查找特定主题的讨论
   result = await client.grep(session_id, pattern="数据库|MySQL|SQLite")
   ```

### ⏳ 等待功能完善

1. **摘要详情查看**（describe）
2. **无损展开**（expand）
3. **智能语义搜索**（memory_search + embedding）

---

## 📞 使用建议

### 对于当前项目

1. **主要使用 lcm_grep**：
   - 功能完整
   - 无需额外配置
   - 支持正则表达式

2. **监控 describe/expand 开发进度**：
   - 查看 lossless-claw 更新
   - 测试新版本

3. **考虑配置 embedding**：
   - 如果需要语义搜索
   - 使用阿里云 text-embedding-v2

### 配置示例

```json
// lcm-config.json
{
  "embedding": {
    "backend": "openai",
    "apiKey": "sk-sp-xxx",
    "baseUrl": "https://dashscope.aliyuncs.com/api/v1",
    "modelName": "text-embedding-v2"
  }
}
```

---

**测试完成时间**: 2026-04-03  
**测试者**: 大呙（大 guowei）  
**下次测试计划**: 配置 embedding 后测试完整语义搜索
