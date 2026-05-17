"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Bot, Plus, Ticket } from "lucide-react";
import { toast } from "sonner";
import { TicketCard } from "@/components/tickets/TicketCard";
import { BackLink } from "@/components/ui/back-link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingPage } from "@/components/ui/loading-page";
import { Pagination } from "@/components/ui/pagination";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { agentApi, storiesApi, ticketsApi } from "@/lib/api";
import { useAuth } from "@/lib/hooks/useAuth";
import { usePagination } from "@/lib/hooks/usePagination";
import { useProject } from "@/lib/hooks/useProjects";
import { canCreateTicket, canEnableAgent } from "@/lib/permissions";
import type { Story, Ticket as TicketType } from "@/lib/types";
import { getErrorMessage } from "@/lib/utils";

const TICKETS_PAGE_SIZE = 8;

export default function StoryDetailPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const storyId = params.storyId as string;
  const projectId = searchParams.get("projectId") || "";
  const { user } = useAuth();
  const { project } = useProject(projectId);
  const [story, setStory] = useState<Story | null>(null);
  const [tickets, setTickets] = useState<TicketType[]>([]);
  const [loading, setLoading] = useState(true);
  const [startingAgent, setStartingAgent] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    title: "",
    description: "",
    type: "task",
    priority: "medium",
  });

  const { paginatedItems, page, totalPages, totalItems, goToPage, resetPage } =
    usePagination(tickets, TICKETS_PAGE_SIZE);

  const canCreate =
    user && project ? canCreateTicket(user.global_role, project.my_role) : false;
  const canStartAgent =
    user && project ? canEnableAgent(user.global_role, project.my_role) : false;

  const load = useCallback(async () => {
    if (!projectId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const [storyRes, ticketsRes] = await Promise.all([
        storiesApi.get(projectId, storyId),
        ticketsApi.list(storyId),
      ]);
      setStory(storyRes.data);
      setTickets(ticketsRes.data);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [projectId, storyId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    resetPage();
  }, [tickets.length, resetPage]);

  const handleStartAiWork = async () => {
    if (!projectId) return;
    setStartingAgent(true);
    try {
      const { data } = await agentApi.runStory(storyId, projectId);
      toast.success("AI agent started — opening workspace");
      router.push(
        `/stories/${storyId}/agent?projectId=${projectId}&runId=${data.id}`
      );
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setStartingAgent(false);
    }
  };

  const handleCreateTicket = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      const { data } = await ticketsApi.create(storyId, form);
      toast.success("Ticket created");
      setForm({ title: "", description: "", type: "task", priority: "medium" });
      setShowForm(false);
      setTickets((prev) => [...prev, data]);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setCreating(false);
    }
  };

  if (!projectId) {
    return (
      <EmptyState
        title="Missing project context"
        description="Open this story from a project page."
        action={
          <Link href="/projects">
            <Button variant="outline">Go to projects</Button>
          </Link>
        }
      />
    );
  }

  if (loading) return <LoadingPage label="Loading story…" />;

  if (!story) {
    return (
      <EmptyState
        title="Story not found"
        description="This story may have been removed."
        action={
          <Link href={`/projects/${projectId}`}>
            <Button variant="outline">Back to project</Button>
          </Link>
        }
      />
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <BackLink href={`/projects/${projectId}`}>Back to project</BackLink>

      <header className="space-y-3">
        <h2 className="text-2xl font-bold tracking-tight">{story.title}</h2>
        <div className="flex flex-wrap gap-2">
          <Badge variant="outline" className="capitalize">
            {story.status}
          </Badge>
          <Badge variant="secondary" className="capitalize">
            {story.priority}
          </Badge>
        </div>
        {story.description && (
          <p className="text-muted-foreground">{story.description}</p>
        )}
        {story.acceptance_criteria && (
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
        {canStartAgent && (
          <div className="flex flex-wrap gap-2 pt-1">
            <Button onClick={handleStartAiWork} disabled={startingAgent}>
              {startingAgent ? (
                <Spinner />
              ) : (
                <>
                  <Bot className="h-4 w-4" />
                  Start AI work
                </>
              )}
            </Button>
            <Link href={`/stories/${storyId}/agent?projectId=${projectId}`}>
              <Button variant="outline">View agent workspace</Button>
            </Link>
          </div>
        )}
      </header>

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold">Tickets</h3>
          {canCreate && (
            <Button size="sm" onClick={() => setShowForm(!showForm)}>
              <Plus className="h-4 w-4" />
              New ticket
            </Button>
          )}
        </div>

        {showForm && canCreate && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Create ticket</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleCreateTicket} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="title">Title</Label>
                  <Input
                    id="title"
                    required
                    value={form.title}
                    onChange={(e) => setForm({ ...form, title: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="description">Description</Label>
                  <Textarea
                    id="description"
                    required
                    value={form.description}
                    onChange={(e) => setForm({ ...form, description: e.target.value })}
                  />
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label>Type</Label>
                    <Select
                      value={form.type}
                      onChange={(e) => setForm({ ...form, type: e.target.value })}
                    >
                      <option value="task">Task</option>
                      <option value="bug">Bug</option>
                      <option value="feature">Feature</option>
                      <option value="chore">Chore</option>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Priority</Label>
                    <Select
                      value={form.priority}
                      onChange={(e) => setForm({ ...form, priority: e.target.value })}
                    >
                      <option value="critical">Critical</option>
                      <option value="high">High</option>
                      <option value="medium">Medium</option>
                      <option value="low">Low</option>
                    </Select>
                  </div>
                </div>
                <Button type="submit" disabled={creating}>
                  {creating ? <Spinner /> : "Create ticket"}
                </Button>
              </form>
            </CardContent>
          </Card>
        )}

        {tickets.length === 0 ? (
          <EmptyState
            icon={Ticket}
            title="No tickets yet"
            description="Break this story into tickets for your team or agent."
            action={
              canCreate ? (
                <Button size="sm" onClick={() => setShowForm(true)}>
                  <Plus className="h-4 w-4" />
                  Create ticket
                </Button>
              ) : undefined
            }
          />
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-2">
              {paginatedItems.map((t) => (
                <TicketCard key={t.id} ticket={t} />
              ))}
            </div>
            <Pagination
              page={page}
              totalPages={totalPages}
              totalItems={totalItems}
              pageSize={TICKETS_PAGE_SIZE}
              onPageChange={goToPage}
            />
          </>
        )}
      </section>
    </div>
  );
}
