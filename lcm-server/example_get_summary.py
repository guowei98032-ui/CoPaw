# -*- coding: utf-8 -*-
"""Simple example: How to get summary from LCM."""
import asyncio
import sys
sys.path.insert(0, "C:/workspace/CoPaw/src")

from copaw.agents.memory.lcm_memory_manager import LCMMemoryManager
from agentscope.message import Msg


async def main():
    print("=" * 60)
    print("LCM 获取 Summary 示例")
    print("=" * 60)
    
    mm = LCMMemoryManager(
        working_dir="C:/workspace/CoPaw/lcm-server/data/example",
        agent_id="default"
    )
    await mm.start()
    
    try:
        # ========== 步骤 1: 压缩消息 ==========
        print("\n[步骤 1] 压缩消息...")
        messages = [
            Msg(name="user", content="Python 是什么？", role="user"),
            Msg(name="assistant", content="Python 是一种高级编程语言，由 Guido van Rossum 于 1989 年发明。", role="assistant"),
            Msg(name="user", content="Python 有什么特点？", role="user"),
            Msg(name="assistant", content="Python 特点：简洁易读、跨平台、丰富的库、支持多种编程范式。", role="assistant"),
            Msg(name="user", content="Python 适合做什么？", role="user"),
            Msg(name="assistant", content="Python 适合：Web 开发、数据分析、人工智能、自动化脚本、科学计算。", role="assistant"),
        ]
        
        compact_result = await mm.compact_memory(messages)
        print(f"压缩状态：{compact_result}")
        
        # ========== 步骤 2: 搜索内容 ==========
        print("\n[步骤 2] 使用 lcm_grep 搜索 'Python'...")
        results = await mm.lcm_grep("Python", limit=5)
        print(f"找到 {len(results)} 条匹配:\n")
        for i, item in enumerate(results, 1):
            print(f"{i}. [{item['role']}] {item['snippet']}")
            print(f"   消息 ID: {item['messageId']}")
            print()
        
        # ========== 步骤 3: 使用 memory_search ==========
        print("\n[步骤 3] 使用 memory_search 搜索 '特点'...")
        tool_result = await mm.memory_search("特点", max_results=3)
        print(f"类型：{type(tool_result)}")
        print(f"内容:\n{tool_result.content}")
        print(f"元数据：{tool_result.metadata}")
        
        # ========== 步骤 4: 获取统计信息 ==========
        print("\n[步骤 4] 获取会话统计...")
        try:
            stats = await mm._client.get_stats(mm.agent_id)
            print(f"会话统计：{stats}")
        except Exception as e:
            print(f"⚠️ 获取统计失败：{e}")
        
        # ========== 总结 ==========
        print("\n" + "=" * 60)
        print("总结:")
        print("=" * 60)
        print("""
✅ compact_memory() - 返回压缩状态字符串
✅ lcm_grep() - 搜索压缩历史，返回详细匹配信息
✅ memory_search() - ToolResponse 格式的搜索结果
⚠️  get_context() - 需要先在 LCMClient 中添加方法
⚠️  get_stats() - 需要先在 LCMClient 中添加方法
❌ lcm_describe() - 服务器未实现
❌ lcm_expand() - 服务器未实现

推荐：使用 lcm_grep() 或 memory_search() 访问压缩内容
        """)
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 错误：{e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await mm.close()
        print("\n✅ 已关闭内存管理器")


if __name__ == "__main__":
    asyncio.run(main())
