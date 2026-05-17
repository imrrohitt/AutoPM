"use client";

import { useEffect } from "react";
import Link from "next/link";
import { FolderKanban, Plus } from "lucide-react";
import { toast } from "sonner";
import { ProjectCard } from "@/components/projects/ProjectCard";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Pagination } from "@/components/ui/pagination";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/hooks/useAuth";
import { usePagination } from "@/lib/hooks/usePagination";
import { useProjects } from "@/lib/hooks/useProjects";
import { canCreateProject } from "@/lib/permissions";

const PAGE_SIZE = 9;

export default function ProjectsPage() {
  const { user } = useAuth();
  const { projects, loading, error } = useProjects();
  const canCreate = user ? canCreateProject(user.global_role) : false;

  const { paginatedItems, page, totalPages, totalItems, goToPage, resetPage } =
    usePagination(projects, PAGE_SIZE);

  useEffect(() => {
    if (error) toast.error(error);
  }, [error]);

  useEffect(() => {
    resetPage();
  }, [projects.length, resetPage]);

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      <PageHeader
        title="Projects"
        description="Manage your AI-native workspaces"
        action={
          canCreate ? (
            <Link href="/projects/new">
              <Button>
                <Plus className="h-4 w-4" />
                New project
              </Button>
            </Link>
          ) : undefined
        }
      />

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
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
              <Link href="/projects/new">
                <Button>Create your first project</Button>
              </Link>
            ) : undefined
          }
        />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {paginatedItems.map((p) => (
              <ProjectCard key={p.id} project={p} />
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
  );
}
