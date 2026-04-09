# LCM Server - Lossless Context Management for CoPaw

这是一个薄的 HTTP 服务层，封装 `@martian-engineering/lossless-claw` npm 包，
为 CoPaw Python 后端提供无损上下文管理能力。

## 架构

```
┌─────────────────┐         HTTP API         ┌─────────────────┐
│   CoPaw (Python)│ ◄──────────────────────► │  LCM Server     │
│                 │                           │  (Node.js)      │
│ LCMMemoryManager│                           │      │          │
│                 │                           │      ▼          │
│   lcm_client.py │                           │ lossless-claw   │
└─────────────────┘                           │  (npm 包)       │
                                              │                 │
                                              │ - SQLite DB     │
                                              │ - DAG 压缩      │
                                              │ - 搜索工具      │
                                              └─────────────────┘
```

## 安装

```bash
cd lcm-server
npm install
```

## 启动服务

```bash
npm start
```

服务默认运行在 `http://localhost:3721`

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LCM_PORT` | 3721 | HTTP 服务端口 |
| `LCM_SERVER_URL` | http://localhost:3721 | Python 客户端连接地址 |
| `LCM_FRESH_TAIL_COUNT` | 32 | 保护最近消息数量 |
| `LCM_CONTEXT_THRESHOLD` | 0.75 | 触发压缩的上下文比例 |
| `LCM_MAX_CONTEXT_TOKENS` | 128000 | 最大上下文窗口 |

## API 端点

### 生命周期

- `GET /health` - 健康检查
- `POST /init` - 初始化引擎
- `POST /close` - 关闭引擎

### 消息操作

- `POST /ingest` - 摄入消息
- `POST /after-turn` - 每轮对话后处理（触发压缩检查）

### 上下文操作

- `GET /context/:sessionId` - 获取组装后的上下文
- `POST /compact` - 手动触发压缩

### LCM 工具

- `POST /grep` - 全文搜索
- `POST /describe` - 描述摘要/文件
- `POST /expand` - 展开摘要获取原始消息

## CoPaw 配置

在 CoPaw 配置文件中设置：

```json
{
  "running": {
    "memory_manager_backend": "lcm"
  }
}
```

或通过前端 UI 选择 "LCM (无损压缩)"。

## 与 ReMeLight 对比

| 特性 | ReMeLight | LCM |
|------|-----------|-----|
| 压缩方式 | 滑动窗口截断 | DAG 摘要 |
| 记忆恢复 | 向量相似度 | 摘要链追溯 |
| 大文件处理 | 截断 | 隔离存储 |
| 搜索能力 | 向量 + FTS | FTS5 + 展开 |
| 适用场景 | 通用对话 | 长期记忆 |

## 注意事项

1. 需要先启动 lcm-server，再启动 CoPaw
2. lossless-claw 包需要 Node.js 22+
3. 数据库文件存储在 `working_dir/lcm.db`