# -*- coding: utf-8 -*-
"""Test script for LCMMemoryManager integration in CoPaw."""
import asyncio
import sys
sys.path.insert(0, 'C:/workspace/CoPaw/src')

# Use real agent_id that exists in config
working_dir = "C:/workspace/CoPaw/lcm-server/data"
agent_id = "default"  # Use 'default' agent which exists

from copaw.agents.memory import LCMMemoryManager

async def test_lcm_memory_manager():
    """Test LCMMemoryManager functionality."""
    print("=" * 60)
    print("LCMMemoryManager Integration Test")
    print("=" * 60)
    
    # Create memory manager
    manager = LCMMemoryManager(working_dir=working_dir, agent_id=agent_id)
    
    try:
        # 1. Start
        print("\n[1] Start Memory Manager...")
        await manager.start()
        print(f"    Started successfully")
        
        # 2. Compact memory (this ingests messages into LCM)
        print("\n[2] Compact Memory (ingest messages)...")
        from agentscope.message import Msg
        
        messages = [
            Msg(name="user", content="Hello, I want to learn about AI", role="user"),
            Msg(name="assistant", content="AI is artificial intelligence!", role="assistant"),
            Msg(name="user", content="What are the main branches?", role="user"),
            Msg(name="assistant", content="Machine learning, NLP, computer vision.", role="assistant"),
        ]
        
        result = await manager.compact_memory(messages)
        print(f"    Compact result: {result[:100] if result else 'No summary generated'}")
        
        # 3. Memory search
        print("\n[3] Memory Search...")
        search_result = await manager.memory_search(query="AI", max_results=5)
        print(f"    Search content: {search_result.content[:200]}...")
        
        # 4. Get in-memory memory (should return None for LCM)
        print("\n[4] Get In-Memory Memory...")
        in_memory = manager.get_in_memory_memory()
        print(f"    Result: {in_memory} (expected: None for LCM)")
        
        # 5. LCM specific: grep
        print("\n[5] LCM Grep...")
        grep_result = await manager.lcm_grep(query="AI", limit=5)
        print(f"    Grep result: {len(grep_result)} matches")
        
        # 6. Stop
        print("\n[6] Stop Memory Manager...")
        await manager.stop()
        print(f"    Stopped successfully")
        
        print("\n" + "=" * 60)
        print("All tests passed!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        try:
            await manager.stop()
        except:
            pass
        return False

if __name__ == "__main__":
    success = asyncio.run(test_lcm_memory_manager())
    sys.exit(0 if success else 1)