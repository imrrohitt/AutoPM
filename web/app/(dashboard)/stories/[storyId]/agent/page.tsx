"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Bot, ExternalLink, Play, Square } from "lucide-react";
import { toast } from "sonner";
import { AgentActivityFeed } from "@/components/agent/AgentActivityFeed";
import { AgentCodePanel } from "@/components/agent/AgentCodePanel";
import { AgentRunHistorySidebar } from "@/components/agent/AgentRunHistorySidebar";
import { AgentStatusBadge } from "@/components/agent/AgentStatusBadge";
import { StoryAgentSchedulePanel } from "@/components/agent/StoryAgentSchedulePanel";
import { BackLink } from "@/components/ui/back-link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingPage } from "@/components/ui/loading-page";
import { Spinner } from "@/components/ui/spinner";
import { agentApi, storiesApi } from "@/lib/api";
import { useAgentStream } from "@/lib/hooks/useAgentStream";
import { useAgentWorkspace } from "@/lib/hooks/useAgentWorkspace";
import { usePagination } from "@/lib/hooks/usePagination";
import type { AgentRun, Story } from "@/lib/types";
import { getErrorMessage } from "@/lib/utils";

const RUNS_PAGE_SIZE = 8;

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
  const [starting, setStarting] = useState(false);

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

  const handleStartRun = async () => {
    if (!projectId) return;
    setStarting(true);
    try {
      const { data } = await agentApi.runStory(storyId, projectId);
      toast.success("Agent started");
      setActiveRunId(data.id);
      router.replace(
        `/stories/${storyId}/agent?projectId=${projectId}&runId=${data.id}`
      );
      await load();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setStarting(false);
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
    <article className="flex min-h-[calc(100vh-5rem)] flex-col gap-5">
      {/* Header */}
      <header className="shrink-0 space-y-3">
        <BackLink href={`/stories/${storyId}?projectId=${projectId}`}>
          Back to story
        </BackLink>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium uppercase tracking-wider text-primary">
              Agent workspace
            </p>
            <h1 className="mt-1 truncate text-2xl font-bold tracking-tight text-foreground">
              {story?.title ?? "Story"}
            </h1>
            {story?.description && (
              <p className="mt-1 line-clamp-2 max-w-2xl text-sm text-muted-foreground">
                {story.description}
              </p>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {!isRunning && (
              <Button size="sm" onClick={handleStartRun} disabled={starting}>
                {starting ? (
                  <Spinner />
                ) : (
                  <>
                    <Play className="h-4 w-4" />
                    Run now
                  </>
                )}
              </Button>
            )}
            {isRunning && activeRun && (
              <Button variant="outline" size="sm" onClick={handleCancel}>
                <Square className="h-4 w-4" />
                Cancel
              </Button>
            )}
          </div>
        </div>
        {story?.acceptance_criteria && (
          <details className="rounded-lg border border-border/80 bg-muted/40 px-4 py-2.5 text-sm">
            <summary className="cursor-pointer text-xs font-medium text-muted-foreground">
              Acceptance criteria
            </summary>
            <p className="mt-2 whitespace-pre-wrap text-sm text-foreground/80">
              {story.acceptance_criteria}
            </p>
          </details>
        )}
      </header>

      {/* Sidebar + main */}
      <div className="grid min-h-0 flex-1 gap-5 lg:grid-cols-[minmax(260px,300px)_1fr] lg:items-start">
        <aside className="flex flex-col gap-4 lg:sticky lg:top-4 lg:max-h-[calc(100vh-8rem)] lg:overflow-y-auto">
          <AgentRunHistorySidebar
            runs={paginatedRuns}
            activeRunId={activeRun?.id}
            onSelect={selectRun}
            page={page}
            totalPages={totalPages}
            totalItems={totalItems}
            pageSize={RUNS_PAGE_SIZE}
            onPageChange={goToPage}
          />
          <StoryAgentSchedulePanel
            storyId={storyId}
            projectId={projectId}
            onScheduledRun={refreshRuns}
          />
        </aside>

        <section className="flex min-h-[min(640px,calc(100vh-12rem))] min-w-0 flex-col">
          {displayRun ? (
            <div className="flex h-full min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-border bg-card shadow-sm">
              <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-border/80 bg-muted/30 px-4 py-2.5">
                <Bot className="h-4 w-4 text-primary" />
                <AgentStatusBadge status={displayRun.status} />
                {connected && (
                  <span className="flex items-center gap-1.5 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                    <span className="relative flex h-1.5 w-1.5">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-60" />
                      <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-primary" />
                    </span>
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
                    className="ml-auto flex items-center gap-1 text-sm font-medium text-primary hover:underline"
                  >
                    PR #{displayRun.pr_number}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                )}
              </div>
              {displayRun.error_message && (
                <p className="shrink-0 border-b border-destructive/20 bg-destructive/5 px-4 py-2 text-sm text-destructive">
                  {displayRun.error_message}
                </p>
              )}

              <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[minmax(260px,36%)_1fr]">
                <div
                  ref={activityScrollRef}
                  className="min-h-[240px] border-b border-border lg:min-h-0 lg:border-b-0 lg:border-r"
                >
                  <AgentActivityFeed
                    logs={logs}
                    loading={loadingHistory}
                    error={error}
                    isRunning={isRunning}
                  />
                </div>
                <div className="min-h-[320px] lg:min-h-0">
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
          ) : (
            <EmptyState
              icon={Bot}
              title="No agent runs yet"
              description="Run the agent now to implement this story, or schedule automatic runs from the sidebar."
              action={
                <Button onClick={handleStartRun} disabled={starting}>
                  {starting ? <Spinner /> : (
                    <>
                      <Play className="h-4 w-4" />
                      Run now
                    </>
                  )}
                </Button>
              }
              className="h-full min-h-[400px] flex-1"
            />
          )}
        </section>
      </div>
    </article>
  );
}
