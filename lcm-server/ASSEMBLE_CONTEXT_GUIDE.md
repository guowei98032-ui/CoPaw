# assemble_context 使用指南

**日期**: 2026-04-02  
**版本**: LCM v0.5.3

---

## 📌 什么是 assemble_context？

**`assemble_context`** 是 LCM 的核心功能之一，用于**组装完整的对话上下文**供 LLM 模型使用。

### 核心作用

将以下内容组合成完整的上下文：
1. **压缩摘要** - 历史对话的 DAG 摘要
2. **Live Messages** - 当前最新的对话消息
3. **Token 控制** - 确保不超过 token 预算限制

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  压缩摘要存储   │     │  Live Messages   │     │  assemble_     │
│  (历史对话)     │  +  │  (最新对话)      │  →  │  context()     │
│                 │     │                  │     │                 │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                          │
                                                          ▼
                                                 ┌─────────────────┐
                                                 │  完整上下文     │
                                                 │  (给 LLM 输入)  │
                                                 └─────────────────┘
```

---

## 🔧 API 使用

### 方法签名

```python
async def assemble_context(
    self,
    session_id: str,
    messages: list[dict],
    token_budget: int = None,
) -> dict:
    """Assemble context for model input.

    Combines stored summaries with live messages, respecting token budget.

    Args:
        session_id: Session identifier.
        messages: Current live messages (recent turns).
        token_budget: Maximum tokens for assembled context.

    Returns:
        dict with:
            - messages: Assembled message list
            - estimatedTokens: Token count estimate
            - contextItems: Number of context items used
    """
```

### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `session_id` | `str` | ✅ | 会话 ID（通常是 agent_id） |
| `messages` | `list[dict]` | ✅ | 当前的 live messages（最近的对话） |
| `token_budget` | `int` | ❌ | Token 预算上限（默认由服务器配置） |

### 返回值

```python
{
    "success": True,
    "messages": [...],           # 组装后的完整消息列表
    "estimatedTokens": 3780,     # 估计的 token 数量
    "contextItems": 35,          # 使用的上下文项数
}
```

---

## 💡 使用示例

### 示例 1: 基本使用

```python
from copaw.agents.memory.lcm_memory_manager import LCMMemoryManager
from agentscope.message import Msg

# 初始化
mm = LCMMemoryManager(working_dir="./data", agent_id="default")
await mm.start()

try:
    # 1. 准备当前的 live messages（最近的对话）
    live_messages = [
        Msg(name="user", content="请总结之前的讨论", role="user"),
    ]
    
    # 2. 转换为 LCM 格式
    msg_dicts = mm._convert_messages(live_messages)
    
    # 3. 调用 assemble_context
    result = await mm._client.assemble_context(
        session_id=mm.agent_id,
        messages=msg_dicts,
        token_budget=4000,
    )
    
    # 4. 获取组装后的消息
    assembled_messages = result["messages"]
    print(f"组装了 {len(assembled_messages)} 条消息")
    print(f"估计 tokens: {result['estimatedTokens']}")
    
finally:
    await mm.close()
```

---

### 示例 2: 在 Agent 对话中使用

```python
async def agent_conversation(user_input: str):
    """完整的 Agent 对话流程"""
    
    # 1. 准备当前消息
    live_messages = [
        Msg(name="user", content=user_input, role="user"),
    ]
    
    # 2. 组装上下文（包含历史摘要 + 当前消息）
    msg_dicts = mm._convert_messages(live_messages)
    context_result = await mm._client.assemble_context(
        session_id=mm.agent_id,
        messages=msg_dicts,
        token_budget=8000,
    )
    
    # 3. 将组装后的上下文发送给 LLM
    llm_input = context_result["messages"]
    response = await llm.chat(llm_input)
    
    # 4. 存储新消息到 LCM
    new_messages = [
        Msg(name="user", content=user_input, role="user"),
        Msg(name="assistant", content=response, role="assistant"),
    ]
    await mm.compact_memory(new_messages)
    
    return response
```

---

### 示例 3: 不同 token_budget 的影响

```python
# 测试不同 token 预算
for budget in [500, 2000, 8000]:
    result = await mm._client.assemble_context(
        session_id=mm.agent_id,
        messages=msg_dicts,
        token_budget=budget,
    )
    print(f"Budget={budget:5d} → "
          f"Messages={len(result['messages']):3d}, "
          f"Tokens={result['estimatedTokens']:5d}")
