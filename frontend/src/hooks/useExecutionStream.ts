"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ExecutionEvent } from "@/lib/types";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/api/v1";

export function useExecutionStream(executionId: string | null) {
  const [events, setEvents] = useState<ExecutionEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    if (!executionId) return;

    const ws = new WebSocket(`${WS_URL}/executions/${executionId}/stream`);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (event) => {
      const data: ExecutionEvent = JSON.parse(event.data);
      setEvents((prev) => [...prev, data]);
    };
    ws.onerror = () => setConnected(false);

    return () => {
      ws.close();
    };
  }, [executionId]);

  const clearEvents = useCallback(() => {
    setEvents([]);
  }, []);

  useEffect(() => {
    setEvents([]);
    const cleanup = connect();
    return () => {
      cleanup?.();
      wsRef.current?.close();
    };
  }, [connect]);

  return { events, connected, clearEvents };
}
