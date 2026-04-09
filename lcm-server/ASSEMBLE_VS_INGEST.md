# assemble_context vs ingest - 关系详解

**日期**: 2026-04-02  
**版本**: LCM v0.5.3

---

## 🎯 核心关系

```
┌─────────────────────────────────────────────────────────────────┐
│                     LCM 工作流程                                 │
└─────────────────────────────────────────────────────────────────┘

ingest (存储)                assemble_context (读取)
    ↓                             ↑
┌──────────┐              ┌──────────────┐
│ 写入数据库 │              │ 从数据库读取  │
│ 压缩消息   │   ──────→    │ 组装上下文    │
│ 生成摘要   │   存储/读取   │ 结合 live    │
└──────────┘              │ messages     │
                          └──────────────┘
```

**简单说**:
- **`ingest`** = **写入/存储**消息到 LCM 数据库
- **`assemble_context`** = **读取/组装**上下文用于 LLM 输入

---

## 📊 功能对比

| 特性 | ingest | assemble_context |
|------|--------|-----------------|
| **操作类型** | 写入 (Write) | 读取 (Read) |
| **用途** | 存储对话历史 | 获取模型输入 |
| **调用时机** | 对话后存储 | 对话前获取 |
| **返回** | 存储结果 | 组装的上下文 |
| **数据流向** | 客户端 → 数据库 | 数据库 → 客户端 |

---

## 🔧 API 对比

### ingest - 存储消息

```python
await mm._client.ingest(
    session_id=mm.agent_id,    # 会话 ID
    messages=msg_dicts,        # 要存储的消息
)
```

**返回**:
```python
{
    "success": True,
    "ingested": 4,             # 存储的消息数
    "results": [...]           # 每条消息的存储结果
}
```

---

### assemble_context - 组装上下文

```python
result = await mm._client.assemble_context(
    session_id=mm.agent_id,    # 会话 ID
    messages=live_messages,    # 当前 live messages
    token_budget=4000,         # token 预算
)
```

**返回**:
```python
{
    "success": True,
    "messages": [...],         # 组装后的完整上下文
    "estimatedTokens": 3912,   # 估计 token 数
    "contextItems": None,      # 上下文项数
}
```

---

## 💡 完整工作流程

### 典型对话流程

```
┌─────────────────────────────────────────────────────────────────┐
│ 第 1 轮对话                                                       │
├─────────────────────────────────────────────────────────────────┤
│ 1. 用户提问："你好"                                              │
│ 2. assemble_context → 获取上下文（空）                          │
│ 3. 调用 LLM → "你好！有什么可以帮助你的？"                       │
│ 4. ingest → 存储对话到 LCM                                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 第 2 轮对话                                                       │
├─────────────────────────────────────────────────────────────────┤
│ 1. 用户提问："Python 是什么？"                                   │
│ 2. assemble_context → 获取上下文（包含第 1 轮摘要）               │
│ 3. 调用 LLM → "Python 是一种编程语言..."                         │
│ 4. ingest → 存储对话到 LCM                                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 第 N 轮对话                                                       │
├─────────────────────────────────────────────────────────────────┤
│ 1. 用户提问："总结一下"                                          │
│ 2. assemble_context → 获取上下文（包含所有历史摘要）            │
│ 3. 调用 LLM → 生成总结                                           │
│ 4. ingest → 存储对话到 LCM                                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📝 代码示例

### 完整对话管理器

```python
class DialogueManager:
    def __init__(self, mm):
        self.mm = mm
        self.history = []
    
    async def chat(self, user_input: str):
        """完整的对话流程"""
        
        # ========== 步骤 1: 准备当前消息 ==========
        live_messages = [
            Msg(name="user", content=user_input, role="user"),
        ]
        
        # ========== 步骤 2: assemble_context (读取历史) ==========
        msg_dicts = self.mm._convert_messages(live_messages)
        context_result = await self.mm._client.assemble_context(
            session_id=self.mm.agent_id,
            messages=msg_dicts,
            token_budget=8000,
        )
        
        # 获取组装后的上下文
        assembled_messages = context_result["messages"]
        print(f"📖 读取上下文：{len(assembled_messages)} 条消息")
        
        # ========== 步骤 3: 调用 LLM ==========
        response = await self.llm.chat(assembled_messages)
        print(f"🤖 LLM 响应：{response[:50]}...")
        
        # ========== 步骤 4: ingest (存储新对话) ==========
        new_messages = [
            Msg(name="user", content=user_input, role="user"),
            Msg(name="assistant", content=response, role="assistant"),
        ]
        new_msg_dicts = self.mm._convert_messages(new_messages)
        
        ingest_result = await self.mm._client.ingest(
            session_id=self.mm.agent_id,
            messages=new_msg_dicts,
        )
        print(f"💾 存储对话：{ingest_result['ingested']} 条消息")
        
        # ========== 步骤 5: 触发压缩（可选） ==========
        await self.mm.compact_memory(new_messages)
        
        return response


