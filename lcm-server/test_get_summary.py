# -*- coding: utf-8 -*-
"""Test script to explore how to get summary from LCM."""
import asyncio
import sys
sys.path.insert(0, "C:/workspace/CoPaw/src")

from copaw.agents.memory.lcm_memory_manager import LCMMemoryManager
from agentscope.message import Msg


async def test_get_summary():
    """Test different ways to get summary from LCM."""
    print("=" * 60)
    print("Test Getting Summary from LCM")
    print("=" * 60)
    
    mm = LCMMemoryManager(
        working_dir="C:/workspace/CoPaw/lcm-server/data/test-summary",
        agent_id="default"
    )
    
    try:
        # Start
        print("\n[1] Start memory manager...")
        await mm.start()
        print("    ✅ Started")
        
        # Clear previous data by using a fresh session
        print("\n[2] Create test conversation...")
        messages = []
        for i in range(5):
            messages.extend([
                Msg(name="user", content=f"Question {i} about Python programming", role="user"),
                Msg(name="assistant", content=f"Answer {i} about Python programming concepts", role="assistant"),
            ])
        
        # Ingest and compact
        print(f"    Ingesting {len(messages)} messages...")
        result = await mm.compact_memory(messages)
        print(f"    Compact result: '{result}'")
        
        # Method 1: Check compact_memory return value
        print("\n[3] Method 1: compact_memory() return value")
        print(f"    Return: '{result}'")
        print("    ℹ️  Returns status string, not actual summary content")
        
        # Method 2: Use lcm_grep to search for content
        print("\n[4] Method 2: lcm_grep() to search compacted history")
        grep_results = await mm.lcm_grep("Python", limit=5)
        print(f"    Found {len(grep_results)} matches:")
        for item in grep_results[:3]:
            print(f"      - {item}")
        
        # Method 3: Use memory_search
        print("\n[5] Method 3: memory_search()")
        from copaw.agents.memory.lcm_memory_manager import ToolResponse
        search_result = await mm.memory_search("Python", max_results=3)
        print(f"    Search result type: {type(search_result)}")
        print(f"    Content preview: {search_result.content[:200]}...")
        
        # Method 4: Get context (assembled with summaries)
        print("\n[6] Method 4: get_context()")
        context = await mm.get_context()
        print(f"    Context type: {type(context)}")
        print(f"    Context length: {len(context) if context else 0}")
        if context:
            print(f"    First item: {context[0] if isinstance(context[0], str) else str(context[0])[:100]}...")
        
        # Method 5: Check if there's a get_stats method
        print("\n[7] Method 5: Check for stats/summary info")
        if hasattr(mm, 'get_stats'):
            stats = await mm.get_stats()
            print(f"    Stats: {stats}")
        else:
            print("    ⚠️  No get_stats method")
        
        # Check client for get_stats
        if hasattr(mm._client, 'get_stats'):
            try:
                stats = await mm._client.get_stats(mm.agent_id)
                print(f"    Client stats: {stats}")
            except Exception as e:
                print(f"    ⚠️  get_stats error: {e}")
        else:
            print("    ⚠️  Client has no get_stats method")
        
        # Method 6: Use lcm_describe (if summary_id available)
        print("\n[8] Method 6: lcm_describe()")
        print("    ℹ️  Requires summary_id from compact result")
        print("    ⚠️  Currently not implemented on server side")
        
        # Method 7: Use lcm_expand (if summary_id available)
        print("\n[9] Method 7: lcm_expand()")
        print("    ℹ️  Requires summary_id from compact result")
        print("    ⚠️  Currently not implemented on server side")
        
        print("\n" + "=" * 60)
        print("Summary Retrieval Methods Summary:")
        print("=" * 60)
        print("""
1. compact_memory() → Returns status string, not summary content
2. lcm_grep() → Search compacted messages by keyword ✅ WORKING
3. memory_search() → Search via ToolResponse interface ✅ WORKING
4. get_context() → Get assembled context (summaries + live messages) ✅ WORKING
5. get_stats() → Get session statistics (not implemented)
6. lcm_describe() → Describe summary (server not implemented)
7. lcm_expand() → Expand summary to original messages (server not implemented)

CURRENT RECOMMENDATION:
- Use lcm_grep() to search compacted history
- Use memory_search() for ToolResponse format
- Use get_context() for model input context
        """)
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\n[10] Close memory manager...")
        await mm.close()
        print("    ✅ Closed")


if __name__ == "__main__":
    asyncio.run(test_get_summary())
