"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Bot, ExternalLink, Square } from "lucide-react";
import { toast } from "sonner";
import { AgentLogEntry } from "@/components/agent/AgentLogEntry";
import { AgentStatusBadge } from "@/components/agent/AgentStatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { agentApi, storiesApi } from "@/lib/api";
import { useAgentStream } from "@/lib/hooks/useAgentStream";
import type { AgentRun, Story } from "@/lib/types";
import { getErrorMessage } from "@/lib/utils";

export default function StoryAgentWorkspacePage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const storyId = params.storyId as string;
  const projectId = searchParams.get("projectId") || "";
  const runIdParam = searchParams.get("runId");

  const [story, setStory] = useState<Story | null>(null);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [activeRunId, setActiveRunId] = useState<string | null>(runIdParam);
  const [loading, setLoading] = useState(true);

  const activeRun = runs.find((r) => r.id === activeRunId) || runs[0];
  const isRunning =
    activeRun?.status === "running" || activeRun?.status === "queued";

  const { logs, done, status, error, connected, loadingHistory } = useAgentStream(
    activeRun?.id ?? null,
    isRunning
  );
  const scrollRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    if (!projectId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const [storyRes, runsRes] = await Promise.all([
        storiesApi.get(projectId, storyId),
        agentApi.listStoryRuns(storyId),
      ]);
      setStory(storyRes.data);
      setRuns(runsRes.data);
      if (!activeRunId && runsRes.data.length > 0) {
        setActiveRunId(runsRes.data[0].id);
      }
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [projectId, storyId, activeRunId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  useEffect(() => {
    if (!isRunning) return;
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, [isRunning, load]);

  const handleCancel = async () => {
    if (!activeRun) return;
    try {
      await agentApi.cancel(activeRun.id);
      toast.success("Run cancelled");
      load();
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  const selectRun = (run: AgentRun) => {
    setActiveRunId(run.id);
    router.replace(
      `/stories/${storyId}/agent?projectId=${projectId}&runId=${run.id}`
    );
  };

  if (!projectId) {
    return (
      <p className="text-destructive">
        Missing projectId. Open from the story page.
      </p>
    );
  }

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner className="h-8 w-8" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link
            href={`/stories/${storyId}?projectId=${projectId}`}
            className="text-sm text-muted-foreground hover:text-primary"
          >
            ← Back to story
          </Link>
          <h2 className="mt-2 flex items-center gap-2 text-2xl font-bold">
            <Bot className="h-7 w-7 text-primary" />
            AI Agent Workspace
          </h2>
          {story && (
            <p className="mt-1 text-muted-foreground">{story.title}</p>
          )}
        </div>
        {isRunning && activeRun && (
          <Button variant="outline" size="sm" onClick={handleCancel}>
            <Square className="h-4 w-4" />
            Cancel run
          </Button>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Run history</CardTitle>
        </CardHeader>
        <CardContent>
          {runs.length === 0 ? (
            <p className="text-sm text-muted-foreground">No runs yet.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {runs.map((run) => (
                <button
                  key={run.id}
                  type="button"
                  onClick={() => selectRun(run)}
                  className={`rounded-lg border px-3 py-2 text-left text-xs transition-colors ${
                    activeRun?.id === run.id
                      ? "border-primary bg-primary/10"
                      : "border-border hover:bg-accent"
                  }`}
                >
                  <AgentStatusBadge status={run.status} />
                  <p className="mt-1 font-mono text-muted-foreground">
                    {new Date(run.created_at).toLocaleString()}
                  </p>
                </button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {activeRun && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Live progress</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              <AgentStatusBadge
                status={done && status ? status : activeRun.status}
              />
              {connected && <Spinner className="h-4 w-4" />}
              {activeRun.branch_name && (
                <Badge variant="outline" className="font-mono text-xs">
                  {activeRun.branch_name}
                </Badge>
              )}
              {activeRun.pr_url && (
                <a
                  href={activeRun.pr_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-sm text-primary hover:underline"
                >
                  PR #{activeRun.pr_number}
                  <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </div>

            {activeRun.error_message && (
              <p className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
                {activeRun.error_message}
              </p>
            )}

            <div
              ref={scrollRef}
              className="max-h-[32rem] overflow-y-auto rounded-lg border border-border bg-background/60 p-4 font-mono text-sm"
            >
              {loadingHistory && logs.length === 0 && (
                <p className="text-muted-foreground">Loading run logs…</p>
              )}
              {!loadingHistory && logs.length === 0 && !error && isRunning && (
                <p className="text-muted-foreground">Waiting for agent logs…</p>
              )}
              {!loadingHistory && logs.length === 0 && !error && !isRunning && (
                <p className="text-muted-foreground">No logs recorded for this run.</p>
              )}
              {!loadingHistory && logs.length > 0 && (
                <p className="mb-2 text-[10px] text-muted-foreground">
                  {logs.length} step{logs.length === 1 ? "" : "s"} recorded
                </p>
              )}
              {error && <p className="text-red-400">{error}</p>}
              {logs.map((log) => (
                <AgentLogEntry key={log.id} log={log} />
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {story?.acceptance_criteria && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Acceptance criteria</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="whitespace-pre-wrap text-sm text-muted-foreground">
              {story.acceptance_criteria}
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
