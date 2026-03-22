import { useEffect, useRef, useState } from "react";
import { CheckCircle2, ChevronDown, ChevronRight, Loader2, Shield, Zap } from "lucide-react";
import type { ReasoningStep } from "../../types/events";
import {
  EVENT_AGENT_START, EVENT_AGENT_THINKING, EVENT_TOOL_CALL,
  EVENT_TOOL_RESULT, EVENT_AGENT_COMPLETE, EVENT_FINDING,
} from "../../types/events";
import { AGENT_CONFIG, AGENT_DISPLAY_NAMES } from "../../config/agents";

function truncate(s: string, max: number): string {
  if (!s) return "";
  return s.length > max ? s.slice(0, max) + "\u2026" : s;
}

function smartFormat(raw: string, maxLen: number): string {
  if (!raw) return "";
  const trimmed = raw.trim();
  if (!trimmed.startsWith("{") && !trimmed.startsWith("[")) return truncate(trimmed, maxLen);
  try {
    const obj = JSON.parse(trimmed);
    if (Array.isArray(obj)) return truncate(obj.map(String).join(", "), maxLen) || "(empty)";
    if (typeof obj === "object" && obj !== null) {
      const parts: string[] = [];
      for (const [k, v] of Object.entries(obj as Record<string, unknown>)) {
        if (v === null || v === undefined || v === "") continue;
        if (Array.isArray(v)) {
          if (v.length === 0) continue;
          parts.push(`${k}=${v.slice(0, 3).map(String).join(",")}${v.length > 3 ? "\u2026" : ""}`);
        } else if (typeof v === "object") {
          parts.push(`${k}={\u2026}`);
        } else {
          parts.push(`${k}=${String(v).slice(0, 40)}`);
        }
      }
      return truncate(parts.join(" \u00b7 "), maxLen) || truncate(trimmed, maxLen);
    }
  } catch { /* not JSON */ }
  return truncate(trimmed, maxLen);
}

function StepLine({ step, isLatest }: { step: ReasoningStep; isLatest: boolean }) {
  let icon = "";
  let style = "text-rw-dim";
  let text = step.content;

  switch (step.type) {
    case EVENT_AGENT_THINKING:
      style = "text-rw-muted";
      break;
    case EVENT_TOOL_CALL:
      icon = "\u26a1";
      style = "text-blue-400 font-mono";
      text = `${step.tool || "tool"} \u2192 ${smartFormat(step.content, 100)}`;
      break;
    case EVENT_TOOL_RESULT:
      icon = "\u2192";
      style = "text-rw-dim font-mono";
      text = smartFormat(step.content, 120);
      break;
    case EVENT_AGENT_COMPLETE:
      icon = "\u2713";
      style = "text-emerald-400";
      text = truncate(step.content, 80);
      break;
    case EVENT_FINDING:
      icon = "\u2691";
      style = "text-amber-400";
      text = truncate(step.content, 100);
      break;
  }

  return (
    <div className={`px-3 py-0.5 text-[10px] leading-relaxed ${style} ${isLatest ? "animate-pulse-dot" : ""}`}>
      {icon && <span className="mr-1">{icon}</span>}
      {text}
    </div>
  );
}

interface AgentPanelProps {
  agentId: string;
  steps: ReasoningStep[];
  isActive: boolean;
  isCompleted: boolean;
  defaultExpanded: boolean;
}

export function AgentPanel({ agentId, steps, isActive, isCompleted, defaultExpanded }: AgentPanelProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const bottomRef = useRef<HTMLDivElement>(null);
  const config = AGENT_CONFIG[agentId];
  const displayName = AGENT_DISPLAY_NAMES[agentId] || agentId;

  useEffect(() => { if (isActive) setExpanded(true); }, [isActive]);

  useEffect(() => {
    if (isActive && expanded) bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [steps.length, isActive, expanded]);

  const toolCalls = steps.filter((s) => s.type === EVENT_TOOL_CALL).length;
  const findingCount = steps.filter((s) => s.type === EVENT_FINDING).length;
  const visibleSteps = steps.filter((s) => s.type !== EVENT_AGENT_START);

  return (
    <div className={`rounded-lg border overflow-hidden transition-all duration-200 ${
      isActive ? "border-rw-accent/30 bg-rw-accent/[0.03]"
      : isCompleted ? "border-emerald-500/15 bg-rw-elevated"
      : "border-rw-border bg-rw-elevated"
    }`}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-rw-surface/30 transition-colors"
      >
        {isCompleted ? <CheckCircle2 size={13} className="text-emerald-400 shrink-0" />
          : isActive ? <Loader2 size={13} className="text-rw-accent animate-spin shrink-0" />
          : <div className="w-3.5 h-3.5 rounded-full border border-rw-dim/30 shrink-0" />}

        <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: config?.color || "#64748b" }} />

        <span className={`text-xs font-medium flex-1 ${
          isActive ? "text-rw-accent" : isCompleted ? "text-rw-text" : "text-rw-dim"
        }`}>{displayName}</span>

        <div className="flex items-center gap-1.5 shrink-0">
          {toolCalls > 0 && (
            <span className="flex items-center gap-0.5 text-[10px] text-rw-dim"><Zap size={8} />{toolCalls}</span>
          )}
          {findingCount > 0 && (
            <span className="flex items-center gap-0.5 text-[10px] text-rw-accent font-medium"><Shield size={8} />{findingCount}</span>
          )}
          <span className="text-[10px] text-rw-dim">{visibleSteps.length}s</span>
        </div>

        {expanded ? <ChevronDown size={12} className="text-rw-dim" /> : <ChevronRight size={12} className="text-rw-dim" />}
      </button>

      {expanded && (
        <div className="border-t border-rw-border-subtle max-h-48 overflow-y-auto py-1">
          {visibleSteps.length === 0 ? (
            <div className="px-3 py-1.5 text-[10px] text-rw-dim">{isActive ? "Starting..." : "Waiting..."}</div>
          ) : (
            visibleSteps.map((step, i) => (
              <StepLine key={step.id || i} step={step} isLatest={i === visibleSteps.length - 1 && isActive} />
            ))
          )}
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  );
}
