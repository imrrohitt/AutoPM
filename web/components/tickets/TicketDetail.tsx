"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { AgentRunPanel } from "@/components/agent/AgentRunPanel";
import { AgentToggle } from "./AgentToggle";
import { TicketStatusBadge } from "./TicketStatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Spinner } from "@/components/ui/spinner";
import { agentApi, ticketsApi } from "@/lib/api";
import { useAuth } from "@/lib/hooks/useAuth";
import { useProject } from "@/lib/hooks/useProjects";
import { useTicket } from "@/lib/hooks/useTickets";
import {
  canComment,
  canEnableAgent,
  canCreateTicket,
} from "@/lib/permissions";
import type { AgentRun, Comment } from "@/lib/types";
import { formatDate, getErrorMessage } from "@/lib/utils";

export function TicketDetail({ ticketId }: { ticketId: string }) {
  const { user } = useAuth();
  const { ticket, loading, error, refetch, setTicket } = useTicket(ticketId);
  const { project } = useProject(ticket?.project_id ?? "");
  const [comments, setComments] = useState<Comment[]>([]);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [commentBody, setCommentBody] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const projectRole = project?.my_role ?? null;
  const globalRole = user?.global_role ?? "member";

  const fetchComments = useCallback(async () => {
    if (!ticketId) return;
    try {
      const { data } = await ticketsApi.comments.list(ticketId);
      setComments(data);
    } catch {
      /* optional */
    }
  }, [ticketId]);

  const fetchRuns = useCallback(async () => {
    if (!ticketId) return;
    try {
      const { data } = await agentApi.listRuns(ticketId);
      setRuns(data);
      if (data.length && !activeRunId) setActiveRunId(data[0].id);
    } catch {
      /* optional */
    }
  }, [ticketId, activeRunId]);

  useEffect(() => {
    fetchComments();
    fetchRuns();
  }, [fetchComments, fetchRuns]);

  const handleAgentToggle = async (enabled: boolean) => {
    if (!ticket) return;
    try {
      if (enabled) {
        const { data } = await ticketsApi.enableAgent(ticket.id);
        setTicket(data);
      } else {
        const { data } = await ticketsApi.update(ticket.id, { agent_enabled: false });
        setTicket(data);
      }
      toast.success(enabled ? "Agent enabled" : "Agent disabled");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  const handleStatusChange = async (status: string) => {
    if (!ticket) return;
    try {
      const { data } = await ticketsApi.update(ticket.id, { status });
      setTicket(data);
      toast.success("Status updated");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  const handleComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!commentBody.trim()) return;
    setSubmitting(true);
    try {
      await ticketsApi.comments.create(ticketId, commentBody);
      setCommentBody("");
      await fetchComments();
      toast.success("Comment added");
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Spinner />
      </div>
    );
  }

  if (error || !ticket) {
    return <p className="text-destructive">{error || "Ticket not found"}</p>;
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          href={`/stories/${ticket.story_id}`}
          className="text-sm text-muted-foreground hover:text-primary"
        >
          ← Back to story
        </Link>
        <h2 className="mt-2 text-2xl font-bold">{ticket.title}</h2>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <TicketStatusBadge status={ticket.status} />
          <span className="text-sm capitalize text-muted-foreground">{ticket.type}</span>
          <span className="text-sm capitalize text-muted-foreground">{ticket.priority}</span>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Description</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="whitespace-pre-wrap text-sm">{ticket.description}</p>
        </CardContent>
      </Card>

      {canCreateTicket(globalRole, projectRole) && (
        <Card>
          <CardContent className="flex flex-wrap items-center gap-4 pt-6">
            <div className="space-y-1">
              <p className="text-sm font-medium">Status</p>
              <Select
                value={ticket.status}
                onChange={(e) => handleStatusChange(e.target.value)}
              >
                <option value="open">Open</option>
                <option value="in_progress">In progress</option>
                <option value="review">Review</option>
                <option value="done">Done</option>
                <option value="failed">Failed</option>
              </Select>
            </div>
            {canEnableAgent(globalRole, projectRole) && (
              <AgentToggle
                enabled={ticket.agent_enabled}
                onChange={handleAgentToggle}
              />
            )}
          </CardContent>
        </Card>
      )}

      <AgentRunPanel
        ticketId={ticket.id}
        runs={runs}
        activeRunId={activeRunId}
        onRunStarted={(run) => {
          setActiveRunId(run.id);
          fetchRuns();
        }}
        onRunsRefresh={fetchRuns}
        canRun={canEnableAgent(globalRole, projectRole) && ticket.agent_enabled}
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Comments</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {comments.length === 0 ? (
            <p className="text-sm text-muted-foreground">No comments yet.</p>
          ) : (
            comments.map((c) => (
              <div key={c.id} className="rounded-lg border border-border p-3">
                <div className="mb-1 flex items-center gap-2 text-xs text-muted-foreground">
                  <span>{c.is_agent ? "AI Agent" : "User"}</span>
                  <span>{formatDate(c.created_at)}</span>
                </div>
                <p className="text-sm">{c.body}</p>
              </div>
            ))
          )}
          {canComment(globalRole, projectRole) && (
            <form onSubmit={handleComment} className="space-y-2">
              <Textarea
                placeholder="Add a comment…"
                value={commentBody}
                onChange={(e) => setCommentBody(e.target.value)}
              />
              <Button type="submit" size="sm" disabled={submitting}>
                {submitting ? "Posting…" : "Post comment"}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
