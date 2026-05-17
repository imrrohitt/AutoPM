import Link from "next/link";
import { Bot } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TicketStatusBadge } from "./TicketStatusBadge";
import type { Ticket } from "@/lib/types";

export function TicketCard({ ticket }: { ticket: Ticket }) {
  return (
    <Link href={`/tickets/${ticket.id}`}>
      <Card className="transition-colors hover:border-primary/40">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="text-sm font-medium">{ticket.title}</CardTitle>
            {ticket.agent_enabled && <Bot className="h-4 w-4 shrink-0 text-primary" />}
          </div>
        </CardHeader>
        <CardContent className="flex items-center gap-2">
          <TicketStatusBadge status={ticket.status} />
          <span className="text-xs capitalize text-muted-foreground">{ticket.type}</span>
          <span className="text-xs capitalize text-muted-foreground">{ticket.priority}</span>
        </CardContent>
      </Card>
    </Link>
  );
}
