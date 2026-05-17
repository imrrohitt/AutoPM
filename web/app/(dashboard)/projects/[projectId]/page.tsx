"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { BookOpen, Plus } from "lucide-react";
import { toast } from "sonner";
import { BackLink } from "@/components/ui/back-link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingPage } from "@/components/ui/loading-page";
import { PageHeader } from "@/components/ui/page-header";
import { Pagination } from "@/components/ui/pagination";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { storiesApi } from "@/lib/api";
import { useAuth } from "@/lib/hooks/useAuth";
import { usePagination } from "@/lib/hooks/usePagination";
import { useProject } from "@/lib/hooks/useProjects";
import { canCreateStory } from "@/lib/permissions";
import type { Story } from "@/lib/types";
import { getErrorMessage } from "@/lib/utils";

const STORIES_PAGE_SIZE = 8;

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

  const { paginatedItems, page, totalPages, totalItems, goToPage, resetPage } =
    usePagination(stories, STORIES_PAGE_SIZE);

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

  useEffect(() => {
    resetPage();
  }, [stories.length, resetPage]);

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

  if (loading) return <LoadingPage label="Loading project…" />;

  if (error || !project) {
    return (
      <EmptyState
        title="Project not found"
        description={error || "This project may have been removed or you lack access."}
        action={
          <Link href="/projects">
            <Button variant="outline">Back to projects</Button>
          </Link>
        }
      />
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <BackLink href="/projects">All projects</BackLink>

      <PageHeader
        title={project.name}
        description={project.description || undefined}
        action={
          canCreate ? (
            <Button size="sm" onClick={() => setShowForm(!showForm)}>
              <Plus className="h-4 w-4" />
              New story
            </Button>
          ) : undefined
        }
      />

      <div className="flex flex-wrap gap-2">
        <Badge variant="success">{project.status}</Badge>
        {project.my_role && (
          <Badge variant="outline" className="capitalize">
            {project.my_role}
          </Badge>
        )}
      </div>

      {(project.goals || project.tech_stack) && (
        <Card>
          <CardContent className="grid gap-6 pt-6 md:grid-cols-2">
            {project.goals && (
              <section>
                <p className="text-sm font-medium text-foreground">Goals</p>
                <p className="mt-1 text-sm text-muted-foreground">{project.goals}</p>
              </section>
            )}
            {project.tech_stack && (
              <section>
                <p className="text-sm font-medium text-foreground">Tech stack</p>
                <p className="mt-1 text-sm text-muted-foreground">{project.tech_stack}</p>
              </section>
            )}
          </CardContent>
        </Card>
      )}

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
                {creating ? <Spinner /> : "Create story"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      <section className="space-y-4">
        <h3 className="text-lg font-semibold">Stories</h3>

        {storiesLoading ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <Skeleton className="h-28 rounded-xl" />
            <Skeleton className="h-28 rounded-xl" />
          </div>
        ) : stories.length === 0 ? (
          <EmptyState
            icon={BookOpen}
            title="No stories yet"
            description="Add a story to define work for your team and AI agent."
            action={
              canCreate ? (
                <Button size="sm" onClick={() => setShowForm(true)}>
                  <Plus className="h-4 w-4" />
                  Create story
                </Button>
              ) : undefined
            }
          />
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-2">
              {paginatedItems.map((story) => (
                <Link
                  key={story.id}
                  href={`/stories/${story.id}?projectId=${projectId}`}
                >
                  <Card className="h-full transition-all hover:border-primary/40 hover:shadow-md">
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
            <Pagination
              page={page}
              totalPages={totalPages}
              totalItems={totalItems}
              pageSize={STORIES_PAGE_SIZE}
              onPageChange={goToPage}
            />
          </>
        )}
      </section>
    </div>
  );
}
