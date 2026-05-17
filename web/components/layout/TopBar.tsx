"use client";

import { LogOut, User } from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
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
    try {
      await onLogout();
      toast.success("Signed out");
      router.push("/login");
    } catch {
      toast.error("Could not sign out");
    }
  };

  return (
    <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center justify-between border-b border-border bg-card/80 px-6 backdrop-blur-sm">
      <h1 className="text-lg font-semibold tracking-tight">{title || "Dashboard"}</h1>
      <div className="flex items-center gap-3">
        {user && (
          <div className="hidden items-center gap-2 rounded-lg border border-border bg-background px-3 py-1.5 text-sm sm:flex">
            <User className="h-4 w-4 text-muted-foreground" />
            <span className="font-medium text-foreground">{user.full_name}</span>
            <Badge variant="secondary" className="capitalize">
              {user.global_role}
            </Badge>
          </div>
        )}
        <Button variant="outline" size="sm" onClick={handleLogout}>
          <LogOut className="h-4 w-4" />
          Sign out
        </Button>
      </div>
    </header>
  );
}
