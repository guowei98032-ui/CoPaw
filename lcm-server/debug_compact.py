# -*- coding: utf-8 -*-
"""Debug script to check compact response structure."""
import asyncio
import sys
sys.path.insert(0, "C:/workspace/CoPaw/src")

from copaw.agents.memory.lcm_client import LCMClient


async def debug_compact():
    """Debug compact response."""
    client = LCMClient(base_url="http://localhost:3721")
    
    print("=" * 60)
    print("Debug Compact Response")
    print("=" * 60)
    
    try:
        # 1. Health check
        print("\n[1] Health check...")
        health = await client.health_check()
        print(f"    Status: {health}")
        
        # 2. Initialize session
        print("\n[2] Initialize session...")
        session_id = "debug-compact-session"
        init_result = await client.init(session_id, config={"dbPath": "data/debug-compact.db"})
        print(f"    Init result: {init_result}")
        
        # 3. Ingest some messages
        print("\n[3] Ingest messages...")
        messages = [
            {"role": "user", "content": [{"type": "text", "text": "Hello"}]},
            {"role": "assistant", "content": [{"type": "text", "text": "Hi there"}]},
            {"role": "user", "content": [{"type": "text", "text": "How are you?"}]},
            {"role": "assistant", "content": [{"type": "text", "text": "I'm good!"}]},
        ]
        ingest_result = await client.ingest(session_id, messages)
        print(f"    Ingest result: {ingest_result}")
        
        # 4. Compact - debug full response
        print("\n[4] Compact (force mode)...")
        compact_result = await client.compact(
            session_id, 
            mode="force",
            token_budget=128000,
        )
        print(f"    Full compact response:")
        print(f"    {compact_result}")
        print(f"\n    Type: {type(compact_result)}")
        print(f"    Keys: {compact_result.keys() if isinstance(compact_result, dict) else 'N/A'}")
        print(f"\n    result field: {compact_result.get('result', 'NOT FOUND')}")
        print(f"    result type: {type(compact_result.get('result', {}))}")
        
        # Check the structure
        result_field = compact_result.get("result", {})
        if isinstance(result_field, dict):
            print(f"\n    result keys: {result_field.keys()}")
            print(f"    compacted: {result_field.get('compacted', 'NOT FOUND')}")
            print(f"    ok: {result_field.get('ok', 'NOT FOUND')}")
            print(f"    reason: {result_field.get('reason', 'NOT FOUND')}")
        else:
            print(f"\n    ⚠️  result is not a dict: {type(result_field)}")
            print(f"    Value: {result_field}")
        
        # 5. Close session
        print("\n[5] Close session...")
        close_result = await client.close_session(session_id)
        print(f"    Close result: {close_result}")
        
        print("\n" + "=" * 60)
        print("Debug completed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(debug_compact())
