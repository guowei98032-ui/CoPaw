# -*- coding: utf-8 -*-
"""
Debug test to check what legacyParams are being passed to the engine.
"""
import asyncio
import aiohttp
import json

async def test_legacy_params():
    """Test what parameters are being sent to the server."""
    print("=" * 70)
    print("Debug: Testing legacyParams transmission")
    print("=" * 70)
    print()
    
    # Test 1: Check health endpoint
    print("Test 1: Health check")
    async with aiohttp.ClientSession() as session:
        async with session.get("http://localhost:3721/health") as resp:
            health = await resp.json()
            print(f"  Provider: {health.get('config', {}).get('provider')}")
            print(f"  Model: {health.get('config', {}).get('model')}")
            print()
        
        # Test 2: Initialize with explicit legacyParams
        print("Test 2: Initialize with explicit legacyParams")
        config = {
            "freshTailCount": 32,
            "contextThreshold": 0.75,
            "maxContextTokens": 128000,
            "dbPath": "./data/test_debug.db",
            "llmConfig": {
                "provider": "openai",
                "model": "qwen3.5-plus",
                "api_key": "sk-sp-4fe2f039355645e18038499216be4fa5",
                "base_url": "https://coding.dashscope.aliyuncs.com/v1",
            },
            # Add legacyParams explicitly
            "legacyParams": {
                "provider": "openai",
                "model": "qwen3.5-plus",
                "config": {
                    "plugins": {
                        "entries": {
                            "lossless-claw": {
                                "config": {
                                    "summaryProvider": "openai",
                                    "summaryModel": "qwen3.5-plus",
                                }
                            }
                        }
                    },
                    "agents": {
                        "defaults": {
                            "model": "qwen3.5-plus",
                            "compaction": {
                                "model": "qwen3.5-plus",
                            }
                        }
                    }
                }
            }
        }
        
        async with session.post(
            "http://localhost:3721/init",
            json={"sessionId": "test_debug", "config": config}
        ) as resp:
            init_result = await resp.json()
            print(f"  Init result: {init_result}")
            print()
        
        # Test 3: Ingest a message
        print("Test 3: Ingest message")
        messages = [
            {
                "id": "msg_1",
                "role": "user",
                "content": [{"type": "text", "text": "测试消息"}]
            }
        ]
        
        async with session.post(
            "http://localhost:3721/ingest",
            json={"sessionId": "test_debug", "messages": messages}
        ) as resp:
            ingest_result = await resp.json()
            print(f"  Ingest result: {ingest_result}")
            print()
        
        # Test 4: Compact with explicit legacyParams
        print("Test 4: Compact with explicit legacyParams")
        compact_config = {
            "sessionId": "test_debug",
            "mode": "force",
            "tokenBudget": 10000,
            "legacyParams": {
                "provider": "openai",
                "model": "qwen3.5-plus",
                "config": {
                    "plugins": {
                        "entries": {
                            "lossless-claw": {
                                "config": {
                                    "summaryProvider": "openai",
                                    "summaryModel": "qwen3.5-plus",
                                }
                            }
                        }
                    }
                }
            }
        }
        
        async with session.post(
            "http://localhost:3721/compact",
            json=compact_config
        ) as resp:
            compact_result = await resp.json()
            print(f"  Compact result: {json.dumps(compact_result, indent=4, ensure_ascii=False)}")
            print()
        
        # Test 5: Close session
        print("Test 5: Close session")
        async with session.post(
            "http://localhost:3721/close",
            json={"sessionId": "test_debug"}
        ) as resp:
            close_result = await resp.json()
            print(f"  Close result: {close_result}")
            print()
    
    print("=" * 70)
    print("Test completed. Check server console for any errors.")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(test_legacy_params())
