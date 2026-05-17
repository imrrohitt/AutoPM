"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { projectsApi } from "@/lib/api";
import { getErrorMessage } from "@/lib/utils";

export function ProjectCreateForm() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    name: "",
    description: "",
    goals: "",
    tech_stack: "",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const { data } = await projectsApi.create(form);
      toast.success("Project created");
      router.push(`/projects/${data.id}`);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>New project</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="goals">Goals (for AI agent)</Label>
            <Textarea
              id="goals"
              value={form.goals}
              onChange={(e) => setForm({ ...form, goals: e.target.value })}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="tech_stack">Tech stack</Label>
            <Input
              id="tech_stack"
              placeholder="Next.js, FastAPI, PostgreSQL"
              value={form.tech_stack}
              onChange={(e) => setForm({ ...form, tech_stack: e.target.value })}
            />
          </div>
          <Button type="submit" disabled={loading}>
            {loading ? <Spinner /> : "Create project"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

