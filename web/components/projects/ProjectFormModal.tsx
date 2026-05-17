"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { projectsApi } from "@/lib/api";
import type { Project } from "@/lib/types";
import { getErrorMessage } from "@/lib/utils";

type ProjectFormModalProps = {
  open: boolean;
  onClose: () => void;
  project?: Project | null;
  onSuccess: (project: Project) => void;
};

const emptyForm = {
  name: "",
  description: "",
  goals: "",
  tech_stack: "",
};

export function ProjectFormModal({
  open,
  onClose,
  project,
  onSuccess,
}: ProjectFormModalProps) {
  const isEdit = Boolean(project);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState(emptyForm);

  useEffect(() => {
    if (!open) return;
    if (project) {
      setForm({
        name: project.name,
        description: project.description || "",
        goals: project.goals || "",
        tech_stack: project.tech_stack || "",
      });
    } else {
      setForm(emptyForm);
    }
  }, [open, project]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      if (isEdit && project) {
        const { data } = await projectsApi.update(project.id, form);
        toast.success("Project updated");
        onSuccess(data);
      } else {
        const { data } = await projectsApi.create(form);
        toast.success("Project created");
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
      title={isEdit ? "Edit project" : "New project"}
      description={
        isEdit
          ? "Update project details and AI context."
          : "Create a workspace for stories and AI agents."
      }
      size="lg"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="project-name">Name</Label>
          <Input
            id="project-name"
            required
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="project-description">Description</Label>
          <Textarea
            id="project-description"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="project-goals">Goals (for AI agent)</Label>
          <Textarea
            id="project-goals"
            value={form.goals}
            onChange={(e) => setForm({ ...form, goals: e.target.value })}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="project-tech">Tech stack</Label>
          <Input
            id="project-tech"
            placeholder="Next.js, FastAPI, PostgreSQL"
            value={form.tech_stack}
            onChange={(e) => setForm({ ...form, tech_stack: e.target.value })}
          />
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="outline" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button type="submit" disabled={loading}>
            {loading ? <Spinner /> : isEdit ? "Save changes" : "Create project"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