```

**输出示例**:
```
Budget=  500 → Messages= 32, Tokens=  918
Budget= 2000 → Messages= 33, Tokens= 1872
Budget= 8000 → Messages= 39, Tokens= 7596
```

---

## 📊 工作流程

### 完整对话流程

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户提问                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. assemble_context                                            │
│     - 从 LCM 获取压缩摘要                                        │
│     - 添加 live messages                                        │
│     - 根据 token_budget 裁剪                                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. 调用 LLM                                                    │
│     输入：组装后的完整上下文                                     │
│     输出：AI 响应                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. compact_memory                                              │
│     - 存储新对话到 LCM                                           │
│     - 触发压缩（如需要）                                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🎯 使用场景

### 场景 1: 长对话历史管理

**问题**: 对话历史太长，超过 LLM 的 token 限制

**解决**:
```python
# 自动组装，只包含相关摘要和最新消息
result = await mm._client.assemble_context(
    session_id=mm.agent_id,
    messages=live_messages,
    token_budget=8000,  # 控制在 8000 tokens 内
)
```

---

### 场景 2: 多轮对话上下文

**问题**: 需要记住之前的对话内容

**解决**:
```python
# 每次对话前调用 assemble_context
# LCM 会自动包含历史摘要
context = await mm._client.assemble_context(...)
# 上下文包含：摘要 1 + 摘要 2 + ... + live messages
```

---

### 场景 3: Token 优化

**问题**: 需要精确控制 token 使用

**解决**:
```python
# 小预算：快速获取核心上下文
result = await mm._client.assemble_context(
    session_id=mm.agent_id,
    messages=live_messages,
    token_budget=1000,  # 严格限制
)

# 大预算：获取更完整的上下文
result = await mm._client.assemble_context(
    session_id=mm.agent_id,
    messages=live_messages,
    token_budget=16000,  # 宽松限制
)
```

---

## 📈 性能对比

### Token Budget vs 消息数量

| Token Budget | 消息数 | 估计 Tokens | 适用场景 |
|-------------|--------|-------------|---------|
| 500 | 32 | 918 | 快速摘要 |
| 2000 | 33 | 1872 | 简短对话 |
| 4000 | 35 | 3780 | 标准对话 |
| 8000 | 39 | 7596 | 长对话 |
| 16000 | 50+ | 15000+ | 超长对话 |

---

## ⚠️ 注意事项

### 1. Message 格式

`messages` 参数需要是 LCM/OpenClaw 格式：

```python
# ✅ 正确格式
msg_dicts = [
    {
        "role": "user",
        "content": [{"type": "text", "text": "Hello"}]
    },
]

# 使用 _convert_messages 转换
msg_dicts = mm._convert_messages(messages)
```

---

### 2. Token Budget 设置

```python
# 不设置：使用服务器默认值（通常 128000）
result = await mm._client.assemble_context(
    session_id=mm.agent_id,
    messages=msg_dicts,
)

# 设置：精确控制
result = await mm._client.assemble_context(
    session_id=mm.agent_id,
    messages=msg_dicts,
    token_budget=4000,  # 限制 4000 tokens
)
```

---

### 3. 错误处理

```python
try:
    result = await mm._client.assemble_context(...)
    if not result.get("success"):
        print(f"组装失败：{result.get('error')}")
        # 回退到原始 messages
        messages = live_messages
except Exception as e:
    print(f"组装异常：{e}")
    messages = live_messages
```

---

## 🔗 相关 API

| API | 用途 | 说明 |
|-----|------|------|
| `assemble_context()` | 组装上下文 | 本文档介绍 |
| `compact_memory()` | 压缩存储消息 | 存储对话到 LCM |
| `lcm_grep()` | 搜索历史 | 搜索压缩内容 |
| `after_turn()` | 每轮后处理 | 自动触发压缩检查 |

---

## 📝 完整代码示例

```python
import asyncio
from copaw.agents.memory.lcm_memory_manager import LCMMemoryManager
from agentscope.message import Msg


async def main():
    # 初始化
    mm = LCMMemoryManager(working_dir="./data", agent_id="default")
    await mm.start()
    
    try:
        # 1. 存储历史消息
        history = [
            Msg(name="user", content="问题 1", role="user"),
            Msg(name="assistant", content="答案 1", role="assistant"),
            # ... 更多历史消息
        ]
        await mm.compact_memory(history)
        
        # 2. 准备当前消息
        live_messages = [
            Msg(name="user", content="新问题", role="user"),
        ]
        
        # 3. 组装上下文
        msg_dicts = mm._convert_messages(live_messages)
        context = await mm._client.assemble_context(
            session_id=mm.agent_id,
            messages=msg_dicts,
            token_budget=4000,
        )
        
        # 4. 使用上下文调用 LLM
        # response = await llm.chat(context["messages"])
        
        print(f"组装完成：{len(context['messages'])} 条消息，"
              f"{context['estimatedTokens']} tokens")
        
    finally:
        await mm.close()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 📚 相关文档

- [LCM Server API](./README.md)
- [如何获取 Summary](./SUMMARY_QUICK_GUIDE.md)
- [Search Features](./SEARCH_FEATURES.md)

---

**测试脚本**: `test_assemble_context.py`  
**更新时间**: 2026-04-02  
**维护者**: CoPaw Team
