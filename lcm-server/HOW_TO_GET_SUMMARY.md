# LCM 获取 Summary 指南

**日期**: 2026-04-02  
**版本**: LCM v0.5.3

---

## 📋 概述

调用 `LCMMemoryManager.compact_memory()` 后，**不会直接返回 summary 内容**，而是返回状态字符串。

```python
result = await mm.compact_memory(messages)
print(result)  # 输出：'[LCM Compacted: compacted]'
```

LCM 使用 **DAG 摘要链** 机制，summary 存储在内部数据库中，需要通过其他方式访问。

---

## 🔍 获取 Summary 的方法

### 方法 1: `compact_memory()` 返回值

**用途**: 确认是否发生了压缩

```python
result = await mm.compact_memory(messages)

if result:
    print(f"压缩状态：{result}")
    # 输出：'[LCM Compacted: compacted]'
else:
    print("未发生压缩")
```

**返回值说明**:
- `'[LCM Compacted: compacted]'` - 已压缩
- `''` (空字符串) - 未压缩（消息量未达阈值）

---

### 方法 2: `lcm_grep()` 搜索压缩历史 ⭐ 推荐

**用途**: 搜索压缩后的消息和摘要

```python
# 搜索关键词
results = await mm.lcm_grep("Python", limit=10)

for item in results:
    print(f"角色：{item['role']}")
    print(f"片段：{item['snippet']}")
    print(f"消息 ID: {item['messageId']}")
    print("---")
```

**返回格式**:
```python
[
    {
        'messageId': 4659,
        'conversationId': 1,
        'role': 'user',
        'snippet': 'Python...',
        'createdAt': '2026-04-02T05:43:45.000Z',
        'rank': 0
    },
    # ...
]
```

**参数**:
- `query`: 搜索关键词或正则表达式
- `limit`: 最大结果数 (默认 10)
- `mode`: `"regex"` 或 `"full_text"`

---

### 方法 3: `memory_search()` ToolResponse 格式

**用途**: 以 ToolResponse 格式获取搜索结果（适合 Agent 工具）

```python
from copaw.agents.memory.lcm_memory_manager import ToolResponse

result = await mm.memory_search("机器学习", max_results=5)

print(f"类型：{type(result)}")
print(f"内容：{result.content}")
print(f"元数据：{result.metadata}")
```

**返回格式**:
```python
ToolResponse(
    content="Found 6 matches:\n  - [user] Python\n  - [assistant] Python...",
    metadata={
        "total_matches": 6,
        "query": "机器学习"
    }
)
```

---

### 方法 4: `get_context()` 获取组装上下文

**用途**: 获取用于模型输入的完整上下文（包含摘要 + 实时消息）

```python
# 注意：需要先在 LCMClient 中添加 get_context 方法
context = await mm.get_context()

for msg in context:
    print(f"{msg['role']}: {msg['content']}")
```

**说明**:
- 返回 LCM 组装的完整上下文
- 包含压缩摘要和最近的 live messages
- 尊重 token budget 限制

---

### 方法 5: `get_stats()` 获取会话统计

**用途**: 获取会话的统计信息（消息数、摘要数等）

```python
# 需要先在 LCMClient 中添加 get_stats 方法
stats = await mm._client.get_stats(mm.agent_id)

print(f"会话 ID: {stats.get('sessionId')}")
print(f"活跃：{stats.get('active')}")
print(f"消息数：{stats.get('messageCount')}")
print(f"摘要数：{stats.get('summaryCount')}")
```

---

### 方法 6: `lcm_describe()` 描述摘要 (⚠️ 服务器未实现)

**用途**: 获取特定摘要的详细信息

```python
# 需要 summary_id（从 compact result 或其他地方获取）
description = await mm.lcm_describe(summary_id="summary_123")
print(description)
```

**当前状态**: ⚠️ 服务器端未实现，返回错误提示

---

### 方法 7: `lcm_expand()` 展开摘要 (⚠️ 服务器未实现)

**用途**: 从摘要展开获取原始消息

```python
# 需要 summary_id
original_messages = await mm.lcm_expand(
    summary_id="summary_123",
    query="Python"  # 可选，过滤特定内容
)
print(original_messages)
```

