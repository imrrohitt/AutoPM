"use client";

import { useParams } from "next/navigation";
import { TicketDetail } from "@/components/tickets/TicketDetail";

export default function TicketPage() {
  const params = useParams();
  const ticketId = params.ticketId as string;

  return <TicketDetail ticketId={ticketId} />;
}
