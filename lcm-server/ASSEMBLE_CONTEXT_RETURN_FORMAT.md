# assemble_context 返回格式详解

**测试日期**: 2026-04-02

---

## 📋 完整返回结构

```python
result = await mm._client.assemble_context(
    session_id=mm.agent_id,
    messages=msg_dicts,
    token_budget=4000,
)
```

### 返回类型：`dict`

```python
{
    "success": True,                    # bool - 请求是否成功
    "messages": [...],                  # list - 组装后的消息数组
    "estimatedTokens": 3912,            # int - 估计的 token 数量
    "contextItems": None,               # int|null - 使用的上下文项数
}
```

---

## 🔍 字段详解

### 1️⃣ `success` (bool)

**说明**: 请求是否成功

**示例**:
```python
result["success"]  # True 或 False
```

---

### 2️⃣ `messages` (list)

**说明**: 组装后的完整消息列表（包含摘要 + live messages）

**类型**: `list[dict]`

**每条消息的结构**:
```python
{
    "role": "user",              # str - "user" | "assistant" | "system"
    "content": [...],            # list | str - 消息内容
    # 可选字段:
    "id": "msg_xxxxx",           # str - 消息 ID
    "name": "用户名",             # str - 显示名称
}
```

**content 字段的三种格式**:

#### 格式 1: 数组格式（标准）
```python
{
    "role": "user",
    "content": [
        {"type": "text", "text": "Hello, Python 编程问题"}
    ]
}
```

#### 格式 2: 字符串格式
```python
{
    "role": "assistant",
    "content": "Python 是一种高级编程语言..."
}
```

#### 格式 3: 摘要格式（XML）
```python
{
    "role": "user",
    "content": """
<summary id="sum_88d182bccc1b250a" kind="condensed" depth="1" 
         descendant_count="8" earliest_at="2026-04-02T13:35:33" 
         latest_at="2026-04-02T13:56:22">
  <parents>
    <summary_ref id="sum_fe0a4a3b2ecba82b" />
    <summary_ref id="sum_9a109fb36384307e" />
  </parents>
  <content>
[2026-04-02 13:35 GMT+8 - 2026-04-02 13:39 GMT+8]
用户询问了 Python 编程相关问题...
  </content>
</summary>
"""
}
```

---

### 3️⃣ `estimatedTokens` (int)

**说明**: 估计的 token 数量

**示例**:
```python
result["estimatedTokens"]  # 3912
```

---

### 4️⃣ `contextItems` (int | None)

**说明**: 使用的上下文项数（摘要数 + 消息数）

**示例**:
```python
result["contextItems"]  # 35 或 None
```

---

## 📊 实际测试数据

### 测试结果

```python
{
    "success": True,
    "messages": [34 条消息],
    "estimatedTokens": 3912,
    "contextItems": None,
}
```

### 消息类型统计

| 类型 | 数量 | 说明 |
|------|------|------|
| 摘要消息 (summary) | 2 条 | XML 格式的压缩摘要 |
| 普通消息 | 32 条 | 标准对话消息 |
| **总计** | **34 条** | |

---

## 💡 使用示例

### 示例 1: 访问返回数据

```python
result = await mm._client.assemble_context(...)

# 1. 检查是否成功
if result.get("success"):
    # 2. 获取消息列表
    messages = result["messages"]
    print(f"共 {len(messages)} 条消息")
    
    # 3. 获取 token 数
    tokens = result["estimatedTokens"]
    print(f"估计 {tokens} tokens")
    
    # 4. 遍历消息
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        
        # 提取文本内容
        if isinstance(content, list):
            text = content[0].get("text", "")
        else:
            text = content
        
        print(f"[{role}] {text[:50]}...")
```

---

### 示例 2: 区分摘要和普通消息

```python
messages = result["messages"]

summary_count = 0
regular_count = 0

for msg in messages:
    content = msg.get("content", "")
    
    # 检查是否是摘要消息
    if isinstance(content, str) and "<summary" in content:
        summary_count += 1
        print(f"📝 摘要消息：{content[:100]}...")
    else:
        regular_count += 1
        # 提取普通消息文本
        if isinstance(content, list):
            text = content[0].get("text", "")
        else:
            text = content
        print(f"💬 普通消息 [{msg.get('role')}]: {text[:50]}...")

print(f"摘要：{summary_count} 条，普通：{regular_count} 条")
```

---

### 示例 3: 提取纯文本内容

```python
def extract_text(msg):
    """从消息中提取纯文本"""
    content = msg.get("content", "")
    
    if isinstance(content, list):
        # 数组格式
        texts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(block.get("text", ""))
        return "\n".join(texts)
    elif isinstance(content, str):
        # 字符串或 XML 格式
        return content
    else:
        return str(content)

# 使用
messages = result["messages"]
for msg in messages[:5]:  # 前 5 条
    text = extract_text(msg)
    print(f"[{msg.get('role')}] {text[:100]}...")
```

---

## 📈 不同 token_budget 对比

| Token Budget | Messages | Estimated Tokens | Context Items |
|-------------|----------|------------------|---------------|
| 500 | 32 | 1904 | 0 |
| 2000 | 32 | 1904 | 0 |
| 4000 | 34 | 3912 | 0 |
| 8000 | 35 | 4966 | 0 |

---

## ⚠️ 注意事项

### 1. 消息格式可能不同

```python
# 可能是数组格式
{"role": "user", "content": [{"type": "text", "text": "..."}]}

# 也可能是字符串格式
{"role": "user", "content": "..."}

# 也可能是摘要 XML
{"role": "user", "content": "<summary>...</summary>"}
```

**建议**: 总是检查 `content` 的类型

---

### 2. 安全访问字段

```python
# ✅ 推荐：使用 .get() 方法
success = result.get("success", False)
messages = result.get("messages", [])
tokens = result.get("estimatedTokens", 0)

# ❌ 避免：直接访问可能抛出 KeyError
success = result["success"]  # 如果不存在会报错
```

---

### 3. 错误处理

```python
try:
    result = await mm._client.assemble_context(...)
    
    if not result.get("success"):
        print(f"组装失败：{result.get('error')}")
        messages = live_messages  # 回退
    else:
        messages = result["messages"]
        
except Exception as e:
    print(f"组装异常：{e}")
    messages = live_messages  # 回退到原始消息
```

---

## 📚 相关文档

- [ASSEMBLE_CONTEXT_GUIDE.md](./ASSEMBLE_CONTEXT_GUIDE.md) - 完整使用指南
- [test_assemble_return_format.py](./test_assemble_return_format.py) - 测试脚本

---

**更新时间**: 2026-04-02  
**维护者**: CoPaw Team
