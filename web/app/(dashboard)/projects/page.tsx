"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { FolderKanban, Plus } from "lucide-react";
import { toast } from "sonner";
import { ProjectCard } from "@/components/projects/ProjectCard";
import { ProjectFormModal } from "@/components/projects/ProjectFormModal";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Pagination } from "@/components/ui/pagination";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/hooks/useAuth";
import { usePagination } from "@/lib/hooks/usePagination";
import { useProjects } from "@/lib/hooks/useProjects";
import { canCreateProject } from "@/lib/permissions";
import type { Project } from "@/lib/types";

const PAGE_SIZE = 9;

export default function ProjectsPage() {
  const router = useRouter();
  const { user } = useAuth();
  const { projects, loading, error, refetch } = useProjects();
  const canCreate = user ? canCreateProject(user.global_role) : false;

  const [modalOpen, setModalOpen] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);

  const { paginatedItems, page, totalPages, totalItems, goToPage, resetPage } =
    usePagination(projects, PAGE_SIZE);

  useEffect(() => {
    if (error) toast.error(error);
  }, [error]);

  useEffect(() => {
    resetPage();
  }, [projects.length, resetPage]);

  const openCreate = () => {
    setEditingProject(null);
    setModalOpen(true);
  };

  const openEdit = (project: Project) => {
    setEditingProject(project);
    setModalOpen(true);
  };

  const handleSuccess = (project: Project) => {
    refetch();
    if (!editingProject) {
      router.push(`/projects/${project.id}`);
    }
  };

  return (
    <>
      <div className="mx-auto max-w-7xl space-y-8">
        <PageHeader
          title="Projects"
          description="Manage your AI-native workspaces"
          action={
            canCreate ? (
              <Button onClick={openCreate}>
                <Plus className="h-4 w-4" />
                New project
              </Button>
            ) : undefined
          }
        />

        {loading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-36 rounded-xl" />
            ))}
          </div>
        ) : projects.length === 0 ? (
          <EmptyState
            icon={FolderKanban}
            title="No projects yet"
            description="Create your first project to start managing stories and AI agents."
            action={
              canCreate ? (
                <Button onClick={openCreate}>Create your first project</Button>
              ) : undefined
            }
          />
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {paginatedItems.map((p) => (
                <ProjectCard
                  key={p.id}
                  project={p}
                  onEdit={canCreate ? () => openEdit(p) : undefined}
                />
              ))}
            </div>
            <Pagination
              page={page}
              totalPages={totalPages}
              totalItems={totalItems}
              pageSize={PAGE_SIZE}
              onPageChange={goToPage}
            />
          </>
        )}
      </div>

      <ProjectFormModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        project={editingProject}
        onSuccess={handleSuccess}
      />
    </>
  );
}