# 使用
mm = LCMMemoryManager(working_dir="./data", agent_id="default")
await mm.start()

manager = DialogueManager(mm)

# 第 1 轮
response1 = await manager.chat("你好")
# 输出:
# 📖 读取上下文：1 条消息
# 🤖 LLM 响应：你好！有什么可以帮助你的？...
# 💾 存储对话：2 条消息

# 第 2 轮
response2 = await manager.chat("Python 是什么？")
# 输出:
# 📖 读取上下文：3 条消息（包含第 1 轮摘要）
# 🤖 LLM 响应：Python 是一种高级编程语言...
# 💾 存储对话：2 条消息

await mm.close()
```

---

## 🔄 数据流向图

```
┌──────────────────────────────────────────────────────────────────┐
│                         用户                                      │
│                    "Python 是什么？"                               │
└──────────────────────────────────────────────────────────────────┘
                                │
                                │ 1. 提问
                                ↓
┌──────────────────────────────────────────────────────────────────┐
│                    assemble_context                              │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 从数据库读取：                                              │ │
│  │ - 历史摘要 1: "用户问候..."                                 │ │
│  │ - 历史摘要 2: "Python 基础..."                              │ │
│  │ - Live messages: ["Python 是什么？"]                        │ │
│  └────────────────────────────────────────────────────────────┘ │
│                      ↓                                          │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 组装后的上下文：                                            │ │
│  │ [<summary>...</summary>, <summary>...</summary>,           │ │
│  │  {"role": "user", "content": "Python 是什么？"}]           │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
                                │
                                │ 2. 完整上下文
                                ↓
┌──────────────────────────────────────────────────────────────────┐
│                         LLM                                      │
│  输入：组装后的上下文                                            │
│  输出："Python 是一种高级编程语言，由 Guido van Rossum 发明..."   │
└──────────────────────────────────────────────────────────────────┘
                                │
                                │ 3. 响应
                                ↓
┌──────────────────────────────────────────────────────────────────┐
│                         ingest                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 存储到数据库：                                              │ │
│  │ - 用户消息："Python 是什么？"                               │ │
│  │ - AI 响应："Python 是一种高级编程语言..."                    │ │
│  │ - 触发压缩检查                                              │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
                                │
                                │ 4. 存储完成
                                ↓
┌──────────────────────────────────────────────────────────────────┐
│                      SQLite 数据库                               │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ messages 表：                                               │ │
│  │ - msg_001: "你好"                                          │ │
│  │ - msg_002: "你好！有什么可以帮助你的？"                     │ │
│  │ - msg_003: "Python 是什么？"                                │ │
│  │ - msg_004: "Python 是一种高级编程语言..."                   │ │
│  │                                                             │ │
│  │ summaries 表：                                              │ │
│  │ - sum_001: <summary>用户问候对话</summary>                 │ │
│  │ - sum_002: <summary>Python 基础讨论</summary>               │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🎯 使用场景对比

### ingest 的使用场景

```python
# ✅ 场景 1: 存储对话历史
await mm._client.ingest(session_id, new_messages)

# ✅ 场景 2: 导入历史数据
old_messages = load_from_file("history.json")
await mm._client.ingest(session_id, old_messages)

# ✅ 场景 3: 存储工具调用结果
tool_result = {"role": "tool", "content": "执行结果..."}
await mm._client.ingest(session_id, [tool_result])
```

