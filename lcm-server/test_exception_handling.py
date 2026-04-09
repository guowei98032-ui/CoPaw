# -*- coding: utf-8 -*-
"""Test script to verify compact_memory exception handling."""
import asyncio
import sys
sys.path.insert(0, "C:/workspace/CoPaw/src")

from copaw.agents.memory.lcm_memory_manager import LCMMemoryManager
from agentscope.message import Msg


async def test_compact_memory_exception_handling():
    """Test compact_memory with various scenarios."""
    print("=" * 60)
    print("Test compact_memory Exception Handling")
    print("=" * 60)
    
    # Create memory manager
    mm = LCMMemoryManager(
        working_dir="C:/workspace/CoPaw/lcm-server/data/test-exception",
        agent_id="default"
    )
    
    try:
        # Start
        print("\n[1] Start memory manager...")
        await mm.start()
        print("    ✅ Started")
        
        # Test 1: Normal compact (should work)
        print("\n[2] Test normal compact...")
        messages = [
            Msg(name="user", content="Hello", role="user"),
            Msg(name="assistant", content="Hi there!", role="assistant"),
        ]
        result = await mm.compact_memory(messages)
        print(f"    Result: '{result}'")
        print("    ✅ No exception")
        
        # Test 2: Empty messages
        print("\n[3] Test empty messages...")
        result = await mm.compact_memory([])
        print(f"    Result: '{result}'")
        print("    ✅ No exception")
        
        # Test 3: Multiple calls
        print("\n[4] Test multiple calls...")
        for i in range(3):
            messages = [
                Msg(name="user", content=f"Message {i}", role="user"),
                Msg(name="assistant", content=f"Response {i}", role="assistant"),
            ]
            result = await mm.compact_memory(messages)
            print(f"    Call {i+1}: '{result}'")
        print("    ✅ No exception")
        
        print("\n" + "=" * 60)
        print("All exception handling tests passed! ✅")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Close
        print("\n[5] Close memory manager...")
        await mm.close()
        print("    ✅ Closed")


if __name__ == "__main__":
    asyncio.run(test_compact_memory_exception_handling())
