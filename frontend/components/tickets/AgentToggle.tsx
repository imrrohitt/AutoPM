"use client";

import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

interface AgentToggleProps {
  enabled: boolean;
  disabled?: boolean;
  onChange: (enabled: boolean) => void;
}

export function AgentToggle({ enabled, disabled, onChange }: AgentToggleProps) {
  return (
    <div className="flex items-center gap-3">
      <Switch
        id="agent-toggle"
        checked={enabled}
        disabled={disabled}
        onCheckedChange={onChange}
      />
      <Label htmlFor="agent-toggle" className="cursor-pointer">
        AI agent enabled
      </Label>
    </div>
  );
}