---

### assemble_context 的使用场景

```python
# ✅ 场景 1: 调用 LLM 前获取上下文
context = await mm._client.assemble_context(...)
response = await llm.chat(context["messages"])

# ✅ 场景 2: 检查当前上下文状态
context = await mm._client.assemble_context(
    session_id, 
    messages=[],  # 无 live messages
    token_budget=1000
)
print(f"当前上下文：{context['estimatedTokens']} tokens")

# ✅ 场景 3: 多轮对话中保持上下文
for user_input in conversation:
    context = await mm._client.assemble_context(...)
    response = await llm.chat(context["messages"])
    await mm._client.ingest(session_id, new_messages)
```

---

## 📊 性能对比

| 操作 | 响应时间 | 数据库操作 | 网络请求 |
|------|---------|-----------|---------|
| `ingest` | ~50ms | INSERT | 1 POST |
| `assemble_context` | ~100ms | SELECT | 1 POST |

---

## ⚠️ 常见错误

### 错误 1: 只 ingest 不 assemble

```python
# ❌ 错误：只存储，不读取
await mm._client.ingest(session_id, messages)
# LLM 收不到历史上下文！

# ✅ 正确：先读取，再存储
context = await mm._client.assemble_context(...)  # 读取
response = await llm.chat(context["messages"])    # 使用
await mm._client.ingest(session_id, new_messages) # 存储
```

---

### 错误 2: 只 assemble 不 ingest

```python
# ❌ 错误：只读取，不存储
context = await mm._client.assemble_context(...)
response = await llm.chat(context["messages"])
# 新对话没有保存，下次 assemble 看不到！

# ✅ 正确：读取 + 存储
context = await mm._client.assemble_context(...)  # 读取
response = await llm.chat(context["messages"])    # 使用
await mm._client.ingest(session_id, new_messages) # 存储
```

---

### 错误 3: 顺序错误

```python
# ❌ 错误：先存储再读取（会包含当前消息）
await mm._client.ingest(session_id, current_messages)
context = await mm._client.assemble_context(...)
# 当前消息被重复包含！

# ✅ 正确：先读取再存储
context = await mm._client.assemble_context(...)  # 读取历史
await mm._client.ingest(session_id, current_messages) # 存储当前
```

---

## 🔗 与其他 API 的关系

```
┌─────────────────────────────────────────────────────────────────┐
│                     LCM API 生态系统                             │
└─────────────────────────────────────────────────────────────────┘

ingest ──→ 存储消息 ──→ compact_memory ──→ 生成摘要
   │                                          │
   │                                          ↓
   │                                   assemble_context
   │                                          │
   │                                          ↓
   └──────────────← 读取上下文 ←──────────────┘
                        │
                        ↓
                   lcm_grep (搜索)
                   memory_search (搜索)
                   get_stats (统计)
```

---

## 📋 总结

### ingest

- **作用**: 写入/存储消息到 LCM 数据库
- **时机**: 对话完成后
- **返回**: 存储结果（消息数等）
- **类比**: `INSERT INTO database`

### assemble_context

- **作用**: 读取/组装上下文用于 LLM 输入
- **时机**: 调用 LLM 前
- **返回**: 组装的消息列表（摘要 + live）
- **类比**: `SELECT FROM database + 组装`

### 关系

```
ingest (写) → 数据库 → assemble_context (读)
                ↑
                │
           compact_memory (压缩)
```

**完整流程**:
```
用户提问 
  → assemble_context (读取历史) 
  → LLM (生成响应) 
  → ingest (存储新对话)
  → compact_memory (压缩摘要)
  → 循环...
```

---

## 📚 相关文档

- [ASSEMBLE_CONTEXT_GUIDE.md](./ASSEMBLE_CONTEXT_GUIDE.md)
- [ASSEMBLE_CONTEXT_RETURN_FORMAT.md](./ASSEMBLE_CONTEXT_RETURN_FORMAT.md)
- [SUMMARY_QUICK_GUIDE.md](./SUMMARY_QUICK_GUIDE.md)

---

**测试脚本**: `test_assemble_context.py`  
**更新时间**: 2026-04-02  
**维护者**: CoPaw Team
