# -*- coding: utf-8 -*-
"""Test script to simulate compact_memory exception scenarios."""
import asyncio
import sys
sys.path.insert(0, "C:/workspace/CoPaw/src")

from copaw.agents.memory.lcm_client import LCMClient, LCMClientError
from agentscope.message import Msg


async def test_compact_memory_scenarios():
    """Test various compact_memory scenarios."""
    client = LCMClient(base_url="http://localhost:3721")
    
    print("=" * 60)
    print("Test Compact Memory Scenarios")
    print("=" * 60)
    
    session_id = "test-compact-scenarios"
    
    try:
        # Initialize
        print("\n[1] Initialize...")
        await client.init(session_id, config={"dbPath": "data/test-scenarios.db"})
        
        # Scenario 1: Normal compact (no actual compaction needed)
        print("\n[2] Scenario 1: Normal compact (under target)...")
        messages = [
            Msg(name="user", content="Hello", role="user"),
            Msg(name="assistant", content="Hi", role="assistant"),
        ]
        msg_dicts = [
            {"id": None, "role": msg.role, "content": [{"type": "text", "text": msg.content}]}
            for msg in messages
        ]
        
        await client.ingest(session_id, msg_dicts)
        result = await client.compact(session_id, mode="force", token_budget=128000)
        
        print(f"    Result type: {type(result)}")
        print(f"    Result keys: {result.keys()}")
        print(f"    result field: {result.get('result')}")
        print(f"    result field type: {type(result.get('result'))}")
        
        compact_result = result.get("result", {})
        print(f"    compact_result type: {type(compact_result)}")
        
        # This is what compact_memory does
        if isinstance(compact_result, dict) and compact_result.get("compacted"):
            print(f"    ✅ Would return: [LCM Compacted: {compact_result.get('reason')}]")
        else:
            print(f"    ℹ️  Would return: '' (compacted={compact_result.get('compacted')})")
        
        # Scenario 2: Check if compact_result could be non-dict
        print("\n[3] Scenario 2: Check edge cases...")
        
        # Test with empty result
        test_cases = [
            {},
            {"result": None},
            {"result": "string"},
            {"result": 123},
            {"result": {"compacted": True}},
            {"result": {"compacted": False}},
        ]
        
        for i, test_result in enumerate(test_cases):
            print(f"\n    Test case {i+1}: {test_result}")
            try:
                compact_result = test_result.get("result", {})
                print(f"      compact_result: {compact_result} (type: {type(compact_result)})")
                
                if isinstance(compact_result, dict):
                    is_compacted = compact_result.get("compacted")
                    print(f"      compacted: {is_compacted}")
                else:
                    print(f"      ⚠️  compact_result is not a dict!")
                    # This would cause AttributeError in original code
                    # is_compacted = compact_result.get("compacted")  # ERROR!
            except Exception as e:
                print(f"      ❌ Error: {e}")
        
        print("\n" + "=" * 60)
        print("Test completed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await client.close_session(session_id)
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_compact_memory_scenarios())
