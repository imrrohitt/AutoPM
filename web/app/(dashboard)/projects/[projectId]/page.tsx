"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { BookOpen, Pencil, Plus, Settings } from "lucide-react";
import { toast } from "sonner";
import { ProjectFormModal } from "@/components/projects/ProjectFormModal";
import { StoryFormModal } from "@/components/stories/StoryFormModal";
import { BackLink } from "@/components/ui/back-link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingPage } from "@/components/ui/loading-page";
import { PageHeader } from "@/components/ui/page-header";
import { Pagination } from "@/components/ui/pagination";
import { Skeleton } from "@/components/ui/skeleton";
import { storiesApi } from "@/lib/api";
import { useAuth } from "@/lib/hooks/useAuth";
import { usePagination } from "@/lib/hooks/usePagination";
import { useProject } from "@/lib/hooks/useProjects";
import { canCreateProject, canCreateStory } from "@/lib/permissions";
import type { Story } from "@/lib/types";
import { getErrorMessage } from "@/lib/utils";

const STORIES_PAGE_SIZE = 10;

export default function ProjectDetailPage() {
  const params = useParams();
  const projectId = params.projectId as string;
  const { user } = useAuth();
  const { project, loading, error, refetch: refetchProject } = useProject(projectId);
  const [stories, setStories] = useState<Story[]>([]);
  const [storiesLoading, setStoriesLoading] = useState(true);

  const [projectModalOpen, setProjectModalOpen] = useState(false);
  const [storyModalOpen, setStoryModalOpen] = useState(false);
  const [editingStory, setEditingStory] = useState<Story | null>(null);

  const { paginatedItems, page, totalPages, totalItems, goToPage, resetPage } =
    usePagination(stories, STORIES_PAGE_SIZE);

  const canCreate = user && project
    ? canCreateStory(user.global_role, project.my_role)
    : false;
  const canEditProject = user ? canCreateProject(user.global_role) : false;

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

  const openCreateStory = () => {
    setEditingStory(null);
    setStoryModalOpen(true);
  };

  const openEditStory = (story: Story) => {
    setEditingStory(story);
    setStoryModalOpen(true);
  };

  const handleStorySuccess = (story: Story) => {
    setStories((prev) => {
      const idx = prev.findIndex((s) => s.id === story.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = story;
        return next;
      }
      return [story, ...prev];
    });
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
    <>
      <div className="mx-auto max-w-7xl space-y-8">
        <BackLink href="/projects">All projects</BackLink>

        <PageHeader
          title={project.name}
          description={project.description || undefined}
          action={
            <div className="flex flex-wrap gap-2">
              {canEditProject && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setProjectModalOpen(true)}
                >
                  <Settings className="h-4 w-4" />
                  Edit project
                </Button>
              )}
              {canCreate && (
                <Button size="sm" onClick={openCreateStory}>
                  <Plus className="h-4 w-4" />
                  New story
                </Button>
              )}
            </div>
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

        <section className="space-y-4">
          <h3 className="text-lg font-semibold">Stories</h3>

          {storiesLoading ? (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-28 rounded-xl" />
              ))}
            </div>
          ) : stories.length === 0 ? (
            <EmptyState
              icon={BookOpen}
              title="No stories yet"
              description="Add a story to define work for your team and AI agent."
              action={
                canCreate ? (
                  <Button size="sm" onClick={openCreateStory}>
                    <Plus className="h-4 w-4" />
                    Create story
                  </Button>
                ) : undefined
              }
            />
          ) : (
            <>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {paginatedItems.map((story) => (
                  <Card
                    key={story.id}
                    className="group relative h-full transition-all hover:border-primary/40 hover:shadow-md"
                  >
                    {canCreate && (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="absolute right-2 top-2 z-10 h-8 w-8 p-0 opacity-0 transition-opacity group-hover:opacity-100"
                        onClick={() => openEditStory(story)}
                        aria-label="Edit story"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                    )}
                    <Link
                      href={`/stories/${story.id}?projectId=${projectId}`}
                      className="block"
                    >
                      <CardHeader className="pb-2 pr-10">
                        <CardTitle className="text-base">{story.title}</CardTitle>
                      </CardHeader>
                      <CardContent className="flex flex-wrap gap-2">
                        <Badge variant="outline" className="capitalize">
                          {story.status}
                        </Badge>
                        <Badge variant="secondary" className="capitalize">
                          {story.priority}
                        </Badge>
                        {story.auto_merge && (
                          <Badge variant="success">Auto merge</Badge>
                        )}
                      </CardContent>
                    </Link>
                  </Card>
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

      <ProjectFormModal
        open={projectModalOpen}
        onClose={() => setProjectModalOpen(false)}
        project={project}
        onSuccess={() => refetchProject()}
      />

      <StoryFormModal
        open={storyModalOpen}
        onClose={() => setStoryModalOpen(false)}
        projectId={projectId}
        story={editingStory}
        onSuccess={handleStorySuccess}
      />
    </>
  );
}
