"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { agentApi } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import type { AgentLog } from "@/lib/types";

interface StreamDone {
  type: "done";
  status: string;
}

export function useAgentStream(runId: string | null, enabled = true) {
  const [logs, setLogs] = useState<AgentLog[]>([]);
  const [done, setDone] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    setLogs([]);
    setDone(false);
    setStatus(null);
    setError(null);
    setConnected(false);
  }, []);

  useEffect(() => {
    if (!runId || !enabled) {
      reset();
      return;
    }

    reset();
    const controller = new AbortController();
    abortRef.current = controller;

    async function stream() {
      const token = getAccessToken();
      if (!token) {
        setError("Not authenticated");
        return;
      }

      try {
        const response = await fetch(agentApi.streamUrl(runId!), {
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`Stream failed (${response.status})`);
        }

        setConnected(true);
        const reader = response.body?.getReader();
        if (!reader) throw new Error("No response body");

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done: readerDone, value } = await reader.read();
          if (readerDone) break;

          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split("\n\n");
          buffer = parts.pop() || "";

          for (const part of parts) {
            const lines = part.split("\n");
            for (const line of lines) {
              if (!line.startsWith("data: ")) continue;
              const raw = line.slice(6).trim();
              if (!raw) continue;
              try {
                const data = JSON.parse(raw) as AgentLog | StreamDone;
                if ("type" in data && data.type === "done") {
                  setDone(true);
                  setStatus(data.status);
                  return;
                }
                setLogs((prev) => {
                  const log = data as AgentLog;
                  if (prev.some((l) => l.id === log.id)) return prev;
                  return [...prev, log];
                });
              } catch {
                /* skip malformed */
              }
            }
          }
        }
        setDone(true);
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          setError(err instanceof Error ? err.message : "Stream error");
        }
      } finally {
        setConnected(false);
      }
    }

    stream();

    return () => {
      controller.abort();
    };
  }, [runId, enabled, reset]);

  return { logs, done, status, error, connected };
}
