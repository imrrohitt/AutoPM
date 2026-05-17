"use client";

import { useEffect, useRef } from "react";
import { ExternalLink, Play, Square } from "lucide-react";
import { toast } from "sonner";
import { AgentLogEntry } from "./AgentLogEntry";
import { AgentStatusBadge } from "./AgentStatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { agentApi } from "@/lib/api";
import { useAgentStream } from "@/lib/hooks/useAgentStream";
import type { AgentRun } from "@/lib/types";
import { getErrorMessage } from "@/lib/utils";

interface AgentRunPanelProps {
  ticketId: string;
  runs: AgentRun[];
  activeRunId: string | null;
  onRunStarted: (run: AgentRun) => void;
  onRunsRefresh: () => void;
  canRun: boolean;
}

export function AgentRunPanel({
  ticketId,
  runs,
  activeRunId,
  onRunStarted,
  onRunsRefresh,
  canRun,
}: AgentRunPanelProps) {
  const activeRun = runs.find((r) => r.id === activeRunId) || runs[0];
  const isRunning = activeRun?.status === "running" || activeRun?.status === "queued";
  const { logs, done, status, error, connected } = useAgentStream(
    activeRun?.id ?? null,
    isRunning
  );
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  const handleRun = async () => {
    try {
      const { data } = await agentApi.run(ticketId);
      onRunStarted(data);
      toast.success("Agent run queued");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  const handleCancel = async () => {
    if (!activeRun) return;
    try {
      await agentApi.cancel(activeRun.id);
      toast.success("Run cancelled");
      onRunsRefresh();
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">Agent runs</CardTitle>
        <div className="flex gap-2">
          {canRun && (
            <Button size="sm" onClick={handleRun} disabled={isRunning}>
              <Play className="h-4 w-4" />
              Run agent
            </Button>
          )}
          {isRunning && activeRun && (
            <Button size="sm" variant="outline" onClick={handleCancel}>
              <Square className="h-4 w-4" />
              Cancel
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {runs.length === 0 ? (
          <p className="text-sm text-muted-foreground">No agent runs yet.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {runs.map((run) => (
              <button
                key={run.id}
                type="button"
                onClick={() => onRunStarted(run)}
                className={`rounded-md border px-3 py-1.5 text-xs ${
                  activeRun?.id === run.id ? "border-primary bg-primary/10" : "border-border"
                }`}
              >
                <AgentStatusBadge status={run.status} />
              </button>
            ))}
          </div>
        )}

        {activeRun && (
          <>
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <AgentStatusBadge status={done && status ? status : activeRun.status} />
              {connected && <Spinner className="h-4 w-4" />}
              {activeRun.pr_url && (
                <a
                  href={activeRun.pr_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-primary hover:underline"
                >
                  PR #{activeRun.pr_number}
                  <ExternalLink className="h-3 w-3" />
                </a>
              )}
              {activeRun.branch_name && (
                <span className="font-mono text-xs text-muted-foreground">
                  {activeRun.branch_name}
                </span>
              )}
            </div>

            <div
              ref={scrollRef}
              className="max-h-96 overflow-y-auto rounded-lg border border-border bg-background/50 p-3"
            >
              {logs.length === 0 && !error && (
                <p className="text-xs text-muted-foreground">Waiting for logs…</p>
              )}
              {error && <p className="text-xs text-red-400">{error}</p>}
              {logs.map((log) => (
                <AgentLogEntry key={log.id} log={log} />
              ))}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
