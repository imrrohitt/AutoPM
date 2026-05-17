"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { agentApi } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import type { AgentLog, AgentRun } from "@/lib/types";

interface StreamDone {
  type: "done";
  status: string;
}

const TERMINAL = new Set(["completed", "failed", "cancelled"]);

function sortLogs(logs: AgentLog[]): AgentLog[] {
  return [...logs].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  );
}

function mergeLogLists(prev: AgentLog[], incoming: AgentLog[]): AgentLog[] {
  const byId = new Map<string, AgentLog>();
  for (const log of prev) byId.set(log.id, log);
  for (const log of incoming) byId.set(log.id, log);
  return sortLogs(Array.from(byId.values()));
}

export function useAgentStream(
  runId: string | null,
  /** When true, poll + SSE for live updates while the run is active. */
  liveStream = true
) {
  const [logs, setLogs] = useState<AgentLog[]>([]);
  const [done, setDone] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    setLogs([]);
    setDone(false);
    setStatus(null);
    setError(null);
    setConnected(false);
    setLoadingHistory(false);
  }, []);

  const fetchLogs = useCallback(async (id: string) => {
    const [logsRes, runRes] = await Promise.all([
      agentApi.getLogs(id),
      agentApi.getRun(id),
    ]);
    const stored = sortLogs(logsRes.data);
    setLogs((prev) => mergeLogLists(prev, stored));
    const runStatus = runRes.data.status;
    setStatus(runStatus);
    if (TERMINAL.has(runStatus)) {
      setDone(true);
    }
    return runStatus;
  }, []);

  // Load all persisted steps when run is selected
  useEffect(() => {
    if (!runId) {
      reset();
      return;
    }

    let cancelled = false;
    setLoadingHistory(true);
    setError(null);
    setLogs([]);

    (async () => {
      try {
        if (!cancelled) await fetchLogs(runId);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load agent logs"
          );
        }
      } finally {
        if (!cancelled) setLoadingHistory(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [runId, reset, fetchLogs]);

  // Poll backend while run is live (ensures every committed step appears)
  useEffect(() => {
    if (!runId || !liveStream) return;

    let cancelled = false;
    const poll = async () => {
      try {
        const runStatus = await fetchLogs(runId);
        if (TERMINAL.has(runStatus)) {
          setDone(true);
        }
      } catch {
        /* keep last good logs */
      }
    };

    poll();
    const interval = setInterval(() => {
      if (!cancelled) poll();
    }, 2000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [runId, liveStream, fetchLogs]);

  // SSE tail for lower latency during active runs
  useEffect(() => {
    if (!runId || !liveStream) {
      abortRef.current?.abort();
      setConnected(false);
      return;
    }

    const controller = new AbortController();
    abortRef.current = controller;

    async function stream() {
      const token = getAccessToken();
      if (!token) return;

      try {
        const response = await fetch(agentApi.streamUrl(runId!), {
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
        });

        if (!response.ok) return;

        setConnected(true);
        const reader = response.body?.getReader();
        if (!reader) return;

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done: readerDone, value } = await reader.read();
          if (readerDone) break;

          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split("\n\n");
          buffer = parts.pop() || "";

          for (const part of parts) {
            for (const line of part.split("\n")) {
              if (!line.startsWith("data: ")) continue;
              const raw = line.slice(6).trim();
              if (!raw) continue;
              try {
                const data = JSON.parse(raw) as AgentLog | StreamDone;
                if ("type" in data && data.type === "done") {
                  setDone(true);
                  setStatus(data.status);
                  await fetchLogs(runId!);
                  return;
                }
                setLogs((prev) => mergeLogLists(prev, [data as AgentLog]));
              } catch {
                /* skip */
              }
            }
          }
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          /* polling still works */
        }
      } finally {
        setConnected(false);
        if (runId) {
          try {
            await fetchLogs(runId);
          } catch {
            /* ignore */
          }
        }
      }
    }

    stream();

    return () => {
      controller.abort();
    };
  }, [runId, liveStream, fetchLogs]);

  return { logs, done, status, error, connected, loadingHistory };
}
