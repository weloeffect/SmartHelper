"""Check QwenCloud credentials and realtime session setup without sending audio."""

import asyncio
import json

from websockets.asyncio.client import connect

from qwen_realtime import realtime_config, session_update


async def main() -> None:
    config = realtime_config()
    if not config.ready:
        print("QwenCloud API key is missing or still a placeholder in .env.")
        return
    try:
        async with connect(
            config.url,
            additional_headers={"Authorization": f"Bearer {config.api_key}"},
            open_timeout=12,
            max_size=2_000_000,
        ) as socket:
            await socket.send(json.dumps(session_update(config)))
            for _ in range(5):
                event = json.loads(await asyncio.wait_for(socket.recv(), timeout=12))
                if event.get("type") == "session.updated":
                    print("QwenCloud realtime session connected and configured.")
                    return
                if event.get("type") == "error":
                    print("QwenCloud rejected the realtime session configuration.")
                    return
            print("QwenCloud connected but did not confirm session configuration.")
    except Exception as exc:
        print(f"QwenCloud realtime connection failed: {type(exc).__name__}.")


if __name__ == "__main__":
    asyncio.run(main())
