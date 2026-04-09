# -*- coding: utf-8 -*-
"""Test script for LCM HTTP client integration."""
import asyncio
import sys
sys.path.insert(0, "C:/workspace/CoPaw/src")

from copaw.agents.memory.lcm_client import LCMClient


async def test_lcm_client():
    """Test LCM client integration with HTTP server."""
    client = LCMClient(base_url="http://localhost:3721")
    
    print("=" * 60)
    print("LCM Client Integration Test")
    print("=" * 60)
    
    try:
        # 1. Health check
        print("\n[1] Health check...")
        health = await client.health_check()
        print(f"    Status: {health['status']}")
        print(f"    LCM Available: {health['lcmAvailable']}")
        
        # 2. Init session
        print("\n[2] Initialize session...")
        session_id = "python-test-session"
        init_result = await client.init(session_id, config={"dbPath": "data/python-test.db"})
        print(f"    Success: {init_result['success']}")
        print(f"    Message: {init_result['message']}")
        
        # 3. Ingest messages
        print("\n[3] Ingest messages...")
        messages = [
            {"role": "user", "content": "Hello, I want to learn Python programming"},
            {"role": "assistant", "content": "I can help you learn Python! Python is a versatile programming language."},
            {"role": "user", "content": "What are the basics I should start with?"},
            {"role": "assistant", "content": "Start with variables, data types, and control structures like loops and conditionals."},
        ]
        ingest_result = await client.ingest(session_id, messages)
        print(f"    Ingested: {ingest_result['ingested']} messages")
        
        # 4. Grep search
        print("\n[4] Search with grep...")
        grep_result = await client.grep(session_id, pattern="Python", mode="regex", scope="messages")
        print(f"    Total matches: {grep_result['totalMatches']}")
        for msg in grep_result['messages'][:3]:
            print(f"    - [{msg['role']}]: {msg['snippet'][:50]}...")
        
        # 5. Assemble context
        print("\n[5] Assemble context...")
        live_messages = [{"role": "user", "content": "Can you show me a simple example?"}]
        context_result = await client.assemble_context(session_id, live_messages, token_budget=4000)
        print(f"    Messages count: {len(context_result['messages'])}")
        print(f"    Estimated tokens: {context_result['estimatedTokens']}")
        
        # 6. Compact
        print("\n[6] Compact...")
        compact_result = await client.compact(session_id, mode="force", token_budget=2000)
        print(f"    Success: {compact_result['success']}")
        result = compact_result.get('result', {})
        print(f"    Compacted: {result.get('compacted', 'N/A')}")
        print(f"    Reason: {result.get('reason', 'N/A')}")
        
        # 7. Close session
        print("\n[7] Close session...")
        close_result = await client.close_session(session_id)
        print(f"    Closed: {close_result.get('success', True)}")
        
        print("\n" + "=" * 60)
        print("All tests completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_lcm_client())