import { createContext, useContext, useMemo } from "react";
import { useRunStream } from "../hooks/useRunStream";
import type { ReasoningStep, GraphSSEState } from "../types/events";
import type { Finding } from "../types/api";

interface HuntContextValue {
  steps: ReasoningStep[];
  graphState: GraphSSEState;
  findings: Finding[];
  activeAgent: string | null;
  done: boolean;
  connected: boolean;
  reset: () => void;
  selectedRunId: string | null;
}

const HuntContext = createContext<HuntContextValue | null>(null);

export function useHuntContext(): HuntContextValue {
  const ctx = useContext(HuntContext);
  if (!ctx) throw new Error("useHuntContext must be used within HuntProvider");
  return ctx;
}

interface HuntProviderProps {
  selectedRunId: string | null;
  children: React.ReactNode;
}

export function HuntProvider({ selectedRunId, children }: HuntProviderProps) {
  const {
    steps, graphState, findings, activeAgent, done, connected, reset,
  } = useRunStream(selectedRunId, true);

  const value = useMemo<HuntContextValue>(
    () => ({ steps, graphState, findings, activeAgent, done, connected, reset, selectedRunId }),
    [steps, graphState, findings, activeAgent, done, connected, reset, selectedRunId]
  );

  return <HuntContext.Provider value={value}>{children}</HuntContext.Provider>;
}
