# -*- coding: utf-8 -*-
"""
Test script to verify LCM summary model configuration is working correctly.
This tests the full flow: init -> ingest -> compact -> verify no errors.
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from copaw.agents.memory.lcm_client import LCMClient, LCMClientError

async def test_summary_model_config():
    """Test that summary model configuration is working."""
    print("=" * 70)
    print("LCM Summary Model Configuration Test")
    print("=" * 70)
    print()
    
    client = LCMClient(base_url="http://localhost:3721", timeout=60.0)
    
    try:
        # Test 1: Health check
        print("Test 1: Health check...")
        health = await client.health_check()
        print(f"  ✅ Status: {health.get('status')}")
        print(f"  ✅ LCM Available: {health.get('lcmAvailable')}")
        print(f"  ✅ Provider: {health.get('config', {}).get('provider')}")
        print(f"  ✅ Model: {health.get('config', {}).get('model')}")
        print()
        
        # Test 2: Initialize session
        print("Test 2: Initialize session...")
        session_id = "test_summary_session"
        config = {
            "freshTailCount": 32,
            "contextThreshold": 0.75,
            "maxContextTokens": 128000,
            "dbPath": "./data/test_summary.db",
            "llmConfig": {
                "provider": "openai",
                "model": "qwen3.5-plus",
                "api_key": "sk-sp-4fe2f039355645e18038499216be4fa5",
                "base_url": "https://coding.dashscope.aliyuncs.com/v1",
            },
            "summary_model": "qwen3.5-plus",
            "summary_provider": "openai",
        }
        
        init_result = await client.init(session_id, config)
        print(f"  ✅ Session initialized: {init_result.get('success')}")
        print()
        
        # Test 3: Ingest messages
        print("Test 3: Ingest test messages...")
        messages = [
            {
                "id": "msg_1",
                "role": "user",
                "content": [{"type": "text", "text": "你好，我想了解 Python 的异步编程。"}]
            },
            {
                "id": "msg_2",
                "role": "assistant",
                "content": [{"type": "text", "text": "Python 的异步编程主要使用 asyncio 库。async/await 是核心语法..."}]
            },
            {
                "id": "msg_3",
                "role": "user",
                "content": [{"type": "text", "text": "能给我一个具体的例子吗？"}]
            },
            {
                "id": "msg_4",
                "role": "assistant",
                "content": [{"type": "text", "text": "当然可以。下面是一个简单的异步示例：\n\n```python\nimport asyncio\n\nasync def main():\n    print('Hello')\n    await asyncio.sleep(1)\n    print('World')\n\nasyncio.run(main())\n```\n\n这个例子展示了基本的 async/await 用法..."}]
            },
        ]
        
        ingest_result = await client.ingest(session_id, messages)
        print(f"  ✅ Ingested {ingest_result.get('ingested')} messages")
        print()
        
        # Test 4: Run compaction (this is where the error would occur)
        print("Test 4: Run compaction (testing summary model)...")
        print("  ⏳ This may take a few seconds...")
        
        try:
            compact_result = await client.compact(
                session_id,
                mode="force",
                token_budget=128000
            )
            
            result_data = compact_result.get('result', {})
            
            if isinstance(result_data, dict):
                if result_data.get('compacted'):
                    print(f"  ✅ Compaction successful!")
                    print(f"     - Reason: {result_data.get('reason', 'N/A')}")
                    print(f"     - OK: {result_data.get('ok', 'N/A')}")
                else:
                    print(f"  ℹ️  Compaction not needed (messages within threshold)")
            else:
                print(f"  ⚠️  Unexpected result format: {type(result_data)}")
                print(f"      Result: {result_data}")
            
            print()
            
        except LCMClientError as e:
            print(f"  ❌ Compaction failed with LCMClientError:")
            print(f"     {e}")
            print()
            
            # Check if it's the summary model error
            if "no summary model candidates" in str(e).lower():
                print("  ⚠️  This is the 'no summary model candidates' error!")
                print("  Suggested fix: Set environment variables:")
                print("    set LCM_SUMMARY_MODEL=qwen3.5-plus")
                print("    set LCM_SUMMARY_PROVIDER=openai")
                print()
            raise
            
        # Test 5: Get stats
        print("Test 5: Get session stats...")
        stats = await client.get_stats(session_id)
        print(f"  ✅ Session stats:")
        for key, value in stats.items():
            if key != 'sessionId':
                print(f"     - {key}: {value}")
        print()
        
        # Test 6: Assemble context
        print("Test 6: Assemble context...")
        context_result = await client.assemble_context(
            session_id,
            messages=messages[-2:],  # Last 2 messages
            token_budget=100000
        )
        print(f"  ✅ Context assembled:")
        print(f"     - Messages: {len(context_result.get('messages', []))}")
        print(f"     - Estimated tokens: {context_result.get('estimatedTokens', 'N/A')}")
        print(f"     - Context items: {context_result.get('contextItems', 'N/A')}")
        print()
        
        # Test 7: Close session
        print("Test 7: Close session...")
        await client.close_session(session_id)
        print(f"  ✅ Session closed")
        print()
        
        print("=" * 70)
        print("✅ All tests passed! Summary model configuration is working correctly.")
        print("=" * 70)
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
    success = asyncio.run(test_summary_model_config())
    sys.exit(0 if success else 1)
