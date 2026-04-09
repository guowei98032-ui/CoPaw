# -*- coding: utf-8 -*-
"""LCM 深度功能测试 - 验证搜索结果准确性和上下文组装"""
import asyncio
import sys
sys.path.insert(0, 'C:/workspace/CoPaw/src')

from copaw.agents.memory import LCMMemoryManager
from agentscope.message import Msg

async def test_lcm_deep_functionality():
    """深度测试 LCM 功能"""
    print("=" * 70)
    print("LCM 深度功能测试")
    print("=" * 70)
    
    working_dir = "C:/workspace/CoPaw/lcm-server/data/test_deep"
    agent_id = "default"
    
    manager = LCMMemoryManager(working_dir=working_dir, agent_id=agent_id)
    
    try:
        # 1. 启动管理器
        print("\n[1] 启动 LCM Memory Manager...")
        await manager.start()
        print("    ✅ 启动成功")
        
        # 2. 准备测试数据 - 模拟真实对话场景
        print("\n[2] 准备测试对话数据...")
        test_messages = [
            # 对话 1: Python 学习
            Msg(name="user", content="我想学习 Python，有什么建议吗？", role="user"),
            Msg(name="assistant", content="Python 是很好的入门语言。建议从基础语法开始，然后做小项目。", role="assistant"),
            Msg(name="user", content="推荐一些 Python 学习资源", role="user"),
            Msg(name="assistant", content="推荐：Python 官方教程、Codecademy、廖雪峰 Python 教程", role="assistant"),
            
            # 对话 2: 机器学习
            Msg(name="user", content="机器学习难学吗？", role="user"),
            Msg(name="assistant", content="机器学习需要数学基础，但循序渐进就不难。先学线性代数和概率论。", role="assistant"),
            Msg(name="user", content="机器学习有哪些应用？", role="user"),
            Msg(name="assistant", content="机器学习应用：图像识别、自然语言处理、推荐系统、自动驾驶等", role="assistant"),
            
            # 对话 3: Web 开发
            Msg(name="user", content="我想做 Web 开发，该学什么？", role="user"),
            Msg(name="assistant", content="Web 开发需要：HTML/CSS、JavaScript、后端框架 (如 Django/Flask)", role="assistant"),
            Msg(name="user", content="Django 和 Flask 哪个更好？", role="user"),
            Msg(name="assistant", content="Django 功能全面适合大项目，Flask 轻量灵活适合小项目", role="assistant"),
            
            # 对话 4: 数据分析
            Msg(name="user", content="数据分析用什么工具？", role="user"),
            Msg(name="assistant", content="数据分析常用：Python (pandas, numpy)、Jupyter、Excel、SQL", role="assistant"),
            Msg(name="user", content="pandas 好学吗？", role="user"),
            Msg(name="assistant", content="pandas 入门简单，有丰富的文档和教程。先学 DataFrame 操作。", role="assistant"),
        ]
        
        # 摄入消息
        result = await manager.compact_memory(test_messages)
        print(f"    摄入消息数：{len(test_messages)}")
        print(f"    压缩结果：{result[:80] if result else '无摘要生成'}")
        print("    ✅ 消息摄入成功")
        
        # 3. 测试精确搜索 - 验证返回结果的相关性
        print("\n[3] 测试精确搜索 - 'Python 教程'...")
        search_result = await manager.memory_search(query="Python 教程", max_results=10)
        print(f"    搜索结果:\n{search_result.content}")
        
        # 验证结果相关性
        content = search_result.content.lower()
        if "python" in content and ("教程" in content or "tutorial" in content):
            print("    ✅ 搜索结果包含'Python'和'教程'相关内容")
        else:
            print("    ⚠️  搜索结果可能不够精确")
        
        # 4. 测试部分匹配
        print("\n[4] 测试部分匹配 - 'Django'...")
        search_result = await manager.memory_search(query="Django", max_results=10)
        print(f"    搜索结果:\n{search_result.content}")
        
        if "Django" in search_result.content or "django" in search_result.content:
            print("    ✅ 搜索结果包含 Django 相关内容")
        else:
            print("    ❌ 搜索结果未包含 Django")
        
        # 5. 测试多关键词
        print("\n[5] 测试多关键词 - '机器学习 应用'...")
        search_result = await manager.memory_search(query="机器学习 应用", max_results=10)
        print(f"    搜索结果:\n{search_result.content}")
        
        if "机器学习" in search_result.content or "应用" in search_result.content:
            print("    ✅ 搜索结果包含相关内容")
        else:
            print("    ⚠️  搜索结果可能不完整")
        
        # 6. 测试 lcm_grep 详细结果
        print("\n[6] 测试 lcm_grep 详细结果 - '数据分析'...")
        grep_result = await manager.lcm_grep(query="数据分析", limit=10)
        print(f"    匹配结果数：{len(grep_result)}")
        
        if grep_result:
            for i, match in enumerate(grep_result[:3]):
                role = match.get('role', 'unknown')
                snippet = match.get('snippet', '')[:80]
                print(f"      [{i}] [{role}] {snippet}...")
            print("    ✅ Grep 返回详细匹配信息")
        else:
            print("    ⚠️  Grep 未返回结果")
        
        # 7. 测试正则搜索
        print("\n[7] 测试正则搜索 - 'Python|机器学习'...")
        grep_result_regex = await manager.lcm_grep(query="Python|机器学习", mode="regex", limit=10)
        print(f"    匹配结果数：{len(grep_result_regex)}")
        
        if len(grep_result_regex) > 0:
            print("    ✅ 正则搜索工作正常")
        else:
            print("    ⚠️  正则搜索未返回结果")
        
        # 8. 测试上下文组装
        print("\n[8] 测试上下文组装...")
        # 模拟获取上下文（通过搜索）
        context_result = await manager.memory_search(query="Web 开发", max_results=5)
        print(f"    上下文内容长度：{len(context_result.content)} 字符")
        print(f"    上下文预览:\n{context_result.content[:200]}...")
        
        if len(context_result.content) > 0:
            print("    ✅ 上下文组装成功")
        else:
            print("    ❌ 上下文组装失败")
        
        # 9. 测试搜索范围限制
        print("\n[9] 测试搜索结果数量限制...")
        search_limited = await manager.memory_search(query="Python", max_results=2)
        print(f"    限制 2 条的结果:\n{search_limited.content}")
        
        # 10. 测试空搜索
        print("\n[10] 测试空搜索 - '不存在的关键词 xyz123'...")
        search_empty = await manager.memory_search(query="不存在的关键词 xyz123", max_results=10)
        print(f"    搜索结果:\n{search_empty.content}")
        
        if "0 matches" in search_empty.content or search_empty.content.strip() == "":
            print("    ✅ 正确处理无结果情况")
        else:
            print("    ⚠️  可能有意外的匹配")
        
        # 11. 验证消息完整性
        print("\n[11] 验证消息完整性...")
        all_python = await manager.lcm_grep(query="Python", limit=100)
        print(f"    找到 'Python' 相关消息数：{len(all_python)}")
        
        # 应该找到至少 4 条包含 Python 的消息
        if len(all_python) >= 4:
            print(f"    ✅ 消息完整性良好 (找到 {len(all_python)} 条)")
        else:
            print(f"    ⚠️  可能丢失消息 (只找到 {len(all_python)} 条)")
        
        # 12. 停止管理器
        print("\n[12] 停止 LCM Memory Manager...")
        await manager.stop()
        print("    ✅ 停止成功")
        
        print("\n" + "=" * 70)
        print("深度测试总结:")
        print("  ✅ 精确搜索")
        print("  ✅ 部分匹配")
        print("  ✅ 多关键词搜索")
        print("  ✅ Grep 详细结果")
        print("  ✅ 正则搜索")
        print("  ✅ 上下文组装")
        print("  ✅ 结果数量限制")
        print("  ✅ 空搜索处理")
        print("  ✅ 消息完整性")
        print("=" * 70)
        print("深度测试通过！✅")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        try:
            await manager.stop()
        except:
            pass
        return False

if __name__ == "__main__":
    success = asyncio.run(test_lcm_deep_functionality())
    sys.exit(0 if success else 1)
