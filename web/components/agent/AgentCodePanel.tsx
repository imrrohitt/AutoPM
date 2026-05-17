"use client";

import { File, FolderGit2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AgentFileChange } from "@/lib/types";
import { Spinner } from "@/components/ui/spinner";

function changeBadge(type: string) {
  if (type === "committed") return "bg-emerald-100 text-emerald-800";
  if (type === "staged") return "bg-amber-100 text-amber-800";
  if (type === "read") return "bg-slate-100 text-slate-600";
  return "bg-muted text-muted-foreground";
}

function DiffView({ change }: { change: AgentFileChange }) {
  const before = change.before_content ?? "";
  const after = change.after_content ?? "";
  const hasDiff = before !== after && (before || after);

  if (!hasDiff && after) {
    return (
      <pre className="overflow-x-auto p-4 font-mono text-[11px] leading-relaxed text-foreground">
        {after}
      </pre>
    );
  }

  if (!hasDiff && before) {
    return (
      <pre className="overflow-x-auto p-4 font-mono text-[11px] leading-relaxed text-muted-foreground">
        {before}
      </pre>
    );
  }

  const beforeLines = before.split("\n");
  const afterLines = after.split("\n");

  return (
    <div className="grid min-h-0 flex-1 grid-cols-2 divide-x divide-border">
      <div className="min-h-0 overflow-auto bg-red-50/30">
        <p className="sticky top-0 border-b border-border bg-red-50/80 px-3 py-1 text-[10px] font-semibold uppercase text-red-700">
          Before
        </p>
        <pre className="p-3 font-mono text-[11px] leading-relaxed">
          {beforeLines.map((line, i) => (
            <div key={`b-${i}`} className="text-red-900/80">
              {line || " "}
            </div>
          ))}
          {beforeLines.length === 0 && (
            <span className="text-muted-foreground">(new file)</span>
          )}
        </pre>
      </div>
      <div className="min-h-0 overflow-auto bg-emerald-50/30">
        <p className="sticky top-0 border-b border-border bg-emerald-50/80 px-3 py-1 text-[10px] font-semibold uppercase text-emerald-700">
          After
        </p>
        <pre className="p-3 font-mono text-[11px] leading-relaxed">
          {afterLines.map((line, i) => (
            <div
              key={`a-${i}`}
              className={cn(
                beforeLines[i] !== line && "bg-emerald-100/80 font-medium text-emerald-950"
              )}
            >
              {line || " "}
            </div>
          ))}
        </pre>
      </div>
    </div>
  );
}

export function AgentCodePanel({
  repoOwner,
  repoName,
  branch,
  treePaths,
  changeList,
  changes,
  selectedPath,
  onSelectPath,
  activeChange,
  loading,
}: {
  repoOwner?: string | null;
  repoName?: string | null;
  branch?: string | null;
  treePaths: string[];
  changeList: AgentFileChange[];
  changes: Record<string, AgentFileChange>;
  selectedPath: string | null;
  onSelectPath: (path: string) => void;
  activeChange?: AgentFileChange;
  loading: boolean;
}) {
  const changedSet = new Set(changeList.map((c) => c.path));
  const sortedTree = [...treePaths].sort((a, b) => {
    const aChanged = changedSet.has(a) ? 0 : 1;
    const bChanged = changedSet.has(b) ? 0 : 1;
    if (aChanged !== bChanged) return aChanged - bChanged;
    return a.localeCompare(b);
  });

  const displayPaths =
    changeList.length > 0
      ? [
          ...changeList.map((c) => c.path),
          ...sortedTree.filter((p) => !changedSet.has(p)),
        ].filter((p, i, arr) => arr.indexOf(p) === i)
      : sortedTree;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <FolderGit2 className="h-3.5 w-3.5" />
          {repoOwner && repoName ? (
            <span className="font-mono">
              {repoOwner}/{repoName}
              {branch && <span className="text-primary"> @{branch}</span>}
            </span>
          ) : (
            <span>Repository files</span>
          )}
        </div>
        {loading && <Spinner className="h-3 w-3" />}
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-[220px_1fr]">
        <div className="scrollbar-thin overflow-y-auto border-r border-border bg-slate-50/50 p-1">
          {displayPaths.length === 0 && !loading && (
            <p className="p-3 text-xs text-muted-foreground">No files indexed.</p>
          )}
          {displayPaths.slice(0, 200).map((path) => {
            const ch = changes[path];
            const isSelected = selectedPath === path;
            return (
              <button
                key={path}
                type="button"
                onClick={() => onSelectPath(path)}
                className={cn(
                  "flex w-full items-start gap-1.5 rounded px-2 py-1 text-left font-mono text-[10px] transition-colors",
                  isSelected
                    ? "bg-primary/10 text-primary"
                    : "text-foreground hover:bg-muted"
                )}
              >
                <File className="mt-0.5 h-3 w-3 shrink-0 opacity-60" />
                <span className="min-w-0 flex-1 break-all leading-tight">{path}</span>
                {ch && (
                  <span
                    className={cn(
                      "shrink-0 rounded px-1 text-[8px] font-semibold uppercase",
                      changeBadge(ch.change_type)
                    )}
                  >
                    {ch.change_type.slice(0, 4)}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        <div className="flex min-h-0 flex-col bg-background">
          {selectedPath ? (
            <>
              <div className="border-b border-border px-3 py-2">
                <p className="font-mono text-xs font-medium">{selectedPath}</p>
                {activeChange?.thought && (
                  <p className="mt-1 text-[11px] italic text-muted-foreground">
                    {activeChange.thought}
                  </p>
                )}
                {activeChange && (
                  <span
                    className={cn(
                      "mt-1 inline-block rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase",
                      changeBadge(activeChange.change_type)
                    )}
                  >
                    {activeChange.change_type}
                  </span>
                )}
              </div>
              <div className="min-h-0 flex-1 overflow-auto">
                {activeChange?.after_content != null ||
                activeChange?.before_content != null ? (
                  <DiffView change={activeChange} />
                ) : (
                  <p className="p-6 text-sm text-muted-foreground">
                    File not modified in this run yet.
                  </p>
                )}
              </div>
            </>
          ) : (
            <p className="p-6 text-sm text-muted-foreground">
              Select a file to view changes.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
