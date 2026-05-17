"use client";

import {
  AlertCircle,
  Brain,
  CheckCircle2,
  FileCode,
  FilePen,
  Info,
  AlertTriangle,
} from "lucide-react";
import { cn, formatDate } from "@/lib/utils";
import type { AgentLog } from "@/lib/types";

const levelIcon = {
  info: Info,
  warning: AlertTriangle,
  error: AlertCircle,
  success: CheckCircle2,
};

function stepLabel(step: string | null | undefined): string {
  if (!step) return "log";
  if (step.startsWith("tool:")) return step.replace("tool:", "").replace(/_/g, " ");
  if (step.startsWith("observe:")) return step.replace("observe:", "");
  if (step.startsWith("blocked:")) return "blocked";
  return step;
}

export function AgentActivityFeed({
  logs,
  loading,
  error,
  isRunning,
}: {
  logs: AgentLog[];
  loading: boolean;
  error: string | null;
  isRunning: boolean;
}) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="border-b border-border px-3 py-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Agent activity
        </p>
        {logs.length > 0 && (
          <p className="text-[10px] text-muted-foreground">
            {logs.length} event{logs.length === 1 ? "" : "s"}
          </p>
        )}
      </div>
      <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto p-2">
        {loading && logs.length === 0 && (
          <p className="px-2 py-4 text-xs text-muted-foreground">Loading…</p>
        )}
        {!loading && logs.length === 0 && !error && isRunning && (
          <p className="px-2 py-4 text-xs text-muted-foreground">Waiting for agent…</p>
        )}
        {!loading && logs.length === 0 && !error && !isRunning && (
          <p className="px-2 py-4 text-xs text-muted-foreground">No activity yet.</p>
        )}
        {error && <p className="px-2 py-2 text-xs text-red-600">{error}</p>}
        <div className="space-y-1">
          {logs.map((log) => (
            <ActivityItem key={log.id} log={log} />
          ))}
        </div>
      </div>
    </div>
  );
}

function ActivityItem({ log }: { log: AgentLog }) {
  const meta = log.metadata || {};
  const thought = (meta.thought as string) || "";
  const tool = meta.tool as string | undefined;
  const path =
    (meta.args as { path?: string } | undefined)?.path ||
    (meta.path as string | undefined);

  const isFileChange =
    log.step === "file_change" ||
    log.step === "commit" ||
    Boolean(path && log.step?.includes("write"));
  const isBlocked = log.step?.startsWith("blocked");
  const isReasoning =
    Boolean(thought) ||
    log.step === "tool:think" ||
    log.step === "thinking" ||
    log.step?.startsWith("tool:");

  const Icon = isFileChange
    ? FilePen
    : isReasoning
      ? Brain
      : levelIcon[log.level as keyof typeof levelIcon] || Info;

  const iconColor = isBlocked
    ? "text-red-500"
    : isFileChange
      ? "text-violet-500"
      : log.level === "success"
        ? "text-emerald-500"
        : log.level === "warning"
          ? "text-amber-500"
          : "text-blue-500";

  return (
    <div
      className={cn(
        "rounded-md border px-2 py-2 text-xs transition-colors",
        isBlocked
          ? "border-red-200 bg-red-50/80"
          : isFileChange
            ? "border-violet-200 bg-violet-50/50"
            : "border-transparent hover:border-border hover:bg-muted/40"
      )}
    >
      <div className="flex gap-2">
        <Icon className={cn("mt-0.5 h-3.5 w-3.5 shrink-0", iconColor)} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[10px] text-muted-foreground">
              {formatDate(log.created_at)}
            </span>
            <span className="rounded bg-muted px-1 py-0.5 text-[9px] font-medium uppercase tracking-wide">
              {stepLabel(log.step)}
            </span>
          </div>
          {thought && (
            <p className="mt-1 text-[11px] italic leading-snug text-muted-foreground">
              {thought}
            </p>
          )}
          {path && (
            <p className="mt-1 flex items-center gap-1 font-mono text-[11px] text-violet-700">
              <FileCode className="h-3 w-3 shrink-0" />
              {path}
            </p>
          )}
          <p className="mt-0.5 whitespace-pre-wrap leading-snug text-foreground">
            {log.message}
          </p>
          {tool && !path && (
            <p className="mt-0.5 text-[10px] text-muted-foreground">tool: {tool}</p>
          )}
        </div>
      </div>
    </div>
  );
}
