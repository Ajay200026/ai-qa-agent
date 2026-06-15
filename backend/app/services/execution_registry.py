import asyncio
import logging
from uuid import UUID

from playwright.async_api import BrowserContext

logger = logging.getLogger(__name__)


class ExecutionCancelled(Exception):
    """Raised when a user stops an in-progress execution."""


class ExecutionRegistry:
    def __init__(self) -> None:
        self._cancelled: set[UUID] = set()
        self._contexts: dict[UUID, BrowserContext] = {}
        self._tasks: dict[UUID, asyncio.Task] = {}

    def clear_cancel(self, execution_id: UUID) -> None:
        self._cancelled.discard(execution_id)

    def request_cancel(self, execution_id: UUID) -> None:
        self._cancelled.add(execution_id)
        logger.info("Cancel requested for execution %s", execution_id)

    def is_cancelled(self, execution_id: UUID) -> bool:
        return execution_id in self._cancelled

    def check_cancelled(self, execution_id: UUID | None) -> None:
        if execution_id and self.is_cancelled(execution_id):
            raise ExecutionCancelled(f"Execution {execution_id} was stopped by user")

    def register_task(self, execution_id: UUID, task: asyncio.Task) -> None:
        self._tasks[execution_id] = task

    def unregister_task(self, execution_id: UUID) -> None:
        self._tasks.pop(execution_id, None)

    def cancel_task(self, execution_id: UUID) -> None:
        task = self._tasks.get(execution_id)
        if task and not task.done():
            task.cancel()
            logger.info("Cancelled asyncio task for execution %s", execution_id)

    def register_context(self, execution_id: UUID, context: BrowserContext) -> None:
        self._contexts[execution_id] = context

    def unregister_context(self, execution_id: UUID) -> None:
        self._contexts.pop(execution_id, None)

    async def close_context(self, execution_id: UUID) -> None:
        context = self._contexts.pop(execution_id, None)
        if not context:
            return
        try:
            await context.close()
            logger.info("Closed browser context for execution %s", execution_id)
        except Exception as exc:
            logger.warning("Failed to close context for %s: %s", execution_id, exc)


execution_registry = ExecutionRegistry()
