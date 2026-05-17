"use client";

import { LogOut, User } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { UserProfile } from "@/lib/types";

interface TopBarProps {
  title?: string;
  user: UserProfile | null;
  onLogout: () => Promise<void>;
}

export function TopBar({ title, user, onLogout }: TopBarProps) {
  const router = useRouter();

  const handleLogout = async () => {
    await onLogout();
    router.push("/login");
  };

  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-card/30 px-6">
      <h1 className="text-lg font-semibold">{title || "Dashboard"}</h1>
      <div className="flex items-center gap-4">
        {user && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <User className="h-4 w-4" />
            <span>{user.full_name}</span>
            <Badge variant="secondary" className="capitalize">
              {user.global_role}
            </Badge>
          </div>
        )}
        <Button variant="ghost" size="sm" onClick={handleLogout}>
          <LogOut className="h-4 w-4" />
          Sign out
        </Button>
      </div>
    </header>
  );
}
