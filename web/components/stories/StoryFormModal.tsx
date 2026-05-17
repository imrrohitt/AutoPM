"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { storiesApi } from "@/lib/api";
import type { Story } from "@/lib/types";
import { getErrorMessage } from "@/lib/utils";

type StoryFormModalProps = {
  open: boolean;
  onClose: () => void;
  projectId: string;
  story?: Story | null;
  onSuccess: (story: Story) => void;
};

const emptyForm = {
  title: "",
  description: "",
  acceptance_criteria: "",
  priority: "medium",
  auto_merge: false,
};

export function StoryFormModal({
  open,
  onClose,
  projectId,
  story,
  onSuccess,
}: StoryFormModalProps) {
  const isEdit = Boolean(story);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState(emptyForm);

  useEffect(() => {
    if (!open) return;
    if (story) {
      setForm({
        title: story.title,
        description: story.description || "",
        acceptance_criteria: story.acceptance_criteria || "",
        priority: story.priority,
        auto_merge: story.auto_merge ?? false,
      });
    } else {
      setForm(emptyForm);
    }
  }, [open, story]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      if (isEdit && story) {
        const { data } = await storiesApi.update(projectId, story.id, form);
        toast.success("Story updated");
        onSuccess(data);
      } else {
        const { data } = await storiesApi.create(projectId, form);
        toast.success("Story created");
        onSuccess(data);
      }
      onClose();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isEdit ? "Edit story" : "New story"}
      description={
        isEdit
          ? "Update story details and agent behavior."
          : "Define work for your team and AI agent."
      }
      size="lg"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="story-title">Title</Label>
          <Input
            id="story-title"
            required
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="story-description">Description</Label>
          <Textarea
            id="story-description"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="story-ac">Acceptance criteria</Label>
          <Textarea
            id="story-ac"
            value={form.acceptance_criteria}
            onChange={(e) => setForm({ ...form, acceptance_criteria: e.target.value })}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="story-priority">Priority</Label>
          <Select
            id="story-priority"
            value={form.priority}
            onChange={(e) => setForm({ ...form, priority: e.target.value })}
          >
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </Select>
        </div>
        <div className="flex items-start justify-between gap-4 rounded-lg border border-border bg-muted/30 p-4">
          <div className="space-y-1">
            <Label htmlFor="story-auto-merge" className="text-base">
              Auto merge
            </Label>
            <p className="text-sm text-muted-foreground">
              When enabled, the agent merges the PR after quality checks pass — no human
              review required.
            </p>
          </div>
          <Switch
            id="story-auto-merge"
            checked={form.auto_merge}
            onCheckedChange={(auto_merge) => setForm({ ...form, auto_merge })}
          />
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="outline" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button type="submit" disabled={loading}>
            {loading ? <Spinner /> : isEdit ? "Save changes" : "Create story"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
