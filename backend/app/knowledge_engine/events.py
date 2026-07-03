"""SSE event manager for knowledge scan progress."""

import asyncio
import logging
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


class ScanEventManager:
    def __init__(self) -> None:
        self._buffers: dict[UUID, list[dict[str, Any]]] = defaultdict(list)
        self._subscribers: dict[UUID, list[asyncio.Queue]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def publish(self, module_id: UUID, event: dict[str, Any]) -> None:
        payload = {**event, "timestamp": datetime.now(UTC).isoformat()}
        async with self._lock:
            buffer = self._buffers[module_id]
            buffer.append(payload)
            if len(buffer) > 100:
                del buffer[:-100]
            queues = list(self._subscribers.get(module_id, []))

        for queue in queues:
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    async def subscribe(self, module_id: UUID) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        async with self._lock:
            self._subscribers[module_id].append(queue)
            buffered = list(self._buffers.get(module_id, []))
        for event in buffered:
            await queue.put(event)
        return queue

    async def unsubscribe(self, module_id: UUID, queue: asyncio.Queue) -> None:
        async with self._lock:
            if module_id in self._subscribers:
                self._subscribers[module_id] = [
                    q for q in self._subscribers[module_id] if q != queue
                ]

    def clear(self, module_id: UUID) -> None:
        self._buffers.pop(module_id, None)


scan_event_manager = ScanEventManager()
