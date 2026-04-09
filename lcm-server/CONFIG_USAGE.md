# LCM 配置文件使用示例

## ✅ 配置已成功加载！

从健康检查响应可以看到，系统已从 `lcm-config.json` 文件读取配置：

```json
{
  "status": "healthy",
  "lcmAvailable": true,
  "config": {
    "databasePath": "data\\lcm.db",
    "contextThreshold": 0.75,
    "freshTailCount": 32,
    "provider": "openai",
    "model": "gpt-4",
    "autoCompact": true
  }
}
```

## 📁 文件结构

```
C:\workspace\CoPaw\lcm-server\
├── lcm-config.json           # 实际配置文件（已添加到 .gitignore）
├── lcm-config.example.json   # 示例配置文件（可提交）
├── index.js                  # 服务器主程序（支持配置文件）
├── lcm-adapter.js            # 依赖适配层
├── .gitignore                # 忽略敏感配置
└── CONFIG.md                 # 配置说明文档
```

## 🔐 安全性

- ✅ `lcm-config.json` 已添加到 `.gitignore`，不会被提交
- ✅ API 密钥等敏感信息存储在本地配置文件中
- ✅ 示例文件 `lcm-config.example.json` 可安全分享

## 🚀 Python 端使用

Python 的 `LCMMemoryManager` 也会自动查找并加载配置文件：

```python
from copaw.agents.memory import LCMMemoryManager

# 自动查找配置文件
manager = LCMMemoryManager(
    working_dir="C:/workspace/CoPaw/data",
    agent_id="default"
)

# 或指定配置文件路径
manager = LCMMemoryManager(
    working_dir="C:/workspace/CoPaw/data",
    agent_id="default",
    config_path="C:/workspace/CoPaw/lcm-server/lcm-config.json"
)

await manager.start()
```

## 📝 配置项优先级

1. **配置文件** (`lcm-config.json`) - 最高优先级
2. **环境变量** - 回退选项
3. **默认值** - 最后回退

## 🎯 下一步

1. 编辑 `lcm-config.json` 填入你的真实 API 密钥
2. 重启服务：`taskkill /F /IM node.exe && npm start`
3. 测试完整功能

## 📖 更多文档

查看 `CONFIG.md` 获取完整的配置项说明。
