"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { Spinner } from "@/components/ui/spinner";
import { storiesApi } from "@/lib/api";
import { useAuth } from "@/lib/hooks/useAuth";
import { useProject } from "@/lib/hooks/useProjects";
import { canCreateStory } from "@/lib/permissions";
import type { Story } from "@/lib/types";
import { getErrorMessage } from "@/lib/utils";

export default function ProjectDetailPage() {
  const params = useParams();
  const projectId = params.projectId as string;
  const { user } = useAuth();
  const { project, loading, error } = useProject(projectId);
  const [stories, setStories] = useState<Story[]>([]);
  const [storiesLoading, setStoriesLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    title: "",
    description: "",
    acceptance_criteria: "",
    priority: "medium",
  });

  const canCreate = user && project
    ? canCreateStory(user.global_role, project.my_role)
    : false;

  const fetchStories = useCallback(async () => {
    setStoriesLoading(true);
    try {
      const { data } = await storiesApi.list(projectId);
      setStories(data);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setStoriesLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchStories();
  }, [fetchStories]);

  const handleCreateStory = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      await storiesApi.create(projectId, form);
      toast.success("Story created");
      setForm({ title: "", description: "", acceptance_criteria: "", priority: "medium" });
      setShowForm(false);
      await fetchStories();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setCreating(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  if (error || !project) {
    return <p className="text-destructive">{error || "Project not found"}</p>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">{project.name}</h2>
        <p className="mt-1 text-muted-foreground">{project.description}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          <Badge variant="success">{project.status}</Badge>
          {project.my_role && (
            <Badge variant="outline" className="capitalize">
              {project.my_role}
            </Badge>
          )}
        </div>
      </div>

      {(project.goals || project.tech_stack) && (
        <Card>
          <CardContent className="grid gap-4 pt-6 md:grid-cols-2">
            {project.goals && (
              <div>
                <p className="text-sm font-medium">Goals</p>
                <p className="mt-1 text-sm text-muted-foreground">{project.goals}</p>
              </div>
            )}
            {project.tech_stack && (
              <div>
                <p className="text-sm font-medium">Tech stack</p>
                <p className="mt-1 text-sm text-muted-foreground">{project.tech_stack}</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Stories</h3>
        {canCreate && (
          <Button size="sm" onClick={() => setShowForm(!showForm)}>
            <Plus className="h-4 w-4" />
            New story
          </Button>
        )}
      </div>

      {showForm && canCreate && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Create story</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreateStory} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="title">Title</Label>
                <Input
                  id="title"
                  required
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
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
                <Label htmlFor="ac">Acceptance criteria</Label>
                <Textarea
                  id="ac"
                  value={form.acceptance_criteria}
                  onChange={(e) => setForm({ ...form, acceptance_criteria: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="priority">Priority</Label>
                <Select
                  id="priority"
                  value={form.priority}
                  onChange={(e) => setForm({ ...form, priority: e.target.value })}
                >
                  <option value="critical">Critical</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </Select>
              </div>
              <Button type="submit" disabled={creating}>
                {creating ? <Spinner /> : "Create"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {storiesLoading ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
      ) : stories.length === 0 ? (
        <p className="text-sm text-muted-foreground">No stories yet.</p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {stories.map((story) => (
            <Link
              key={story.id}
              href={`/stories/${story.id}?projectId=${projectId}`}
            >
              <Card className="transition-colors hover:border-primary/40">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">{story.title}</CardTitle>
                </CardHeader>
                <CardContent className="flex gap-2">
                  <Badge variant="outline" className="capitalize">
                    {story.status}
                  </Badge>
                  <Badge variant="secondary" className="capitalize">
                    {story.priority}
                  </Badge>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

