"use client";

import { useCallback, useEffect, useState } from "react";
import {
  CalendarClock,
  ChevronDown,
  ChevronUp,
  History,
  Pause,
  Play,
  Plus,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { AgentStatusBadge } from "@/components/agent/AgentStatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { agentApi } from "@/lib/api";
import type { AgentRun, StoryAgentSchedule } from "@/lib/types";
import { cn, getErrorMessage } from "@/lib/utils";

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

function scheduleTypeLabel(type: string) {
  if (type === "daily") return "Daily";
  if (type === "weekly") return "Weekly";
  return "Once";
}

export function StoryAgentSchedulePanel({
  storyId,
  projectId,
  onScheduledRun,
}: Props) {
  const [schedules, setSchedules] = useState<StoryAgentSchedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [expanded, setExpanded] = useState(true);
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
      toast.success("Schedule saved");
      setLabel("");
      setRunAtLocal(defaultDatetimeLocal());
      setShowForm(false);
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

  return (
    <Card className="shadow-sm">
      <CardHeader className="border-b border-border/60 pb-0 pt-4">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="flex w-full items-center justify-between gap-2 pb-3 text-left"
        >
          <CardTitle className="flex items-center gap-2 text-sm font-semibold">
            <CalendarClock className="h-4 w-4 text-primary" />
            Scheduled runs
            {schedules.length > 0 && (
              <Badge variant="secondary" className="ml-1 font-normal">
                {schedules.length}
              </Badge>
            )}
          </CardTitle>
          {expanded ? (
            <ChevronUp className="h-4 w-4 shrink-0 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
          )}
        </button>
      </CardHeader>

      {expanded && (
        <CardContent className="space-y-3 p-3 pt-3">
          <p className="text-xs leading-relaxed text-muted-foreground">
            Auto-run the agent on a timer ({timezone.replace(/_/g, " ")}).
          </p>

          {!showForm ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="w-full"
              onClick={() => setShowForm(true)}
            >
              <Plus className="h-4 w-4" />
              New schedule
            </Button>
          ) : (
            <form
              onSubmit={handleCreate}
              className="space-y-3 rounded-lg border border-border/80 bg-muted/30 p-3"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  New schedule
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-7 px-2 text-xs"
                  onClick={() => setShowForm(false)}
                >
                  Cancel
                </Button>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1.5 sm:col-span-2">
                  <Label htmlFor="sched-label" className="text-xs">
                    Label
                  </Label>
                  <Input
                    id="sched-label"
                    value={label}
                    onChange={(e) => setLabel(e.target.value)}
                    placeholder="e.g. nightly sync"
                    className="h-9 bg-background"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="sched-type" className="text-xs">
                    Repeat
                  </Label>
                  <Select
                    id="sched-type"
                    value={scheduleType}
                    onChange={(e) =>
                      setScheduleType(
                        e.target.value as "once" | "daily" | "weekly"
                      )
                    }
                    className="h-9"
                  >
                    <option value="once">Once</option>
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="sched-at" className="text-xs">
                    {scheduleType === "once" ? "Run at" : "Start time"}
                  </Label>
                  <Input
                    id="sched-at"
                    type="datetime-local"
                    value={runAtLocal}
                    onChange={(e) => setRunAtLocal(e.target.value)}
                    required
                    className="h-9 bg-background"
                  />
                </div>
              </div>

              {scheduleType === "weekly" && (
                <div className="flex flex-wrap gap-1.5">
                  {WEEKDAY_LABELS.map((name, i) => (
                    <button
                      key={name}
                      type="button"
                      onClick={() => toggleWeekday(i)}
                      className={cn(
                        "rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
                        weekdays.includes(i)
                          ? "border-primary bg-primary text-primary-foreground"
                          : "border-border bg-background text-muted-foreground hover:border-primary/40"
                      )}
                    >
                      {name}
                    </button>
                  ))}
                </div>
              )}

              <Button type="submit" size="sm" className="w-full" disabled={saving}>
                {saving ? <Spinner /> : "Save schedule"}
              </Button>
            </form>
          )}

          {loading ? (
            <div className="flex justify-center py-4">
              <Spinner />
            </div>
          ) : schedules.length === 0 ? (
            <p className="py-2 text-center text-xs text-muted-foreground">
              No schedules yet.
            </p>
          ) : (
            <ul className="space-y-2">
              {schedules.map((s) => {
                const next = new Date(s.next_run_at);
                return (
                  <li
                    key={s.id}
                    className="rounded-lg border border-border/80 bg-card p-3"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <Badge variant="outline" className="text-[10px]">
                            {scheduleTypeLabel(s.schedule_type)}
                          </Badge>
                          <Badge variant={s.enabled ? "success" : "secondary"}>
                            {s.enabled ? "Active" : "Paused"}
                          </Badge>
                        </div>
                        {s.label && (
                          <p className="mt-1 truncate text-sm font-medium">{s.label}</p>
                        )}
                        <p className="mt-1 text-xs text-muted-foreground">
                          Next:{" "}
                          {next.toLocaleString(undefined, {
                            dateStyle: "medium",
                            timeStyle: "short",
                          })}
                        </p>
                        <p className="mt-0.5 text-[11px] text-muted-foreground">
                          {s.run_count} run{s.run_count !== 1 ? "s" : ""}
                          {s.last_run_status && (
                            <>
                              {" · "}
                              Last{" "}
                              <AgentStatusBadge status={s.last_run_status} />
                            </>
                          )}
                        </p>
                      </div>
                      <div className="flex shrink-0 gap-0.5">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0"
                          title={s.enabled ? "Pause" : "Resume"}
                          onClick={() => handleToggle(s)}
                        >
                          {s.enabled ? (
                            <Pause className="h-3.5 w-3.5" />
                          ) : (
                            <Play className="h-3.5 w-3.5" />
                          )}
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0"
                          title="History"
                          onClick={() => loadHistory(s.id)}
                        >
                          <History className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0 text-destructive hover:text-destructive"
                          title="Delete"
                          onClick={() => handleDelete(s.id)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </div>
                    {historyId === s.id && (
                      <div className="mt-3 border-t border-border/60 pt-2">
                        {historyLoading ? (
                          <Spinner />
                        ) : history.length === 0 ? (
                          <p className="text-xs text-muted-foreground">
                            No runs yet for this schedule.
                          </p>
                        ) : (
                          <ul className="space-y-1.5">
                            {history.map((run) => (
                              <li
                                key={run.id}
                                className="flex items-center gap-2 rounded-md bg-muted/50 px-2 py-1"
                              >
                                <AgentStatusBadge status={run.status} />
                                <span className="text-[11px] text-muted-foreground">
                                  {new Date(run.created_at).toLocaleString()}
                                </span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </CardContent>
      )}
    </Card>
  );
}
