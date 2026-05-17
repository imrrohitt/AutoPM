"use client";

import { useCallback, useEffect, useState } from "react";
import { ticketsApi } from "@/lib/api";
import type { Ticket } from "@/lib/types";
import { getErrorMessage } from "@/lib/utils";

export function useTicket(ticketId: string) {
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTicket = useCallback(async () => {
    if (!ticketId) return;
    setLoading(true);
    setError(null);
    try {
      const { data } = await ticketsApi.get(ticketId);
      setTicket(data);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [ticketId]);

  useEffect(() => {
    fetchTicket();
  }, [fetchTicket]);

  return { ticket, loading, error, refetch: fetchTicket, setTicket };
}

export function useStoryTickets(storyId: string) {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTickets = useCallback(async () => {
    if (!storyId) return;
    setLoading(true);
    setError(null);
    try {
      const { data } = await ticketsApi.list(storyId);
      setTickets(data);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [storyId]);

  useEffect(() => {
    fetchTickets();
  }, [fetchTickets]);

  return { tickets, loading, error, refetch: fetchTickets };
}
