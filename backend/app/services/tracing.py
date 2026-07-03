"""Structured execution tracing."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any

from app.schemas.test_case import AssertionEvidence


class ExecutionTracer:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def record(
        self,
        *,
        event_type: str,
        tc_id: str | None = None,
        step_seq: int | None = None,
        action: str | None = None,
        status: str | None = None,
        detail: str = "",
        duration_ms: int | None = None,
        screenshot_path: str | None = None,
        extra: dict | None = None,
    ) -> None:
        self.events.append({
            "ts": time.time(),
            "event_type": event_type,
            "tc_id": tc_id,
            "step_seq": step_seq,
            "action": action,
            "status": status,
            "detail": detail,
            "duration_ms": duration_ms,
            "screenshot_path": screenshot_path,
            **(extra or {}),
        })

    def record_assertion(self, tc_id: str, step_seq: int, evidence: AssertionEvidence) -> None:
        self.record(
            event_type="assertion",
            tc_id=tc_id,
            step_seq=step_seq,
            status="passed" if evidence.passed else "failed",
            detail=evidence.detail,
            screenshot_path=evidence.screenshot_path,
            extra={
                "kind": evidence.kind,
                "expected": evidence.expected,
                "actual": evidence.actual,
            },
        )

    @asynccontextmanager
    async def step_span(self, tc_id: str, step_seq: int, action: str):
        start = time.perf_counter()
        try:
            yield
            duration = int((time.perf_counter() - start) * 1000)
            self.record(
                event_type="step",
                tc_id=tc_id,
                step_seq=step_seq,
                action=action,
                status="passed",
                duration_ms=duration,
            )
        except Exception as exc:
            duration = int((time.perf_counter() - start) * 1000)
            self.record(
                event_type="step",
                tc_id=tc_id,
                step_seq=step_seq,
                action=action,
                status="failed",
                detail=str(exc),
                duration_ms=duration,
            )
            raise
