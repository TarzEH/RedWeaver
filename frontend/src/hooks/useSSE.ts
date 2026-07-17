import { useEffect, useRef, useCallback, useState } from "react";

const isDev = import.meta.env.DEV;

interface UseSSEOptions {
  /** WebSocket URL to connect to. If null/undefined, no connection is made. */
  url: string | null | undefined;
  /** Called for each parsed event ({type, data, ...envelope}). */
  onEvent: (event: { type: string; data: Record<string, unknown> }) => void;
  /** Called on connection error. */
  onError?: (error: Event) => void;
  /** Called when connection opens. */
  onOpen?: () => void;
  /** Called when the stream closes normally (hunt_complete/hunt_error). */
  onClose?: () => void;
}

/**
 * Run event-stream hook (Django Channels WebSocket).
 *
 * Keeps the original `useSSE` interface so callers are unchanged. Adds
 * exponential-backoff reconnect (WebSocket has none) and resumes from the
 * last received `seq` so the server replays only the gap from EventLog.
 */
export function useSSE({ url, onEvent, onError, onOpen, onClose }: UseSSEOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const reconnectRef = useRef<number | null>(null);
  const backoffRef = useRef(1000);
  const closedTerminalRef = useRef(false);
  const unmountedRef = useRef(false);
  const lastSeqRef = useRef(0);
  const eventCountRef = useRef(0);

  const disconnect = useCallback(() => {
    if (reconnectRef.current) {
      clearTimeout(reconnectRef.current);
      reconnectRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setConnected(false);
  }, []);

  useEffect(() => {
    unmountedRef.current = false;
    closedTerminalRef.current = false;
    backoffRef.current = 1000;
    lastSeqRef.current = 0;
    eventCountRef.current = 0;

    if (!url) {
      disconnect();
      return;
    }

    const connect = () => {
      const sep = url.includes("?") ? "&" : "?";
      const fullUrl =
        lastSeqRef.current > 0 ? `${url}${sep}last_seq=${lastSeqRef.current}` : url;
      if (isDev) console.log("[WS] Connecting:", fullUrl);
      const ws = new WebSocket(fullUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (isDev) console.log("[WS] Connected");
        setConnected(true);
        backoffRef.current = 1000;
        onOpen?.();
      };

      ws.onmessage = (ev) => {
        try {
          const parsed = JSON.parse(ev.data);
          if (typeof parsed.seq === "number") lastSeqRef.current = parsed.seq;
          if (parsed.type === "replay_complete") return;

          eventCountRef.current++;
          if (isDev && (eventCountRef.current <= 5 || parsed.type !== "agent_thinking")) {
            console.log(`[WS] Event #${eventCountRef.current}:`, parsed.type);
          }

          onEvent(parsed);

          if (parsed.type === "hunt_complete" || parsed.type === "hunt_error") {
            closedTerminalRef.current = true;
            onClose?.();
            ws.close();
          }
        } catch {
          /* ignore malformed frames */
        }
      };

      ws.onerror = (e) => {
        if (isDev) console.warn("[WS] Error:", e);
        onError?.(e);
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        if (!closedTerminalRef.current && !unmountedRef.current) {
          const delay = Math.min(backoffRef.current, 10000);
          if (isDev) console.log(`[WS] Reconnecting in ${delay}ms`);
          reconnectRef.current = window.setTimeout(connect, delay);
          backoffRef.current = Math.min(backoffRef.current * 2, 10000);
        }
      };
    };

    connect();

    return () => {
      unmountedRef.current = true;
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      setConnected(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url]);

  return { connected, disconnect };
}
