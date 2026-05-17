import { AlertCircle, CheckCircle2, Info, AlertTriangle } from "lucide-react";
import { cn, formatDate } from "@/lib/utils";
import type { AgentLog } from "@/lib/types";

const levelIcon = {
  info: Info,
  warning: AlertTriangle,
  error: AlertCircle,
  success: CheckCircle2,
};

const levelColor = {
  info: "text-blue-400",
  warning: "text-amber-400",
  error: "text-red-400",
  success: "text-emerald-400",
};

export function AgentLogEntry({ log }: { log: AgentLog }) {
  const Icon = levelIcon[log.level as keyof typeof levelIcon] || Info;
  const color = levelColor[log.level as keyof typeof levelColor] || "text-muted-foreground";

  return (
    <div className="flex gap-3 border-b border-border/50 py-2 font-mono text-xs last:border-0">
      <Icon className={cn("mt-0.5 h-3.5 w-3.5 shrink-0", color)} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2 text-muted-foreground">
          <span>{formatDate(log.created_at)}</span>
          {log.step && (
            <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] uppercase">
              {log.step}
            </span>
          )}
        </div>
        <p className="mt-0.5 whitespace-pre-wrap text-foreground">{log.message}</p>
      </div>
    </div>
  );
}
