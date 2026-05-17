"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { Spinner } from "@/components/ui/spinner";
import { useAuth } from "@/lib/hooks/useAuth";
import { getAccessToken } from "@/lib/auth";

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading, logout } = useAuth();

  useEffect(() => {
    if (!loading && !user && !getAccessToken()) {
      router.replace(`/login?from=${encodeURIComponent(pathname)}`);
    }
  }, [loading, user, pathname, router]);

  const projectMatch = pathname.match(/\/projects\/([^/]+)/);
  const projectId = projectMatch?.[1];

  const titleMap: Record<string, string> = {
    "/projects": "Projects",
    "/projects/new": "New project",
  };
  let title = titleMap[pathname] || "AutoPM";
  if (pathname.includes("/settings/github")) title = "GitHub";
  if (pathname.includes("/settings/llm")) title = "LLM config";
  if (pathname.includes("/settings/members")) title = "Members";
  if (pathname.startsWith("/stories/")) title = "Story";
  if (pathname.startsWith("/tickets/")) title = "Ticket";

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner className="h-8 w-8" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar projectId={projectId} />
      <div className="flex flex-1 flex-col">
        <TopBar title={title} user={user} onLogout={logout} />
        <main className="flex-1 overflow-auto p-6">{children}</main>
      </div>
    </div>
  );
}
