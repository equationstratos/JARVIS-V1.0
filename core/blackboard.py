from typing import Any, Dict
import asyncio

class Blackboard:
    def __init__(self):
        self.data: Dict[str, Any] = {}
        self.lock = asyncio.Lock()

    async def set(self, key: str, value: Any):
        async with self.lock:
            self.data[key] = value

    async def get(self, key: str, default: Any = None) -> Any:
        async with self.lock:
            return self.data.get(key, default)

    async def get_all(self) -> Dict[str, Any]:
        async with self.lock:
            return self.data.copy()
