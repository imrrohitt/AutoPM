"use client";

import { useCallback, useEffect, useState } from "react";
import { CalendarClock, History, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { AgentStatusBadge } from "@/components/agent/AgentStatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { agentApi } from "@/lib/api";
import type { AgentRun, StoryAgentSchedule } from "@/lib/types";
import { getErrorMessage } from "@/lib/utils";

const WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

type Props = {
  storyId: string;
  projectId: string;
  onScheduledRun?: () => void;
};

function toLocalDatetimeValue(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function defaultDatetimeLocal(): string {
  const d = new Date(Date.now() + 60 * 60 * 1000);
  return toLocalDatetimeValue(d.toISOString());
}

function Field({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={`space-y-1 ${className}`}>{children}</div>;
}

export function StoryAgentSchedulePanel({
  storyId,
  projectId,
  onScheduledRun,
}: Props) {
  const [schedules, setSchedules] = useState<StoryAgentSchedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [historyId, setHistoryId] = useState<string | null>(null);
  const [history, setHistory] = useState<AgentRun[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const [label, setLabel] = useState("");
  const [scheduleType, setScheduleType] = useState<"once" | "daily" | "weekly">(
    "once"
  );
  const [runAtLocal, setRunAtLocal] = useState(defaultDatetimeLocal);
  const [weekdays, setWeekdays] = useState<number[]>([1, 2, 3, 4, 5]);

  const timezone =
    typeof Intl !== "undefined"
      ? Intl.DateTimeFormat().resolvedOptions().timeZone
      : "UTC";

  const load = useCallback(async () => {
    try {
      const { data } = await agentApi.listStorySchedules(storyId);
      setSchedules(data);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [storyId]);

  useEffect(() => {
    load();
  }, [load]);

  const toggleWeekday = (day: number) => {
    setWeekdays((prev) =>
      prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day].sort()
    );
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const runAt = new Date(runAtLocal).toISOString();
      await agentApi.createStorySchedule(storyId, projectId, {
        label: label.trim() || undefined,
        schedule_type: scheduleType,
        run_at: runAt,
        weekdays: scheduleType === "weekly" ? weekdays : undefined,
        timezone,
      });
      toast.success("Smart AI work scheduled");
      setLabel("");
      setRunAtLocal(defaultDatetimeLocal());
      await load();
      onScheduledRun?.();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async (schedule: StoryAgentSchedule) => {
    try {
      await agentApi.updateStorySchedule(schedule.id, {
        enabled: !schedule.enabled,
      });
      await load();
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  const handleDelete = async (scheduleId: string) => {
    try {
      await agentApi.deleteStorySchedule(scheduleId);
      toast.success("Schedule removed");
      if (historyId === scheduleId) {
        setHistoryId(null);
        setHistory([]);
      }
      await load();
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  const loadHistory = async (scheduleId: string) => {
    if (historyId === scheduleId) {
      setHistoryId(null);
      setHistory([]);
      return;
    }
    setHistoryId(scheduleId);
    setHistoryLoading(true);
    try {
      const { data } = await agentApi.getStoryScheduleHistory(scheduleId);
      setHistory(data);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setHistoryLoading(false);
    }
  };

  const formatSchedule = (s: StoryAgentSchedule) => {
    const type =
      s.schedule_type === "once"
        ? "Once"
        : s.schedule_type === "daily"
          ? "Daily"
          : "Weekly";
    const next = new Date(s.next_run_at).toLocaleString();
    return `${type}${s.label ? ` · ${s.label}` : ""} · next ${next}`;
  };

  return (
    <Card>
      <CardHeader className="py-3">
        <CardTitle className="flex items-center gap-2 text-sm">
          <CalendarClock className="h-4 w-4" />
          Schedule Smart AI work
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 pb-4 pt-0">
        <p className="text-xs text-muted-foreground">
          Pick a time to run the story agent automatically ({timezone}). Requires{" "}
          <code className="text-xs">./scripts/dev-celery.sh</code> running.
        </p>

        <form onSubmit={handleCreate} className="space-y-3 rounded-lg border p-3">
          <Field>
            <Label htmlFor="sched-label">Label (optional)</Label>
            <Input
              id="sched-label"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="e.g. nightly sync"
            />
          </Field>

          <Field>
            <Label htmlFor="sched-type">Repeat</Label>
            <select
              id="sched-type"
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
              value={scheduleType}
              onChange={(e) =>
                setScheduleType(e.target.value as "once" | "daily" | "weekly")
              }
            >
              <option value="once">Once</option>
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
            </select>
          </Field>

          {scheduleType === "weekly" && (
            <div className="flex flex-wrap gap-1">
              {WEEKDAY_LABELS.map((name, i) => (
                <button
                  key={name}
                  type="button"
                  onClick={() => toggleWeekday(i)}
                  className={`rounded-md border px-2 py-1 text-xs ${
                    weekdays.includes(i)
                      ? "border-primary bg-primary/10"
                      : "border-border"
                  }`}
                >
                  {name}
                </button>
              ))}
            </div>
          )}

          <Field>
            <Label htmlFor="sched-at">
              {scheduleType === "once" ? "Run at" : "Time (first / anchor)"}
            </Label>
            <Input
              id="sched-at"
              type="datetime-local"
              value={runAtLocal}
              onChange={(e) => setRunAtLocal(e.target.value)}
              required
            />
          </Field>

          <Button type="submit" size="sm" disabled={saving}>
            {saving ? <Spinner /> : "Add schedule"}
          </Button>
        </form>

        {loading ? (
          <p className="text-sm text-muted-foreground">Loading schedules…</p>
        ) : schedules.length === 0 ? (
          <p className="text-sm text-muted-foreground">No schedules yet.</p>
        ) : (
          <ul className="space-y-2">
            {schedules.map((s) => (
              <li
                key={s.id}
                className="rounded-lg border border-border px-3 py-2 text-sm"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <Field>
                    <p className="font-medium">{formatSchedule(s)}</p>
                    <p className="text-xs text-muted-foreground">
                      {s.run_count} run{s.run_count === 1 ? "" : "s"}
                      {s.last_run_status && (
                        <>
                          {" "}
                          · last{" "}
                          <AgentStatusBadge status={s.last_run_status} />
                        </>
                      )}
                    </p>
                  </Field>
                  <div className="flex flex-wrap items-center gap-1">
                    <Badge variant={s.enabled ? "success" : "secondary"}>
                      {s.enabled ? "Active" : "Paused"}
                    </Badge>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => handleToggle(s)}
                    >
                      {s.enabled ? "Pause" : "Resume"}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => loadHistory(s.id)}
                    >
                      <History className="h-3 w-3" />
                      History
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDelete(s.id)}
                    >
                      <Trash2 className="h-3 w-3 text-destructive" />
                    </Button>
                  </div>
                </div>
                {historyId === s.id && (
                  <div className="mt-2 border-t pt-2">
                    {historyLoading ? (
                      <Spinner />
                    ) : history.length === 0 ? (
                      <p className="text-xs text-muted-foreground">
                        No runs from this schedule yet.
                      </p>
                    ) : (
                      <ul className="space-y-1">
                        {history.map((run) => (
                          <li
                            key={run.id}
                            className="flex items-center gap-2 text-xs"
                          >
                            <AgentStatusBadge status={run.status} />
                            <span className="font-mono text-muted-foreground">
                              {new Date(run.created_at).toLocaleString()}
                            </span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
