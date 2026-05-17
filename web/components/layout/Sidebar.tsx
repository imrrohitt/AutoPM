"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bot,
  FolderKanban,
  Github,
  LayoutDashboard,
  Settings,
  Users,
  Wrench,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface SidebarProps {
  projectId?: string;
}

export function Sidebar({ projectId }: SidebarProps) {
  const pathname = usePathname();

  const mainNav = [{ href: "/projects", label: "Projects", icon: FolderKanban }];

  const projectNav = projectId
    ? [
        { href: `/projects/${projectId}`, label: "Overview", icon: LayoutDashboard },
        { href: `/projects/${projectId}/settings/github`, label: "GitHub", icon: Github },
        { href: `/projects/${projectId}/settings/llm`, label: "LLM", icon: Bot },
        { href: `/projects/${projectId}/settings/members`, label: "Members", icon: Users },
      ]
    : [];

  const isActive = (href: string) => {
    if (href === `/projects/${projectId}`) return pathname === href;
    return pathname === href || pathname.startsWith(`${href}/`);
  };

  const linkClass = (href: string) =>
    cn(
      "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
      isActive(href)
        ? "bg-primary/10 text-primary"
        : "text-muted-foreground hover:bg-accent hover:text-foreground"
    );

  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col border-r border-border bg-card">
      <div className="flex h-14 items-center gap-2.5 border-b border-border px-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Wrench className="h-4 w-4" />
        </div>
        <span className="font-semibold tracking-tight">AutoPM</span>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto p-3">
        {mainNav.map(({ href, label, icon: Icon }) => (
          <Link key={href} href={href} className={linkClass(href)}>
            <Icon className="h-4 w-4" />
            {label}
          </Link>
        ))}

        {projectNav.length > 0 && (
          <>
            <p className="mb-1 mt-5 px-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Project
            </p>
            {projectNav.map(({ href, label, icon: Icon }) => (
              <Link key={href} href={href} className={linkClass(href)}>
                <Icon className="h-4 w-4" />
                {label}
              </Link>
            ))}
          </>
        )}
      </nav>

      <div className="border-t border-border p-3">
        <Link
          href={projectId ? `/projects/${projectId}/settings/github` : "/projects"}
          className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          <Settings className="h-4 w-4" />
          Settings
        </Link>
      </div>
    </aside>
  );
}
