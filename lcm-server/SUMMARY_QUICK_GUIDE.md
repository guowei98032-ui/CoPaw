# 调用 compact_memory 后如何获取 Summary

## 🎯 快速回答

**`compact_memory()` 不直接返回 summary 内容**，而是返回状态字符串：

```python
result = await mm.compact_memory(messages)
print(result)  # '[LCM Compacted: compacted]' 或 ''
```

---

## ✅ 推荐的获取方式

### 1️⃣ 使用 `lcm_grep()` 搜索（最常用）

```python
# 搜索关键词
results = await mm.lcm_grep("Python", limit=10)

for item in results:
    print(f"[{item['role']}] {item['snippet']}")
    print(f"消息 ID: {item['messageId']}")
```

**返回**:
```python
[
    {'messageId': 5710, 'role': 'user', 'snippet': 'Python...', ...},
    {'messageId': 5711, 'role': 'assistant', 'snippet': 'Python...', ...},
]
```

---

### 2️⃣ 使用 `memory_search()`（ToolResponse 格式）

```python
result = await mm.memory_search("Python 特点", max_results=5)

print(result.content)     # 可读的搜索结果
print(result.metadata)    # 元数据（总匹配数等）
```

**返回**:
```python
ToolResponse(
    content="Found 2 matches:\n  - [user] 特点\n  - [assistant] 特点",
    metadata={"total_matches": 2, "query": "Python 特点"}
)
```

---

### 3️⃣ 使用 `get_stats()` 查看统计

```python
stats = await mm._client.get_stats(mm.agent_id)
print(stats)  # {'sessionId': 'default', 'active': True, ...}
```

---

## 📊 方法对比

| 方法 | 用途 | 状态 |
|------|------|------|
| `compact_memory()` | 确认压缩状态 | ✅ 返回值是状态字符串 |
| `lcm_grep()` | 搜索压缩内容 | ✅ **推荐** |
| `memory_search()` | Agent 工具搜索 | ✅ **推荐** |
| `get_stats()` | 查看会话统计 | ✅ 已添加 |
| `lcm_describe()` | 描述摘要 | ❌ 服务器未实现 |
| `lcm_expand()` | 展开摘要 | ❌ 服务器未实现 |

---

## 💡 完整示例

```python
from copaw.agents.memory.lcm_memory_manager import LCMMemoryManager
from agentscope.message import Msg

mm = LCMMemoryManager(working_dir="./data", agent_id="default")
await mm.start()

try:
    # 1. 压缩消息
    messages = [
        Msg(name="user", content="Python 是什么？", role="user"),
        Msg(name="assistant", content="Python 是一种编程语言", role="assistant"),
    ]
    status = await mm.compact_memory(messages)
    print(f"压缩状态：{status}")
    
    # 2. 搜索内容
    results = await mm.lcm_grep("Python", limit=5)
    for item in results:
        print(f"[{item['role']}] {item['snippet']}")
    
    # 3. 或使用 ToolResponse
    search = await mm.memory_search("Python", max_results=3)
    print(search.content)
    
finally:
    await mm.close()
```

---

## 📝 注意事项

1. **LCM 的 summary 存储在内部数据库**，通过搜索访问，不直接返回
2. **使用 FTS5 全文搜索**，不是向量相似度搜索
3. **所有方法都是异步的**，需要使用 `await`

---

**详细文档**: [HOW_TO_GET_SUMMARY.md](./HOW_TO_GET_SUMMARY.md)  
**示例代码**: [example_get_summary.py](./example_get_summary.py)