**当前状态**: ⚠️ 服务器端未实现，返回错误提示

---

## 🎯 推荐工作流程

### 场景 1: 查看压缩后的内容

```python
# 1. 压缩消息
result = await mm.compact_memory(messages)
print(f"压缩状态：{result}")

# 2. 搜索感兴趣的内容
results = await mm.lcm_grep("Python", limit=10)
for item in results:
    print(f"[{item['role']}] {item['snippet']}")
```

### 场景 2: Agent 工具调用

```python
# 在 Agent 工具中使用 memory_search
async def search_memory(query: str):
    result = await mm.memory_search(query, max_results=5)
    return result.content
```

### 场景 3: 获取模型上下文

```python
# 获取组装好的上下文用于模型输入
context = await mm.get_context()
# 传递给模型...
```

---

## 📊 方法对比

| 方法 | 返回类型 | 用途 | 状态 |
|------|---------|------|------|
| `compact_memory()` | `str` | 确认压缩状态 | ✅ 可用 |
| `lcm_grep()` | `list[dict]` | 搜索压缩历史 | ✅ 可用 |
| `memory_search()` | `ToolResponse` | Agent 工具搜索 | ✅ 可用 |
| `get_context()` | `list` | 获取模型上下文 | ⚠️ 需添加 client 方法 |
| `get_stats()` | `dict` | 获取会话统计 | ⚠️ 需添加 client 方法 |
| `lcm_describe()` | `str` | 描述摘要 | ❌ 服务器未实现 |
| `lcm_expand()` | `str` | 展开摘要 | ❌ 服务器未实现 |

---

## 🔧 完整示例

```python
import asyncio
from copaw.agents.memory.lcm_memory_manager import LCMMemoryManager
from agentscope.message import Msg


async def main():
    # 初始化
    mm = LCMMemoryManager(
        working_dir="./data",
        agent_id="default"
    )
    await mm.start()
    
    try:
        # 1. 创建对话
        messages = [
            Msg(name="user", content="什么是 Python？", role="user"),
            Msg(name="assistant", content="Python 是一种编程语言...", role="assistant"),
            Msg(name="user", content="Python 有什么特点？", role="user"),
            Msg(name="assistant", content="Python 特点包括简洁、易读...", role="assistant"),
        ]
        
        # 2. 压缩消息
        compact_result = await mm.compact_memory(messages)
        print(f"压缩结果：{compact_result}")
        
        # 3. 搜索内容
        search_results = await mm.lcm_grep("Python", limit=5)
        print(f"\n找到 {len(search_results)} 条匹配:")
        for item in search_results:
            print(f"  [{item['role']}] {item['snippet']}")
        
        # 4. 使用 ToolResponse 格式
        tool_result = await mm.memory_search("Python 特点", max_results=3)
        print(f"\nToolResponse 内容:\n{tool_result.content}")
        
    finally:
        await mm.close()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 📝 注意事项

1. **Summary 不直接返回**: LCM 的设计是将 summary 存储在内部数据库中，通过搜索和展开访问

2. **搜索 vs 向量检索**: LCM 使用 FTS5 全文搜索，不是向量相似度搜索
   - ✅ 精确匹配关键词
   - ❌ 不支持语义相似度（"ML" 不会匹配 "机器学习"）

3. **服务器限制**: 
   - `/describe` 和 `/expand` 端点尚未实现
   - 当前主要通过 `lcm_grep` 访问压缩内容

4. **异步调用**: 所有方法都是异步的，需要使用 `await`

---

## 🔮 未来改进

1. **实现 describe/expand**: 在服务器端实现完整的摘要描述和展开功能

2. **添加 summary_id 返回**: 在 compact result 中返回生成的 summary_id

3. **增强搜索**: 支持语义搜索和向量检索

4. **批量操作**: 支持批量获取多个摘要

---

## 📚 相关文档

- [LCM Server API](./README.md)
- [Search Features](./SEARCH_FEATURES.md)
- [Technical Details](./SEARCH_TECHNICAL_DETAILS.md)

---

**更新时间**: 2026-04-02  
**维护者**: CoPaw Team
