import asyncio
import logging
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import WebSocket

from app.schemas.execution import ExecutionEvent

logger = logging.getLogger(__name__)


class EventManager:
    def __init__(self) -> None:
        self._connections: dict[UUID, list[WebSocket]] = defaultdict(list)
        self._buffers: dict[UUID, list[ExecutionEvent]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def connect(self, execution_id: UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[execution_id].append(websocket)
            buffered = list(self._buffers.get(execution_id, []))
        logger.info("WebSocket connected for execution %s", execution_id)
        for event in buffered:
            try:
                await websocket.send_json(event.model_dump(mode="json"))
            except Exception:
                await self.disconnect(execution_id, websocket)
                return

    async def disconnect(self, execution_id: UUID, websocket: WebSocket) -> None:
        async with self._lock:
            if execution_id in self._connections:
                self._connections[execution_id] = [
                    ws for ws in self._connections[execution_id] if ws != websocket
                ]
                if not self._connections[execution_id]:
                    del self._connections[execution_id]

    def clear_buffer(self, execution_id: UUID) -> None:
        self._buffers.pop(execution_id, None)

    async def publish(self, execution_id: UUID, event: ExecutionEvent) -> None:
        payload = event.model_dump(mode="json")
        async with self._lock:
            buffer = self._buffers.setdefault(execution_id, [])
            buffer.append(event)
            if len(buffer) > 200:
                del buffer[:-200]
            connections = list(self._connections.get(execution_id, []))

        dead: list[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)

        for ws in dead:
            await self.disconnect(execution_id, ws)

    async def emit(
        self,
        execution_id: UUID,
        event_type: str,
        *,
        step_seq: int | None = None,
        step_name: str | None = None,
        status: str | None = None,
        message: str | None = None,
        screenshot_path: str | None = None,
    ) -> None:
        event = ExecutionEvent(
            execution_id=execution_id,
            event_type=event_type,
            step_seq=step_seq,
            step_name=step_name,
            status=status,
            message=message,
            screenshot_path=screenshot_path,
            timestamp=datetime.now(UTC),
        )
        await self.publish(execution_id, event)


event_manager = EventManager()
