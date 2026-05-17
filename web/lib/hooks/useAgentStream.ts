"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { agentApi } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import type { AgentLog, AgentRun } from "@/lib/types";

interface StreamDone {
  type: "done";
  status: string;
}

interface StreamRunUpdate {
  type: "run";
  status: string;
  pr_url?: string | null;
  pr_number?: number | null;
  branch_name?: string | null;
  error_message?: string | null;
}

type StreamEvent = AgentLog | StreamDone | StreamRunUpdate;

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

function isAgentLog(data: StreamEvent): data is AgentLog {
  return "id" in data && "message" in data && !("type" in data);
}

export function useAgentStream(
  runId: string | null,
  /** Connect SSE while the run is active (no polling). */
  liveStream = true,
  onComplete?: () => void
) {
  const [logs, setLogs] = useState<AgentLog[]>([]);
  const [done, setDone] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [runMeta, setRunMeta] = useState<Partial<AgentRun> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const doneRef = useRef(false);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  const reset = useCallback(() => {
    setLogs([]);
    setDone(false);
    setStatus(null);
    setRunMeta(null);
    setError(null);
    setConnected(false);
    setLoadingHistory(false);
    doneRef.current = false;
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
    setRunMeta(runRes.data);
    if (TERMINAL.has(runStatus)) {
      setDone(true);
      doneRef.current = true;
    }
    return runStatus;
  }, []);

  // One-time load when run is selected (history for completed runs)
  useEffect(() => {
    if (!runId) {
      reset();
      return;
    }

    let cancelled = false;
    setLoadingHistory(true);
    setError(null);
    setLogs([]);
    setDone(false);
    setRunMeta(null);

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

  // SSE-only live stream (no polling)
  useEffect(() => {
    if (!runId || !liveStream) {
      abortRef.current?.abort();
      setConnected(false);
      return;
    }

    let cancelled = false;
    let retryMs = 1000;

    const connect = async () => {
      const token = getAccessToken();
      if (!token || cancelled) return;

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const response = await fetch(agentApi.streamUrl(runId), {
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: "text/event-stream",
          },
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`Stream failed (${response.status})`);
        }

        setConnected(true);
        setError(null);
        retryMs = 1000;

        const reader = response.body?.getReader();
        if (!reader) throw new Error("No response body");

        const decoder = new TextDecoder();
        let buffer = "";

        while (!cancelled) {
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
                const data = JSON.parse(raw) as StreamEvent;

                if ("type" in data && data.type === "done") {
                  doneRef.current = true;
                  setDone(true);
                  setStatus(data.status);
                  setConnected(false);
                  await fetchLogs(runId);
                  onCompleteRef.current?.();
                  return;
                }

                if ("type" in data && data.type === "run") {
                  setStatus(data.status);
                  setRunMeta({
                    status: data.status,
                    pr_url: data.pr_url ?? undefined,
                    pr_number: data.pr_number ?? undefined,
                    branch_name: data.branch_name ?? undefined,
                    error_message: data.error_message ?? undefined,
                  });
                  if (TERMINAL.has(data.status)) {
                    doneRef.current = true;
                    setDone(true);
                  }
                  continue;
                }

                if (isAgentLog(data)) {
                  setLogs((prev) => mergeLogLists(prev, [data]));
                }
              } catch {
                /* skip malformed chunk */
              }
            }
          }
        }
      } catch (err) {
        if ((err as Error).name === "AbortError" || cancelled) return;
        setConnected(false);
        if (!doneRef.current) {
          setError("Live stream disconnected — reconnecting…");
          await new Promise((r) => setTimeout(r, retryMs));
          retryMs = Math.min(retryMs * 2, 8000);
          if (!cancelled && !doneRef.current) connect();
        }
      } finally {
        if (!cancelled) setConnected(false);
      }
    };

    connect();

    return () => {
      cancelled = true;
      abortRef.current?.abort();
    };
  }, [runId, liveStream, fetchLogs]);

  return { logs, done, status, runMeta, error, connected, loadingHistory };
}
