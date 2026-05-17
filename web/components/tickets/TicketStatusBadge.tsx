import { Badge } from "@/components/ui/badge";

const statusVariant: Record<string, "default" | "secondary" | "success" | "warning" | "destructive"> = {
  open: "secondary",
  in_progress: "default",
  review: "warning",
  done: "success",
  failed: "destructive",
};

export function TicketStatusBadge({ status }: { status: string }) {
  return (
    <Badge variant={statusVariant[status] || "outline"} className="capitalize">
      {status.replace("_", " ")}
    </Badge>
  );
}
