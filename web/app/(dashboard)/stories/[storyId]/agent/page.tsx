"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Bot, ExternalLink, Square } from "lucide-react";
import { toast } from "sonner";
import { AgentLogEntry } from "@/components/agent/AgentLogEntry";
import { AgentStatusBadge } from "@/components/agent/AgentStatusBadge";
import { BackLink } from "@/components/ui/back-link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LoadingPage } from "@/components/ui/loading-page";
import { Pagination } from "@/components/ui/pagination";
import { Spinner } from "@/components/ui/spinner";
import { agentApi, storiesApi } from "@/lib/api";
import { useAgentStream } from "@/lib/hooks/useAgentStream";
import { usePagination } from "@/lib/hooks/usePagination";
import type { AgentRun, Story } from "@/lib/types";
import { getErrorMessage } from "@/lib/utils";

const RUNS_PAGE_SIZE = 6;

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

  const { paginatedItems: paginatedRuns, page, totalPages, totalItems, goToPage } =
    usePagination(runs, RUNS_PAGE_SIZE);

  const activeRun = runs.find((r) => r.id === activeRunId) || runs[0];
  const isRunning =
    activeRun?.status === "running" || activeRun?.status === "queued";

  const refreshRuns = useCallback(async () => {
    if (!projectId) return;
    try {
      const runsRes = await agentApi.listStoryRuns(storyId);
      setRuns(runsRes.data);
    } catch {
      /* keep last list */
    }
  }, [projectId, storyId]);

  const { logs, done, status, runMeta, error, connected, loadingHistory } =
    useAgentStream(activeRun?.id ?? null, isRunning, refreshRuns);
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

  const displayRun = activeRun
    ? {
        ...activeRun,
        status: done && status ? status : activeRun.status,
        pr_url: runMeta?.pr_url ?? activeRun.pr_url,
        pr_number: runMeta?.pr_number ?? activeRun.pr_number,
        branch_name: runMeta?.branch_name ?? activeRun.branch_name,
        error_message: runMeta?.error_message ?? activeRun.error_message,
      }
    : null;

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
      <p className="rounded-lg border border-destructive/30 bg-red-50 px-4 py-3 text-sm text-destructive">
        Missing projectId. Open from the story page.
      </p>
    );
  }

  if (loading) return <LoadingPage label="Loading agent workspace…" />;

  return (
    <article className="mx-auto max-w-4xl space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <BackLink href={`/stories/${storyId}?projectId=${projectId}`}>
            Back to story
          </BackLink>
          <h2 className="mt-3 flex items-center gap-2 text-2xl font-bold tracking-tight">
            <Bot className="h-7 w-7 text-primary" />
            AI Agent Workspace
          </h2>
          {story && <p className="mt-1 text-muted-foreground">{story.title}</p>}
        </div>
        {isRunning && activeRun && (
          <Button variant="outline" size="sm" onClick={handleCancel}>
            <Square className="h-4 w-4" />
            Cancel run
          </Button>
        )}
      </header>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Run history</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {runs.length === 0 ? (
            <p className="text-sm text-muted-foreground">No runs yet.</p>
          ) : (
            <>
              <ul className="grid gap-2 sm:grid-cols-2">
                {paginatedRuns.map((run) => (
                  <li key={run.id}>
                    <button
                      type="button"
                      onClick={() => selectRun(run)}
                      className={`w-full rounded-lg border px-3 py-2.5 text-left text-xs transition-all ${
                        activeRun?.id === run.id
                          ? "border-primary bg-primary/5 shadow-sm"
                          : "border-border hover:border-primary/30 hover:bg-accent"
                      }`}
                    >
                      <AgentStatusBadge status={run.status} />
                      <p className="mt-1.5 font-mono text-muted-foreground">
                        {new Date(run.created_at).toLocaleString()}
                      </p>
                    </button>
                  </li>
                ))}
              </ul>
              <Pagination
                page={page}
                totalPages={totalPages}
                totalItems={totalItems}
                pageSize={RUNS_PAGE_SIZE}
                onPageChange={goToPage}
              />
            </>
          )}
        </CardContent>
      </Card>

      {displayRun && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Live progress</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              <AgentStatusBadge status={displayRun.status} />
              {connected && (
                <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Spinner className="h-3 w-3 text-primary" />
                  Live
                </span>
              )}
              {displayRun.branch_name && (
                <Badge variant="outline" className="font-mono text-xs">
                  {displayRun.branch_name}
                </Badge>
              )}
              {displayRun.pr_url && (
                <a
                  href={displayRun.pr_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-sm font-medium text-primary hover:underline"
                >
                  PR #{displayRun.pr_number}
                  <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </div>

            {displayRun.error_message && (
              <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                {displayRun.error_message}
              </p>
            )}

            <div
              ref={scrollRef}
              className="scrollbar-thin max-h-[32rem] overflow-y-auto rounded-lg border border-border bg-slate-50 p-4 font-mono text-sm"
            >
              {loadingHistory && logs.length === 0 && (
                <p className="flex items-center gap-2 text-muted-foreground">
                  <Spinner className="h-4 w-4" />
                  Loading run logs…
                </p>
              )}
              {!loadingHistory && logs.length === 0 && !error && isRunning && (
                <p className="text-muted-foreground">Waiting for agent logs…</p>
              )}
              {!loadingHistory && logs.length === 0 && !error && !isRunning && (
                <p className="text-muted-foreground">No logs recorded for this run.</p>
              )}
              {!loadingHistory && logs.length > 0 && (
                <p className="mb-2 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                  {logs.length} step{logs.length === 1 ? "" : "s"} recorded
                </p>
              )}
              {error && <p className="text-red-600">{error}</p>}
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
    </article>
  );
}
