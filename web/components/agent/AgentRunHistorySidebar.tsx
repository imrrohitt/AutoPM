"use client";

import { Clock, CalendarClock } from "lucide-react";
import { AgentStatusBadge } from "@/components/agent/AgentStatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Pagination } from "@/components/ui/pagination";
import { cn } from "@/lib/utils";
import type { AgentRun } from "@/lib/types";

type Props = {
  runs: AgentRun[];
  activeRunId: string | null | undefined;
  onSelect: (run: AgentRun) => void;
  page: number;
  totalPages: number;
  totalItems: number;
  pageSize: number;
  onPageChange: (page: number) => void;
};

function formatRunTime(iso: string) {
  const d = new Date(iso);
  return {
    date: d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }),
    time: d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" }),
  };
}

export function AgentRunHistorySidebar({
  runs,
  activeRunId,
  onSelect,
  page,
  totalPages,
  totalItems,
  pageSize,
  onPageChange,
}: Props) {
  return (
    <Card className="flex flex-col shadow-sm">
      <CardHeader className="border-b border-border/60 pb-3 pt-4">
        <CardTitle className="flex items-center gap-2 text-sm font-semibold">
          <Clock className="h-4 w-4 text-primary" />
          Run history
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-2 p-2 pt-3">
        {runs.length === 0 ? (
          <EmptyState
            icon={Clock}
            title="No runs yet"
            description="Start AI work from the story page or schedule a run below."
            className="border-0 bg-transparent py-8 shadow-none"
          />
        ) : (
          <>
            <ul className="scrollbar-thin max-h-[min(280px,40vh)] space-y-1 overflow-y-auto pr-0.5">
              {runs.map((run) => {
                const selected = activeRunId === run.id;
                const { date, time } = formatRunTime(run.created_at);
                return (
                  <li key={run.id}>
                    <button
                      type="button"
                      onClick={() => onSelect(run)}
                      className={cn(
                        "w-full rounded-lg border px-3 py-2.5 text-left transition-all",
                        selected
                          ? "border-primary/40 bg-primary/5 shadow-sm ring-1 ring-primary/20"
                          : "border-transparent bg-muted/40 hover:border-border hover:bg-muted/70"
                      )}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <AgentStatusBadge status={run.status} />
                        {run.schedule_id && (
                          <span
                            className="flex items-center gap-0.5 text-[10px] font-medium uppercase tracking-wide text-primary"
                            title="Scheduled run"
                          >
                            <CalendarClock className="h-3 w-3" />
                            Auto
                          </span>
                        )}
                      </div>
                      <p className="mt-1.5 text-xs font-medium text-foreground">{date}</p>
                      <p className="text-[11px] text-muted-foreground">{time}</p>
                    </button>
                  </li>
                );
              })}
            </ul>
            {totalPages > 1 && (
              <Pagination
                page={page}
                totalPages={totalPages}
                totalItems={totalItems}
                pageSize={pageSize}
                onPageChange={onPageChange}
                className="border-t border-border/60 pt-2"
              />
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
