"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Bot, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { TicketCard } from "@/components/tickets/TicketCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { Spinner } from "@/components/ui/spinner";
import { agentApi, storiesApi, ticketsApi } from "@/lib/api";
import { useAuth } from "@/lib/hooks/useAuth";
import { useProject } from "@/lib/hooks/useProjects";
import { canCreateTicket, canEnableAgent } from "@/lib/permissions";
import type { Story, Ticket } from "@/lib/types";
import { getErrorMessage } from "@/lib/utils";

export default function StoryDetailPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const router = useRouter();
  const storyId = params.storyId as string;
  const projectId = searchParams.get("projectId") || "";
  const { user } = useAuth();
  const { project } = useProject(projectId);
  const [story, setStory] = useState<Story | null>(null);
  const [tickets, setTickets] = useState<Ticket[]>([]);
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
      <p className="text-destructive">
        Missing projectId. Open this story from a project page.
      </p>
    );
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-32" />
      </div>
    );
  }

  if (!story) {
    return <p className="text-destructive">Story not found</p>;
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          href={`/projects/${projectId}`}
          className="text-sm text-muted-foreground hover:text-primary"
        >
          ← Back to project
        </Link>
        <h2 className="mt-2 text-2xl font-bold">{story.title}</h2>
        <div className="mt-2 flex gap-2">
          <Badge variant="outline" className="capitalize">
            {story.status}
          </Badge>
          <Badge variant="secondary" className="capitalize">
            {story.priority}
          </Badge>
        </div>
        {story.description && (
          <p className="mt-3 text-muted-foreground">{story.description}</p>
        )}
        {story.acceptance_criteria && (
          <Card className="mt-4">
            <CardHeader>
              <CardTitle className="text-sm">Acceptance criteria</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="whitespace-pre-wrap text-sm">{story.acceptance_criteria}</p>
            </CardContent>
          </Card>
        )}
        {canStartAgent && (
          <div className="mt-4 flex flex-wrap gap-2">
            <Button onClick={handleStartAiWork} disabled={startingAgent}>
              {startingAgent ? (
                <Spinner />
              ) : (
                <>
                  <Bot className="mr-2 h-4 w-4" />
                  Start AI work
                </>
              )}
            </Button>
            <Link
              href={`/stories/${storyId}/agent?projectId=${projectId}`}
              className="inline-flex h-10 items-center rounded-md border border-input px-4 text-sm hover:bg-accent"
            >
              View agent workspace
            </Link>
          </div>
        )}
      </div>

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
        <p className="text-sm text-muted-foreground">No tickets yet.</p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {tickets.map((t) => (
            <TicketCard key={t.id} ticket={t} />
          ))}
        </div>
      )}
    </div>
  );
}
