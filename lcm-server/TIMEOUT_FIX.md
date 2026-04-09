# LCM 超时问题解决方案

## 📋 问题现象

服务器日志显示：
```
[lcm] summarizer timed out; provider=openai; model=qwen3.5-plus; timeout=60000ms
[DEBUG createCompleteFn] Response status: 200
```

**矛盾点**：响应状态是 200（成功），但提示超时。

---

## 🔍 问题原因

### 1. 实际发生了什么

1. **请求发送**：LCM 向阿里云 DashScope 发送摘要生成请求
2. **模型处理**：qwen3.5-plus 开始处理大量文本（100 条消息）
3. **超时触发**：60 秒后，`lossless-claw` 判定超时
4. **响应到达**：实际上阿里云在 60+ 秒后返回了成功响应（HTTP 200）

### 2. 为什么需要更长时间

- **大量文本**：测试发送了 100 条消息，每条消息包含大量文本
- **摘要任务复杂**：需要从大量对话中提取关键信息
- **模型响应时间**：qwen3.5-plus 处理长文本需要较长时间
- **网络延迟**：国内 API 虽然快，但大模型推理仍需时间

---

## ✅ 解决方案

### 修改 1: 增加超时时间

**文件**: `node_modules/@martian-engineering/lossless-claw/src/summarize.ts`

**修改内容**:
```typescript
// 原来：60 秒
const SUMMARIZER_TIMEOUT_MS = 60_000;

// 修改后：180 秒（3 分钟）
const SUMMARIZER_TIMEOUT_MS = 180_000;
```

### 修改 2: 优化测试数据（可选）

如果不想增加超时时间，可以：
1. 减少测试消息数量（从 100 条减少到 20-30 条）
2. 减少每条消息的长度
3. 使用更快的模型

---

## 📊 不同场景的超时建议

| 场景 | 消息数量 | 建议超时 | 说明 |
|------|---------|---------|------|
| 日常对话 | 10-20 条 | 60 秒 | 普通对话摘要 |
| 中等对话 | 20-50 条 | 120 秒 | 技术讨论摘要 |
| 长对话 | 50-100 条 | 180 秒 | 复杂项目讨论 |
| 超长对话 | 100+ 条 | 300 秒 | 多日项目总结 |

---

## 🚀 使用方法

### 重启服务器
```bash
cd C:\workspace\CoPaw\lcm-server
restart-server.bat
```

### 验证配置
```bash
curl http://localhost:3721/health
```

### 运行测试
```bash
python test_force_compact.py
```

---

## 📝 预期日志

### 修改前（超时）
```
[lcm] summarizer timed out; provider=openai; model=qwen3.5-plus; timeout=60000ms
[lcm] summarizer timed out; provider=openai; model=qwen3.5-plus; source=fallback
[DEBUG createCompleteFn] Response status: 200  ← 实际成功了但已超时
```

### 修改后（正常）
```
[DEBUG createCompleteFn] Request: {
  "url": "https://coding.dashscope.aliyuncs.com/v1/chat/completions",
  "model": "qwen3.5-plus",
  "messagesCount": 2,
  "maxTokens": 2400
}
[DEBUG createCompleteFn] Response status: 200  ← 在超时内完成
✅✅✅ COMPACTION SUCCESSFUL! ✅✅✅
```

---

## ⚠️ 注意事项

### 1. 超时不是错误

- 60 秒超时是 `lossless-claw` 的保护机制
- 防止 API 挂起导致系统阻塞
- 对于大模型和长文本，需要更长时间是正常的

### 2. 超时时间设置

**不要设置太短**：
- < 30 秒：大多数摘要会超时
- 30-60 秒：短对话可以，长对话会超时

**不要设置太长**：
- > 300 秒：API 真的挂起时会影响系统
- 180 秒：平衡点，适合大多数场景

### 3. 其他优化方法

如果 180 秒还是不够：

**方法 A**: 减少 token 预算
```python
config = {
    "maxContextTokens": 50000,  # 从 128000 减少
}
```

**方法 B**: 使用更快的模型
```json
{
  "summary": {
    "model": "qwen-turbo",  # 更快的模型
    "baseUrl": "https://dashscope.aliyuncs.com/api/v1"
  }
}
```

**方法 C**: 分批压缩
- 不要一次性压缩 100 条消息
- 让 LCM 自动增量压缩

---

## 🎯 最佳实践

### 1. 生产环境配置

```json
{
  "compaction": {
    "contextThreshold": 0.75,
    "freshTailCount": 32,
    "maxContextTokens": 128000,
    "autoCompact": true
  },
  "summary": {
    "provider": "openai",
    "model": "qwen3.5-plus",
    "apiKey": "...",
    "baseUrl": "https://coding.dashscope.aliyuncs.com/v1",
    "timeout": 180000
  }
}
```

### 2. 监控超时

在日志中查找：
```bash
findstr /C:"timed out" server_log.txt
```

如果频繁超时：
- 增加超时时间
- 减少消息数量
- 优化模型选择

### 3. 性能调优

- **freshTailCount**: 保护最近消息不被压缩（默认 32）
- **contextThreshold**: 触发压缩的阈值（默认 0.75）
- **maxContextTokens**: 最大上下文 token 数（默认 128000）

---

## 📞 故障排查

### 问题 1: 仍然超时

**检查**：
1. 消息数量是否太多？
2. 模型是否太慢？
3. 网络是否稳定？

**解决**：
```bash
# 增加超时到 300 秒
# 修改 summarize.ts: const SUMMARIZER_TIMEOUT_MS = 300_000;
```

### 问题 2: API 返回错误

**检查**：
```bash
findstr /C:"401" /C:"403" /C:"500" server_log.txt
```

**解决**：
- 401: API 密钥错误
- 403: 配额不足
- 500: API 服务问题

### 问题 3: 压缩不触发

**检查**：
```bash
findstr /C:"below threshold" server_log.txt
```

**解决**：
- 降低 `contextThreshold`（从 0.75 到 0.5）
- 增加消息数量

---

**修改时间**: 2026-04-03  
**修改者**: 大呙（大 guowei）  
**超时设置**: 60 秒 → 180 秒
