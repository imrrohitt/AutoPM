"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { ProjectCreateForm } from "@/components/projects/ProjectCreateForm";
import { useAuth } from "@/lib/hooks/useAuth";
import { canCreateProject } from "@/lib/permissions";

export default function NewProjectPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user && !canCreateProject(user.global_role)) {
      router.replace("/projects");
    }
  }, [user, loading, router]);

  return (
    <div>
      <h2 className="mb-6 text-2xl font-bold">Create project</h2>
      <ProjectCreateForm />
    </div>
  );
}
