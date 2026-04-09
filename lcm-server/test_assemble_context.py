# -*- coding: utf-8 -*-
"""Test script to demonstrate assemble_context usage."""
import asyncio
import sys
sys.path.insert(0, "C:/workspace/CoPaw/src")

from copaw.agents.memory.lcm_memory_manager import LCMMemoryManager
from agentscope.message import Msg


async def test_assemble_context():
    """Test assemble_context functionality."""
    print("=" * 70)
    print("LCM assemble_context 使用示例")
    print("=" * 70)
    
    mm = LCMMemoryManager(
        working_dir="C:/workspace/CoPaw/lcm-server/data/test-assemble",
        agent_id="default"
    )
    await mm.start()
    
    try:
        # ========== 步骤 1: 先存储一些历史消息 ==========
        print("\n[步骤 1] 存储历史消息到 LCM...")
        history_messages = []
        for i in range(10):
            history_messages.extend([
                Msg(name="user", content=f"问题 {i}: 关于 Python 编程的问题", role="user"),
                Msg(name="assistant", content=f"答案 {i}: Python 编程相关解答", role="assistant"),
            ])
        
        await mm.compact_memory(history_messages)
        print(f"✅ 已存储 {len(history_messages)} 条历史消息")
        
        # ========== 步骤 2: 准备当前的 live messages ==========
        print("\n[步骤 2] 准备当前的 live messages...")
        live_messages = [
            Msg(name="user", content="请总结一下之前讨论的内容", role="user"),
        ]
        print(f"✅ Live messages: {len(live_messages)} 条")
        
        # ========== 步骤 3: 调用 assemble_context ==========
        print("\n[步骤 3] 调用 assemble_context 组装上下文...")
        
        # 通过 client 直接调用
        msg_dicts = mm._convert_messages(live_messages)
        result = await mm._client.assemble_context(
            session_id=mm.agent_id,
            messages=msg_dicts,
            token_budget=4000,  # 设置 token 预算
        )
        
        print(f"\n📊 组装结果:")
        print(f"   - 成功：{result.get('success')}")
        print(f"   - 消息数：{len(result.get('messages', []))}")
        print(f"   - 估计 tokens: {result.get('estimatedTokens', 0)}")
        print(f"   - 上下文项数：{result.get('contextItems', 0)}")
        
        # ========== 步骤 4: 查看组装后的消息 ==========
        print("\n[步骤 4] 查看组装后的消息内容...")
        messages = result.get('messages', [])
        print(f"\n总共 {len(messages)} 条消息:")
        for i, msg in enumerate(messages[:5], 1):  # 只显示前 5 条
            role = msg.get('role', 'unknown')
            content = msg.get('content', [])
            # 提取文本内容
            text = ""
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get('type') == 'text':
                        text = block.get('text', '')[:50]
                        break
            elif isinstance(content, str):
                text = content[:50]
            
            print(f"   {i}. [{role}] {text}...")
        
        if len(messages) > 5:
            print(f"   ... 还有 {len(messages) - 5} 条消息")
        
        # ========== 步骤 5: 不同 token_budget 的对比 ==========
        print("\n[步骤 5] 测试不同 token_budget 的影响...")
        
        for budget in [500, 2000, 8000]:
            result = await mm._client.assemble_context(
                session_id=mm.agent_id,
                messages=msg_dicts,
                token_budget=budget,
            )
            print(f"   Budget={budget:5d} → Messages={len(result.get('messages', [])):3d}, "
                  f"Tokens={result.get('estimatedTokens', 0):5d}")
        
        # ========== 总结 ==========
        print("\n" + "=" * 70)
        print("assemble_context 总结:")
        print("=" * 70)
        print("""
📌 作用:
   将 LCM 存储的压缩摘要 + 当前 live messages 组装成完整的上下文
   用于提供给 LLM 模型作为输入

📌 参数:
   - session_id: 会话 ID
   - messages: 当前的 live messages (最近的对话)
   - token_budget: token 预算上限 (可选)

📌 返回:
   - messages: 组装后的完整消息列表
   - estimatedTokens: 估计的 token 数量
   - contextItems: 使用的上下文项数

📌 使用场景:
   1. 在每次调用 LLM 前，获取完整上下文
   2. 结合历史摘要和最新对话
   3. 控制上下文长度不超过 token 限制

📌 工作流程:
   用户提问 → assemble_context → 获取完整上下文 → 调用 LLM → 返回响应
        """)
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ 错误：{e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await mm.close()
        print("\n✅ 已关闭内存管理器")


if __name__ == "__main__":
    asyncio.run(test_assemble_context())
