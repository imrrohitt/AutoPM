"use client";

import { useCallback, useEffect, useState } from "react";
import { agentApi } from "@/lib/api";
import type { AgentFileChange, AgentWorkspace } from "@/lib/types";

export function useAgentWorkspace(runId: string | null) {
  const [workspace, setWorkspace] = useState<AgentWorkspace | null>(null);
  const [changes, setChanges] = useState<Record<string, AgentFileChange>>({});
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const mergeFileChange = useCallback((fc: AgentFileChange) => {
    setChanges((prev) => ({
      ...prev,
      [fc.path]: { ...prev[fc.path], ...fc },
    }));
    setSelectedPath((current) => current ?? fc.path);
  }, []);

  const loadWorkspace = useCallback(async (id: string) => {
    setLoading(true);
    try {
      const { data } = await agentApi.getWorkspace(id);
      setWorkspace(data);
      const map: Record<string, AgentFileChange> = {};
      for (const c of data.changes) {
        map[c.path] = c;
      }
      setChanges(map);
      if (data.changes.length > 0) {
        setSelectedPath((p) => p ?? data.changes[data.changes.length - 1].path);
      } else if (data.tree.length > 0) {
        setSelectedPath((p) => p ?? data.tree[0]);
      }
    } catch {
      /* keep prior */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!runId) {
      setWorkspace(null);
      setChanges({});
      setSelectedPath(null);
      return;
    }
    loadWorkspace(runId);
  }, [runId, loadWorkspace]);

  const changeList = Object.values(changes).sort(
    (a, b) => new Date(a.updated_at).getTime() - new Date(b.updated_at).getTime()
  );

  const activeChange = selectedPath ? changes[selectedPath] : undefined;

  const treePaths = workspace?.tree?.length
    ? workspace.tree
    : changeList.map((c) => c.path);

  return {
    workspace,
    changes,
    changeList,
    activeChange,
    selectedPath,
    setSelectedPath,
    treePaths,
    loading,
    mergeFileChange,
    reload: () => runId && loadWorkspace(runId),
  };
}
