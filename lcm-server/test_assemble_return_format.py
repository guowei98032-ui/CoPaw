# -*- coding: utf-8 -*-
"""详细展示 assemble_context 的返回格式."""
import asyncio
import sys
import json
sys.path.insert(0, "C:/workspace/CoPaw/src")

from copaw.agents.memory.lcm_memory_manager import LCMMemoryManager
from agentscope.message import Msg


async def test_assemble_context_return_format():
    """详细测试 assemble_context 返回格式."""
    print("=" * 80)
    print("assemble_context 返回格式详解")
    print("=" * 80)
    
    mm = LCMMemoryManager(
        working_dir="C:/workspace/CoPaw/lcm-server/data/test-return-format",
        agent_id="default"
    )
    await mm.start()
    
    try:
        # ========== 准备测试数据 ==========
        print("\n[准备] 存储测试数据...")
        history_messages = []
        for i in range(5):
            history_messages.extend([
                Msg(name="user", content=f"问题 {i}: Python 编程相关问题", role="user"),
                Msg(name="assistant", content=f"答案 {i}: Python 编程相关解答，包含详细内容", role="assistant"),
            ])
        
        await mm.compact_memory(history_messages)
        print(f"✅ 已存储 {len(history_messages)} 条历史消息")
        
        # ========== 调用 assemble_context ==========
        print("\n[测试] 调用 assemble_context...")
        live_messages = [
            Msg(name="user", content="请总结之前的内容", role="user"),
        ]
        msg_dicts = mm._convert_messages(live_messages)
        
        result = await mm._client.assemble_context(
            session_id=mm.agent_id,
            messages=msg_dicts,
            token_budget=4000,
        )
        
        # ========== 展示完整返回结构 ==========
        print("\n" + "=" * 80)
        print("1️⃣ 完整返回结构 (JSON 格式)")
        print("=" * 80)
        
        # 为了展示，我们复制一份并格式化
        display_result = {
            "success": result.get("success"),
            "messages": f"[{len(result.get('messages', []))} 条消息]",
            "estimatedTokens": result.get("estimatedTokens"),
            "contextItems": result.get("contextItems"),
        }
        
        print(json.dumps(display_result, indent=2, ensure_ascii=False))
        
        # ========== 展示每个字段的详细信息 ==========
        print("\n" + "=" * 80)
        print("2️⃣ 字段详解")
        print("=" * 80)
        
        print(f"\n✅ success: {result.get('success')}")
        print(f"   类型：{type(result.get('success'))}")
        print(f"   说明：请求是否成功")
        
        print(f"\n📄 messages: [{len(result.get('messages', []))} 条消息]")
        print(f"   类型：{type(result.get('messages'))}")
        print(f"   说明：组装后的完整消息列表")
        
        print(f"\n🔢 estimatedTokens: {result.get('estimatedTokens')}")
        print(f"   类型：{type(result.get('estimatedTokens'))}")
        print(f"   说明：估计的 token 数量")
        
        print(f"\n📦 contextItems: {result.get('contextItems')}")
        print(f"   类型：{type(result.get('contextItems'))}")
        print(f"   说明：使用的上下文项数")
        
        # ========== 展示 messages 数组的详细结构 ==========
        print("\n" + "=" * 80)
        print("3️⃣ messages 数组详细结构")
        print("=" * 80)
        
        messages = result.get('messages', [])
        print(f"\n总共 {len(messages)} 条消息\n")
        
        # 展示前 3 条消息的完整结构
        for i, msg in enumerate(messages[:3], 1):
            print(f"┌─ 消息 {i} " + "─" * 70)
            print(f"│ 类型：{type(msg)}")
            
            if isinstance(msg, dict):
                print(f"│ 键：{list(msg.keys())}")
                for key, value in msg.items():
                    if key == 'content':
                        # 特殊处理 content
                        if isinstance(value, list):
                            print(f"│ {key}: [")
                            for block in value[:2]:  # 只显示前 2 个 block
                                if isinstance(block, dict):
                                    if block.get('type') == 'text':
                                        text = block.get('text', '')[:100]
                                        print(f"│     {{'type': 'text', 'text': '{text}...'}}")
                                    else:
                                        print(f"│     {block}")
                            if len(value) > 2:
                                print(f"│     ... 还有 {len(value) - 2} 个 block")
                            print(f"│ ]")
                        else:
                            print(f"│ {key}: {value}")
                    elif key == 'id':
                        print(f"│ {key}: {value}")
                    else:
                        value_str = str(value)[:100]
                        print(f"│ {key}: {value_str}...")
            
            print(f"└" + "─" * 76)
            print()
        
        if len(messages) > 3:
            print(f"... 还有 {len(messages) - 3} 条消息\n")
        
        # ========== 展示不同类型的 message ==========
        print("=" * 80)
        print("4️⃣ 消息类型分析")
        print("=" * 80)
        
        # 统计不同类型的消息
        summary_count = 0
        regular_count = 0
        
        for msg in messages:
            if isinstance(msg, dict):
                content = msg.get('content', '')
                if isinstance(content, str) and '<summary' in content:
                    summary_count += 1
                else:
                    regular_count += 1
        
        print(f"\n📊 消息类型统计:")
        print(f"   - 摘要消息 (summary): {summary_count} 条")
        print(f"   - 普通消息：{regular_count} 条")
        print(f"   - 总计：{len(messages)} 条")
        
        # ========== 展示摘要消息示例 ==========
        if summary_count > 0:
            print(f"\n📝 摘要消息示例:")
            for msg in messages[:5]:
                if isinstance(msg, dict):
                    content = msg.get('content', '')
                    if isinstance(content, str) and '<summary' in content:
                        print(f"\n   {content[:200]}...")
                        break
        
        # ========== 展示普通消息示例 ==========
        if regular_count > 0:
            print(f"\n💬 普通消息示例:")
            count = 0
            for msg in messages:
                if isinstance(msg, dict):
                    content = msg.get('content', '')
                    if not (isinstance(content, str) and '<summary' in content):
                        # 提取文本
                        text = ""
                        if isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get('type') == 'text':
                                    text = block.get('text', '')[:150]
                                    break
                        elif isinstance(content, str):
                            text = content[:150]
                        
                        print(f"   [{msg.get('role', 'unknown')}] {text}...")
                        count += 1
                        if count >= 3:
                            break
        
        # ========== 不同 token_budget 的返回对比 ==========
        print("\n" + "=" * 80)
        print("5️⃣ 不同 token_budget 的返回对比")
        print("=" * 80)
        
        print(f"\n{'Token Budget':<15} {'Messages':<10} {'Estimated Tokens':<20} {'Context Items':<15}")
        print("-" * 60)
        
        for budget in [500, 2000, 4000, 8000]:
            result = await mm._client.assemble_context(
                session_id=mm.agent_id,
                messages=msg_dicts,
                token_budget=budget,
            )
            print(f"{budget:<15} {len(result.get('messages', [])):<10} "
                  f"{result.get('estimatedTokens', 0):<20} "
                  f"{result.get('contextItems', 0):<15}")
        
        # ========== 总结 ==========
        print("\n" + "=" * 80)
        print("📋 返回格式总结")
        print("=" * 80)
        
        print("""
✅ 返回类型：dict

✅ 顶层字段:
   {
       "success": bool,           # 请求是否成功
       "messages": list,          # 组装后的消息数组
       "estimatedTokens": int,    # 估计的 token 数量
       "contextItems": int,       # 使用的上下文项数
   }

✅ messages 数组中的每条消息:
   {
       "id": str,                 # 消息 ID (可选)
       "role": str,               # "user" | "assistant" | "system"
       "content": list | str,     # 内容数组或字符串
       "name": str,               # 名称 (可选)
       ...                        # 其他可选字段
   }

✅ content 字段格式:
   - 数组格式：[{"type": "text", "text": "内容..."}]
   - 字符串格式："内容..."
   - 摘要格式："<summary id='...' kind='...' ...>摘要内容</summary>"

📖 详细文档：ASSEMBLE_CONTEXT_GUIDE.md
        """)
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ 错误：{e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await mm.close()
        print("\n✅ 已关闭内存管理器")


if __name__ == "__main__":
    asyncio.run(test_assemble_context_return_format())
