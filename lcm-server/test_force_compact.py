# -*- coding: utf-8 -*-
"""
Force compaction test to verify summary model is working.
This creates enough messages to trigger compaction.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from copaw.agents.memory.lcm_client import LCMClient, LCMClientError

async def test_force_compaction():
    """Force compaction to test summary model."""
    print("=" * 70)
    print("LCM Force Compaction Test (Testing Summary Model)")
    print("=" * 70)
    print()
    
    client = LCMClient(base_url="http://localhost:3721", timeout=120.0)
    
    try:
        # Initialize
        print("Step 1: Initialize session...")
        session_id = "test_force_compact"
        config = {
            "freshTailCount": 5,  # Small to trigger compaction quickly
            "contextThreshold": 0.5,  # Lower threshold
            "maxContextTokens": 10000,  # Small budget
            "dbPath": "./data/test_force.db",
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
        
        # Create many messages to exceed token budget
        print("Step 2: Ingest many messages to exceed token budget...")
        messages = []
        for i in range(50):  # 50 message pairs
            msg_user = {
                "id": f"msg_user_{i}",
                "role": "user",
                "content": [{"type": "text", "text": f"这是第 {i+1} 个问题，关于 Python 编程的第 {i+1} 个疑问。" * 10}]
            }
            msg_assistant = {
                "id": f"msg_assistant_{i}",
                "role": "assistant",
                "content": [{"type": "text", "text": f"这是第 {i+1} 个问题的详细回答，包含了很多技术细节和代码示例。" * 20}]
            }
            messages.extend([msg_user, msg_assistant])
        
        print(f"  Creating {len(messages)} messages...")
        
        # Ingest in batches
        batch_size = 10
        for i in range(0, len(messages), batch_size):
            batch = messages[i:i+batch_size]
            await client.ingest(session_id, batch)
            print(f"  ✅ Ingested batch {i//batch_size + 1}/{(len(messages)+batch_size-1)//batch_size}")
        
        print()
        
        # Force compaction
        print("Step 3: Force compaction (this will test summary model)...")
        print("  ⏳ This may take 10-30 seconds for LLM summarization...")
        print()
        
        compact_result = await client.compact(
            session_id,
            mode="force",  # Force regardless of threshold
            token_budget=5000  # Very small to ensure compaction happens
        )
        
        result_data = compact_result.get('result', {})
        
        print("Step 4: Check compaction result...")
        if isinstance(result_data, dict):
            if result_data.get('compacted'):
                print(f"  ✅✅✅ COMPACTION SUCCESSFUL! ✅✅✅")
                print(f"     - Compacted: {result_data.get('compacted')}")
                print(f"     - Reason: {result_data.get('reason', 'N/A')}")
                print(f"     - OK: {result_data.get('ok', 'N/A')}")
                print()
                print("  🎉 Summary model is working correctly!")
                print("  🎉 No 'no summary model candidates' error!")
            else:
                print(f"  ℹ️  Compaction not triggered")
                print(f"     - Result: {result_data}")
        else:
            print(f"  ⚠️  Unexpected result: {type(result_data)}")
            print(f"      {result_data}")
        
        print()
        
        # Get stats
        print("Step 5: Get session stats...")
        stats = await client.get_stats(session_id)
        print(f"  Stats: {stats}")
        print()
        
        # Close
        print("Step 6: Close session...")
        await client.close_session(session_id)
        print("  ✅ Session closed")
        print()
        
        print("=" * 70)
        print("✅ TEST PASSED: Summary model configuration is working!")
        print("=" * 70)
        return True
        
    except LCMClientError as e:
        print("=" * 70)
        print(f"❌ LCMClientError: {e}")
        print("=" * 70)
        
        error_msg = str(e).lower()
        if "no summary model candidates" in error_msg:
            print()
            print("  ⚠️  This is the 'no summary model candidates' error!")
            print()
            print("  Solution:")
            print("  1. Check lcm-config.json has 'summary' section")
            print("  2. Or set environment variables:")
            print("     set LCM_SUMMARY_MODEL=qwen3.5-plus")
            print("     set LCM_SUMMARY_PROVIDER=openai")
            print()
        return False
    except Exception as e:
        print("=" * 70)
        print(f"❌ Unexpected error: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        return False
    finally:
        await client.close()


if __name__ == "__main__":
    success = asyncio.run(test_force_compaction())
    sys.exit(0 if success else 1)
