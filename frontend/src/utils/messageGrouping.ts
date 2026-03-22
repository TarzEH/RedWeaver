import type { RunMessage } from "../types/api";

export type MessageKind = "user" | "toolTrace" | "summary" | "error";

export interface MessageGroup {
  key: string;
  kind: MessageKind;
  messages: RunMessage[];
  collapsed?: boolean;
}

export function getMessageKind(msg: RunMessage): MessageKind {
  if (msg.role === "user") return "user";
  const c = (msg.content || "").trim();
  if (c.startsWith("Error:") || c.toLowerCase().startsWith("error:")) return "error";
  if (c === "No matches found") return "toolTrace";
  if ((c.startsWith("{") && c.includes("}")) || (c.startsWith("[") && c.includes("]")))
    return "toolTrace";
  if (
    msg.role === "assistant" &&
    (c.includes("###") ||
      c.includes("Findings:") ||
      c.includes("**") ||
      (c.length > 200 && (c.includes("\n- ") || c.includes("\n\u2022 "))))
  )
    return "summary";
  if (msg.role === "assistant") return "toolTrace";
  return "toolTrace";
}

export function groupMessages(messages: RunMessage[]): MessageGroup[] {
  const groups: MessageGroup[] = [];
  let i = 0;
  while (i < messages.length) {
    const msg = messages[i];
    const kind = getMessageKind(msg);
    if (kind === "error") {
      const batch: RunMessage[] = [];
      while (
        i < messages.length &&
        getMessageKind(messages[i]) === "error" &&
        messages[i].content === msg.content
      ) {
        batch.push(messages[i]);
        i++;
      }
      groups.push({
        key: `err-${i}-${msg.content.slice(0, 30)}`,
        kind: "error",
        messages: batch,
      });
      continue;
    }
    if (kind === "toolTrace") {
      const batch: RunMessage[] = [];
      while (i < messages.length && getMessageKind(messages[i]) === "toolTrace") {
        batch.push(messages[i]);
        i++;
      }
      groups.push({ key: `trace-${i}`, kind: "toolTrace", messages: batch, collapsed: true });
      continue;
    }
    groups.push({ key: `msg-${i}`, kind, messages: [msg] });
    i++;
  }
  return groups;
}
