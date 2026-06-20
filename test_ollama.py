import asyncio
import httpx

async def main():
    payload = {
        "model": "llama3.1:8b",
        "prompt": "Hello",
        "stream": False,
        "format": "json"
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post("http://localhost:11434/api/generate", json=payload)
            resp.raise_for_status()
            print("Success:", resp.json())
    except Exception as exc:
        print("Error type:", type(exc))
        print("Error details:", repr(exc))

asyncio.run(main())
