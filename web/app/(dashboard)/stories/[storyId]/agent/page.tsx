"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Bot, ExternalLink, Square } from "lucide-react";
import { toast } from "sonner";
import { AgentActivityFeed } from "@/components/agent/AgentActivityFeed";
import { StoryAgentSchedulePanel } from "@/components/agent/StoryAgentSchedulePanel";
import { AgentCodePanel } from "@/components/agent/AgentCodePanel";
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
import { useAgentWorkspace } from "@/lib/hooks/useAgentWorkspace";
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

  const {
    workspace,
    changes,
    changeList,
    activeChange,
    selectedPath,
    setSelectedPath,
    treePaths,
    loading: workspaceLoading,
    mergeFileChange,
    reload: reloadWorkspace,
  } = useAgentWorkspace(activeRun?.id ?? null);

  const refreshRuns = useCallback(async () => {
    if (!projectId) return;
    try {
      const runsRes = await agentApi.listStoryRuns(storyId);
      setRuns(runsRes.data);
      reloadWorkspace();
    } catch {
      /* keep last list */
    }
  }, [projectId, storyId, reloadWorkspace]);

  const { logs, done, status, runMeta, error, connected, loadingHistory } =
    useAgentStream(
      activeRun?.id ?? null,
      isRunning,
      refreshRuns,
      mergeFileChange
    );

  const activityScrollRef = useRef<HTMLDivElement>(null);

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
    if (activityScrollRef.current) {
      activityScrollRef.current.scrollTop = activityScrollRef.current.scrollHeight;
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
    <article className="flex h-[calc(100vh-5rem)] max-w-[100vw] flex-col gap-4">
      <header className="flex shrink-0 flex-wrap items-start justify-between gap-4">
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

      <StoryAgentSchedulePanel
        storyId={storyId}
        projectId={projectId}
        onScheduledRun={refreshRuns}
      />

      <Card className="shrink-0">
        <CardHeader className="py-3">
          <CardTitle className="text-sm">Run history</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 pb-3 pt-0">
          {runs.length === 0 ? (
            <p className="text-sm text-muted-foreground">No runs yet.</p>
          ) : (
            <>
              <ul className="flex flex-wrap gap-2">
                {paginatedRuns.map((run) => (
                  <li key={run.id}>
                    <button
                      type="button"
                      onClick={() => selectRun(run)}
                      className={`rounded-lg border px-3 py-2 text-left text-xs transition-all ${
                        activeRun?.id === run.id
                          ? "border-primary bg-primary/5 shadow-sm"
                          : "border-border hover:border-primary/30 hover:bg-accent"
                      }`}
                    >
                      <AgentStatusBadge status={run.status} />
                      <p className="mt-1 font-mono text-muted-foreground">
                        {new Date(run.created_at).toLocaleString()}
                        {run.schedule_id && (
                          <span className="ml-1 text-primary">scheduled</span>
                        )}
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
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-border bg-card shadow-sm">
          <div className="flex shrink-0 flex-wrap items-center gap-3 border-b border-border px-4 py-2">
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
            {displayRun.error_message && (
              <p className="w-full text-sm text-red-600">{displayRun.error_message}</p>
            )}
          </div>

          <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[minmax(280px,38%)_1fr]">
            <div
              ref={activityScrollRef}
              className="min-h-[280px] border-b border-border lg:min-h-0 lg:border-b-0 lg:border-r"
            >
              <AgentActivityFeed
                logs={logs}
                loading={loadingHistory}
                error={error}
                isRunning={isRunning}
              />
            </div>
            <div className="min-h-[360px] lg:min-h-0">
              <AgentCodePanel
                repoOwner={workspace?.repo_owner}
                repoName={workspace?.repo_name}
                branch={workspace?.branch ?? displayRun.branch_name}
                treePaths={treePaths}
                changeList={changeList}
                changes={changes}
                selectedPath={selectedPath}
                onSelectPath={setSelectedPath}
                activeChange={activeChange}
                loading={workspaceLoading}
              />
            </div>
          </div>
        </div>
      )}

      {story?.acceptance_criteria && (
        <details className="shrink-0 rounded-lg border border-border bg-muted/30 px-4 py-2 text-sm">
          <summary className="cursor-pointer font-medium text-muted-foreground">
            Acceptance criteria
          </summary>
          <p className="mt-2 whitespace-pre-wrap text-muted-foreground">
            {story.acceptance_criteria}
          </p>
        </details>
      )}
    </article>
  );
}
