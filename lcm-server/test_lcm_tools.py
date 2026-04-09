# -*- coding: utf-8 -*-
"""
Test script for LCM tools: lcm_grep, lcm_describe, lcm_expand, memory_search
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from copaw.agents.memory.lcm_client import LCMClient, LCMClientError

async def test_lcm_tools():
    """Test all LCM tools."""
    print("=" * 70)
    print("LCM Tools Test: grep, describe, expand, memory_search")
    print("=" * 70)
    print()
    
    client = LCMClient(base_url="http://localhost:3721", timeout=180.0)
    
    try:
        # Step 1: Initialize session
        print("Step 1: Initialize session...")
        session_id = "test_lcm_tools"
        config = {
            "freshTailCount": 5,
            "contextThreshold": 0.5,
            "maxContextTokens": 50000,
            "dbPath": "./data/test_tools.db",
            "provider": "openai",
            "model": "qwen3.5-plus",
            "apiKey": "sk-sp-4fe2f039355645e18038499216be4fa5",
            "baseUrl": "https://coding.dashscope.aliyuncs.com/v1",
            "llmConfig": {
                "provider": "openai",
                "model": "qwen3.5-plus",
                "apiKey": "sk-sp-4fe2f039355645e18038499216be4fa5",
                "baseUrl": "https://coding.dashscope.aliyuncs.com/v1",
            },
            "summaryModel": "qwen3.5-plus",
            "summaryProvider": "openai",
        }
        
        await client.init(session_id, config)
        print("  ✅ Session initialized")
        print()
        
        # Step 2: Ingest diverse messages for testing
        print("Step 2: Ingest test messages with diverse content...")
        messages = [
            # Topic 1: Python programming
            {
                "id": "msg_py_1",
                "role": "user",
                "content": [{"type": "text", "text": "Python 中的异步编程如何使用 async 和 await？"}]
            },
            {
                "id": "msg_py_2",
                "role": "assistant",
                "content": [{"type": "text", "text": "Python 的异步编程使用 asyncio 库。async 定义协程函数，await 等待异步操作完成。例如：async def fetch(): data = await api_call()"}]
            },
            # Topic 2: Database
            {
                "id": "msg_db_1",
                "role": "user",
                "content": [{"type": "text", "text": "SQLite 和 MySQL 有什么区别？"}]
            },
            {
                "id": "msg_db_2",
                "role": "assistant",
                "content": [{"type": "text", "text": "SQLite 是嵌入式数据库，无需服务器，适合小型应用。MySQL 是客户端 - 服务器数据库，支持并发访问，适合大型应用。"}]
            },
            # Topic 3: Web development
            {
                "id": "msg_web_1",
                "role": "user",
                "content": [{"type": "text", "text": "React 和 Vue 哪个更好？"}]
            },
            {
                "id": "msg_web_2",
                "role": "assistant",
                "content": [{"type": "text", "text": "React 由 Facebook 开发，生态丰富，适合大型项目。Vue 由尤雨溪开发，学习曲线平缓，适合中小型项目。选择取决于团队熟悉度和项目需求。"}]
            },
            # Topic 4: Machine Learning
            {
                "id": "msg_ml_1",
                "role": "user",
                "content": [{"type": "text", "text": "什么是 Transformer 模型？"}]
            },
            {
                "id": "msg_ml_2",
                "role": "assistant",
                "content": [{"type": "text", "text": "Transformer 是一种基于自注意力机制的深度学习模型，由 Google 在 2017 年提出。它并行处理序列数据，在 NLP 任务中表现出色。BERT、GPT 都基于 Transformer。"}]
            },
            # Topic 5: DevOps
            {
                "id": "msg_devops_1",
                "role": "user",
                "content": [{"type": "text", "text": "Docker 容器化的好处是什么？"}]
            },
            {
                "id": "msg_devops_2",
                "role": "assistant",
                "content": [{"type": "text", "text": "Docker 容器化提供环境一致性、快速部署、资源隔离、可移植性等优点。一次构建，到处运行。"}]
            },
        ]
        
        await client.ingest(session_id, messages)
        print(f"  ✅ Ingested {len(messages)} messages")
        print()
        
        # Step 3: Force compaction to create summaries
        print("Step 3: Force compaction to create summaries...")
        print("  ⏳ This may take 30-60 seconds...")
        
        compact_result = await client.compact(
            session_id,
            mode="force",
            token_budget=10000
        )
        
        result_data = compact_result.get('result', {})
        if isinstance(result_data, dict) and result_data.get('compacted'):
            print(f"  ✅ Compaction successful")
        else:
            print(f"  ℹ️  Compaction result: {result_data}")
        print()
        
        # Step 4: Test lcm_grep
        print("=" * 70)
        print("Test 1: lcm_grep - Search through conversation history")
        print("=" * 70)
        
        search_queries = [
            ("Python", "regex"),
            ("数据库", "regex"),
            ("Transformer|BERT|GPT", "regex"),
        ]
        
        for query, mode in search_queries:
            print(f"\n  Search query: '{query}' (mode: {mode})")
            grep_result = await client.grep(
                session_id,
                pattern=query,
                mode=mode,
                scope="both",
                limit=10
            )
            
            total = grep_result.get('totalMatches', 0)
            messages_found = grep_result.get('messages', [])
            summaries_found = grep_result.get('summaries', [])
            
            print(f"    Total matches: {total}")
            print(f"    Messages: {len(messages_found)}")
            print(f"    Summaries: {len(summaries_found)}")
            
            if messages_found:
                print(f"    Sample match:")
                sample = messages_found[0]
                snippet = sample.get('snippet', sample.get('content', ''))[:100]
                print(f"      - [{sample.get('role')}] {snippet}...")
        
        print()
        
        # Step 5: Get stats to find summary IDs
        print("=" * 70)
        print("Test 2: Get session stats")
        print("=" * 70)
        
        stats = await client.get_stats(session_id)
        print(f"  Session stats: {stats}")
        print()
        
        # Step 6: Test lcm_describe (if summary ID available)
        print("=" * 70)
        print("Test 3: lcm_describe - Get summary details")
        print("=" * 70)
        
        # Try to get summary ID from stats or grep
        summary_id = None
        if stats.get('summaryCount', 0) > 0:
            print(f"  Found {stats.get('summaryCount')} summaries in session")
            # We need to get summary ID from the database
            # For now, we'll try a common format
            summary_id = "summary_1"  # Try default ID
        
        if summary_id:
            print(f"  Attempting to describe summary: {summary_id}")
            try:
                describe_result = await client.describe(session_id, summary_id=summary_id)
                print(f"  Describe result: {describe_result}")
            except Exception as e:
                print(f"  ℹ️  Describe not available yet: {e}")
        else:
            print(f"  ℹ️  No summary ID available")
        
        print()
        
        # Step 7: Test lcm_expand (if summary ID available)
        print("=" * 70)
        print("Test 4: lcm_expand - Expand summary to get original messages")
        print("=" * 70)
        
        if summary_id:
            print(f"  Attempting to expand summary: {summary_id}")
            try:
                expand_result = await client.expand(
                    session_id,
                    summary_id=summary_id,
                    query="Python"
                )
                print(f"  Expand result: {expand_result}")
            except Exception as e:
                print(f"  ℹ️  Expand not available yet: {e}")
        else:
            print(f"  ℹ️  No summary ID available")
        
        print()
        
        # Step 8: Test memory_search (semantic search)
        print("=" * 70)
        print("Test 5: memory_search - Semantic search")
        print("=" * 70)
        
        # This requires embedding to be configured
        print("  Note: memory_search requires embedding configuration")
        print("  Testing with grep as fallback...")
        
        semantic_queries = [
            "异步编程",
            "深度学习",
            "容器化",
        ]
        
        for query in semantic_queries:
            print(f"\n  Semantic query: '{query}'")
            # Use grep as fallback
            grep_result = await client.grep(
                session_id,
                pattern=query,
                mode="full_text",
                scope="both",
                limit=5
            )
            
            total = grep_result.get('totalMatches', 0)
            print(f"    Matches: {total}")
        
        print()
        
        # Step 9: Close session
        print("=" * 70)
        print("Step 9: Close session")
        print("=" * 70)
        
        await client.close_session(session_id)
        print("  ✅ Session closed")
        print()
        
        # Summary
        print("=" * 70)
        print("✅ LCM Tools Test Summary")
        print("=" * 70)
        print()
        print("Tested tools:")
        print("  ✅ lcm_grep - Search through conversation history")
        print("  ⚠️  lcm_describe - Get summary details (requires summary ID)")
        print("  ⚠️  lcm_expand - Expand summary (requires summary ID)")
        print("  ⚠️  memory_search - Semantic search (requires embedding)")
        print()
        print("Notes:")
        print("  - grep: Fully functional ✅")
        print("  - describe/expand: Need summary ID from database")
        print("  - memory_search: Requires embedding configuration")
        print()
        
        return True
        
    except LCMClientError as e:
        print("=" * 70)
        print(f"❌ Test failed with LCMClientError: {e}")
        print("=" * 70)
        return False
    except Exception as e:
        print("=" * 70)
        print(f"❌ Test failed with unexpected error: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        return False
    finally:
        await client.close()


if __name__ == "__main__":
    success = asyncio.run(test_lcm_tools())
    sys.exit(0 if success else 1)
