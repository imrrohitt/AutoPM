"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bot,
  ChevronLeft,
  ChevronRight,
  FolderKanban,
  Github,
  LayoutDashboard,
  Settings,
  Users,
} from "lucide-react";
import { Logo } from "@/components/brand/Logo";
import { useSidebar } from "@/components/layout/sidebar-context";
import { cn } from "@/lib/utils";

interface SidebarProps {
  projectId?: string;
}

export function Sidebar({ projectId }: SidebarProps) {
  const pathname = usePathname();
  const { collapsed, toggle } = useSidebar();

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
      "flex items-center gap-3 rounded-lg py-2 text-sm font-medium transition-colors",
      collapsed ? "justify-center px-2" : "px-3",
      isActive(href)
        ? "bg-primary/10 text-primary"
        : "text-muted-foreground hover:bg-accent hover:text-foreground"
    );

  const NavLink = ({
    href,
    label,
    icon: Icon,
  }: {
    href: string;
    label: string;
    icon: React.ComponentType<{ className?: string }>;
  }) => (
    <Link href={href} className={linkClass(href)} title={collapsed ? label : undefined}>
      <Icon className="h-4 w-4 shrink-0" />
      {!collapsed && <span>{label}</span>}
    </Link>
  );

  return (
    <aside
      className={cn(
        "flex h-screen shrink-0 flex-col border-r border-border bg-card transition-[width] duration-200",
        collapsed ? "w-[52px]" : "w-56"
      )}
    >
      <div
        className={cn(
          "flex h-14 items-center border-b border-border",
          collapsed ? "justify-center px-2" : "justify-between px-3"
        )}
      >
        {!collapsed && <Logo size={36} />}
        <button
          type="button"
          onClick={toggle}
          className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </button>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto p-2">
        {mainNav.map((item) => (
          <NavLink key={item.href} {...item} />
        ))}

        {projectNav.length > 0 && (
          <>
            {!collapsed && (
              <p className="mb-1 mt-4 px-3 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Project
              </p>
            )}
            {collapsed && <div className="my-2 border-t border-border" />}
            {projectNav.map((item) => (
              <NavLink key={item.href} {...item} />
            ))}
          </>
        )}
      </nav>

      <div className="border-t border-border p-2">
        <Link
          href={projectId ? `/projects/${projectId}/settings/github` : "/projects"}
          className={linkClass(
            projectId ? `/projects/${projectId}/settings/github` : "/projects"
          )}
          title={collapsed ? "Settings" : undefined}
        >
          <Settings className="h-4 w-4 shrink-0" />
          {!collapsed && <span>Settings</span>}
        </Link>
      </div>
    </aside>
  );
}
