import { useEffect, useRef, useCallback, useState } from "react";

const isDev = import.meta.env.DEV;

interface UseSSEOptions {
  /** URL to connect to. If null/undefined, no connection is made. */
  url: string | null | undefined;
  /** Called for each parsed SSE event. */
  onEvent: (event: { type: string; data: Record<string, unknown> }) => void;
  /** Called on connection error. */
  onError?: (error: Event) => void;
  /** Called when connection opens. */
  onOpen?: () => void;
  /** Called when the stream closes normally (hunt_complete/hunt_error). */
  onClose?: () => void;
}

/**
 * Generic SSE connection hook.
 * Manages EventSource lifecycle — connects when url is set, disconnects on unmount or url change.
 */
export function useSSE({ url, onEvent, onError, onOpen, onClose }: UseSSEOptions) {
  const sourceRef = useRef<EventSource | null>(null);
  const [connected, setConnected] = useState(false);
  const eventCountRef = useRef(0);

  const disconnect = useCallback(() => {
    if (sourceRef.current) {
      sourceRef.current.close();
      sourceRef.current = null;
    }
    setConnected(false);
  }, []);

  useEffect(() => {
    if (!url) {
      disconnect();
      return;
    }

    if (isDev) console.log("[SSE] Connecting to:", url);
    eventCountRef.current = 0;
    const es = new EventSource(url);
    sourceRef.current = es;

    es.onopen = () => {
      if (isDev) console.log("[SSE] Connected:", url);
      setConnected(true);
      onOpen?.();
    };

    es.onerror = (e) => {
      if (isDev) console.warn("[SSE] Error:", e, "readyState:", es.readyState);
      onError?.(e);
      // EventSource auto-reconnects on transient errors.
      // If readyState is CLOSED it won't reconnect.
      if (es.readyState === EventSource.CLOSED) {
        if (isDev) console.warn("[SSE] Connection closed permanently");
        setConnected(false);
      }
    };

    es.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        eventCountRef.current++;

        // Log first few events and lifecycle events for debugging
        if (isDev && (eventCountRef.current <= 5 || parsed.type !== "agent_thinking")) {
          console.log(`[SSE] Event #${eventCountRef.current}:`, parsed.type);
        }

        onEvent(parsed);

        // Auto-close on terminal events
        if (parsed.type === "hunt_complete" || parsed.type === "hunt_error") {
          if (isDev) console.log(`[SSE] Terminal: ${parsed.type} (total: ${eventCountRef.current} events)`);
          onClose?.();
          es.close();
          sourceRef.current = null;
          setConnected(false);
        }
      } catch {
        // Ignore heartbeats or malformed JSON
      }
    };

    return () => {
      if (isDev) console.log(`[SSE] Cleanup (received ${eventCountRef.current} events)`);
      es.close();
      sourceRef.current = null;
      setConnected(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url]);

  return { connected, disconnect };
}
