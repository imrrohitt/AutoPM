import { Badge } from "@/components/ui/badge";

const variants: Record<string, "default" | "secondary" | "success" | "warning" | "destructive"> = {
  queued: "secondary",
  running: "default",
  completed: "success",
  failed: "destructive",
  cancelled: "warning",
};

export function AgentStatusBadge({ status }: { status: string }) {
  return (
    <Badge variant={variants[status] || "outline"} className="capitalize">
      {status}
    </Badge>
  );
}
