# LCM 搜索技术详解

## ✅ 结论

**LCM 没有使用向量搜索 (Vector Search)**，而是使用 **SQLite FTS5 全文搜索引擎**。

## 🔍 技术实现

### LCM 的搜索架构

```
┌─────────────────────────────────────────────────────┐
│                  lcm_grep 工具                       │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│              RetrievalEngine.grep()                  │
│  - 支持 mode: "regex" | "full_text"                 │
│  - 支持 scope: "messages" | "summaries" | "both"    │
└─────────────────┬───────────────────────────────────┘
                  │
        ┌─────────┴──────────┐
        │                    │
        ▼                    ▼
┌──────────────┐    ┌──────────────────┐
│ searchRegex  │    │ searchFullText   │
│ (正则匹配)    │    │ (FTS5 全文搜索)  │
└──────────────┘    └─────────┬────────┘
                              │
                    ┌─────────┴──────────┐
                    │                    │
                    ▼                    ▼
           ┌─────────────┐    ┌──────────────────┐
           │ FTS5 可用？  │    │ LIKE 回退方案    │
           │ MATCH 查询  │    │ (CJK 文本/无 FTS5)│
           └─────────────┘    └──────────────────┘
```

### 代码实现（来自 retrieval.ts）

```typescript
async grep(input: GrepInput): Promise<GrepResult> {
  const { query, mode, scope, conversationId } = input;
  
  if (mode === "full_text") {
    // 检测是否包含 CJK 字符
    if (containsCjk(query)) {
      return this.searchLike(...);  // 使用 LIKE 回退
    }
    
    if (this.fts5Available) {
      try {
        return this.searchFullText(...);  // FTS5 MATCH 查询
      } catch {
        return this.searchLike(...);  // FTS5 失败回退
      }
    }
    return this.searchLike(...);
  }
  
  return this.searchRegex(...);  // 正则表达式搜索
}
```

## 📊 三种搜索模式对比

| 特性 | 正则搜索 | FTS5 全文搜索 | LIKE 回退 |
|------|---------|-------------|----------|
| **实现** | JavaScript RegExp | SQLite FTS5 虚拟表 | SQL LIKE |
| **速度** | 慢（全表扫描） | 快（倒排索引） | 慢（全表扫描） |
| **准确性** | 精确匹配 | 词干提取、同义词 | 子串匹配 |
| **支持语言** | 所有 | 西方语言较好，CJK 有限 | 所有 |
| **使用场景** | 精确模式匹配 | 一般文本搜索 | CJK 文本/无 FTS5 |

## 🗄️ 数据库结构

### FTS5 虚拟表（可选）

```sql
-- 主表
CREATE TABLE messages (
  message_id INTEGER PRIMARY KEY,
  content TEXT NOT NULL,
  ...
);

-- FTS5 虚拟表（全文搜索索引）
CREATE VIRTUAL TABLE messages_fts USING fts5(
  content,
  tokenize='unicode61'
);

-- 触发器自动同步
CREATE TRIGGER messages_ai AFTER INSERT ON messages BEGIN
  INSERT INTO messages_fts(rowid, content) 
  VALUES (new.message_id, new.content);
END;
```

### 搜索查询示例

```sql
-- FTS5 MATCH 查询（快速，使用索引）
SELECT m.* FROM messages m
JOIN messages_fts fts ON m.message_id = fts.rowid
WHERE messages_fts MATCH '机器学习'
LIMIT 50;

-- LIKE 回退（慢，全表扫描）
SELECT * FROM messages
WHERE content LIKE '%机器学习%'
LIMIT 50;
```

## ❌ 不是向量搜索

### 向量搜索的特点（LCM 没有）

```
向量搜索需要：
1. Embedding 模型 → 将文本转换为向量
2. 向量索引 → HNSW、IVF 等
3. 相似度计算 → 余弦相似度、欧氏距离
4. 向量数据库 → Pinecone、Milvus、pgvector 等

示例查询：
"找到与'机器学习'语义最相似的 5 条消息"
→ 计算 query_vector 与所有消息向量的相似度
→ 返回 top 5
```

### LCM 的搜索（全文搜索）

```
全文搜索需要：
1. 文本索引 → FTS5 倒排索引
2. 关键词匹配 → 词项匹配
3. 标准数据库 → SQLite

示例查询：
"找到包含'机器学习'这个词的消息"
→ 查找索引中包含该词的文档
→ 返回匹配结果
```

## 💡 为什么容易混淆？

### 1. 都有"语义"的感觉

- **向量搜索**: 真的理解语义（"ML" ≈ "机器学习"）
- **FTS5**: 只是看起来像（通过词干提取、同义词表）

### 2. 配置中都有 embedding

- **ReMeLight**: 实际使用 embedding 进行向量搜索
- **LCM**: embedding 配置仅用于接口兼容，**不实际使用**

### 3. 都能"搜索历史"

- **向量搜索**: 基于含义搜索
- **全文搜索**: 基于关键词搜索

## 🎯 实际效果对比

### 搜索 "机器学习"

| 消息内容 | 向量搜索 | LCM (FTS5) |
|---------|---------|-----------|
| "我想学习机器学习" | ✅ 匹配 | ✅ 匹配 |
| "机器学习的优势" | ✅ 匹配 | ✅ 匹配 |
| "ML 技术很强大" | ✅ 匹配 | ❌ 不匹配 |
| "神经网络训练" | ✅ 匹配 | ❌ 不匹配 |
| "AI 模型优化" | ✅ 匹配 | ❌ 不匹配 |

### 搜索 "python"

| 消息内容 | 向量搜索 | LCM (FTS5) |
|---------|---------|-----------|
| "Python 编程" | ✅ 匹配 | ✅ 匹配（大小写不敏感） |
| "python 脚本" | ✅ 匹配 | ✅ 匹配 |
| "py 语言" | ✅ 匹配 | ❌ 不匹配 |

## 📝 总结

| 特性 | LCM | ReMeLight |
|------|-----|-----------|
| **搜索技术** | SQLite FTS5 | 向量搜索 + FTS |
| **需要 Embedding** | ❌ 否 | ✅ 是 |
| **语义理解** | ❌ 否 | ✅ 是 |
| **关键词搜索** | ✅ 是 | ✅ 是 |
| **正则搜索** | ✅ 是 | ❌ 否 |
| **搜索速度** | 快（有索引） | 快（向量索引） |
| **数据库** | SQLite | SQLite + 向量索引 |

## 🔧 Embedding 配置的作用

虽然 LCM 不使用 embedding 进行搜索，但配置中仍然保留：

1. **接口兼容性** - `get_embedding_config()` 方法需要返回有效值
2. **未来扩展** - 预留添加语义搜索的可能性
3. **配置一致性** - 与 ReMeLight 保持相同的配置结构

```json
{
  "embedding": {
    // LCM 不使用这些配置进行搜索
    // 但保留以便与 ReMeLight 兼容
    "backend": "openai",
    "apiKey": "sk-xxx",
    "modelName": "text-embedding-3-small"
  }
}
```
