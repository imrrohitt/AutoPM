"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { BackLink } from "@/components/ui/back-link";
import { LoadingPage } from "@/components/ui/loading-page";
import { Pagination } from "@/components/ui/pagination";
import { usePagination } from "@/lib/hooks/usePagination";
import { projectsApi, usersApi } from "@/lib/api";
import { useAuth } from "@/lib/hooks/useAuth";
import { useProject } from "@/lib/hooks/useProjects";
import { canManageProjectMembers } from "@/lib/permissions";
import type { ProjectMember, User } from "@/lib/types";
import { getErrorMessage } from "@/lib/utils";

const MEMBERS_PAGE_SIZE = 10;

export default function ProjectMembersPage() {
  const params = useParams();
  const projectId = params.projectId as string;
  const { user } = useAuth();
  const { project } = useProject(projectId);
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [companyUsers, setCompanyUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [addUserId, setAddUserId] = useState("");
  const [addRole, setAddRole] = useState("developer");

  const { paginatedItems, page, totalPages, totalItems, goToPage } = usePagination(
    members,
    MEMBERS_PAGE_SIZE
  );

  const canEdit =
    user && project
      ? canManageProjectMembers(user.global_role, project.my_role)
      : false;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [membersRes, usersRes] = await Promise.all([
        projectsApi.members.list(projectId),
        usersApi.list(),
      ]);
      setMembers(membersRes.data);
      setCompanyUsers(usersRes.data);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!addUserId) return;
    try {
      await projectsApi.members.add(projectId, { user_id: addUserId, role: addRole });
      toast.success("Member added");
      setAddUserId("");
      await load();
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  const handleRoleChange = async (userId: string, role: string) => {
    try {
      await projectsApi.members.update(projectId, userId, role);
      toast.success("Role updated");
      await load();
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  const handleRemove = async (userId: string) => {
    try {
      await projectsApi.members.remove(projectId, userId);
      toast.success("Member removed");
      await load();
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  const availableUsers = companyUsers.filter(
    (u) => !members.some((m) => m.user_id === u.id)
  );

  if (loading) return <LoadingPage label="Loading members…" />;

  return (
    <article className="mx-auto max-w-2xl space-y-6">
      <BackLink href={`/projects/${projectId}`}>Back to project</BackLink>
      <h2 className="text-2xl font-bold tracking-tight">Project members</h2>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Team</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {members.length === 0 ? (
            <p className="text-sm text-muted-foreground">No members yet.</p>
          ) : (
            <>
              {paginatedItems.map((m) => (
                <div
                  key={m.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-white p-3"
                >
                  <div>
                    <p className="font-medium">{m.user?.full_name || m.user_id}</p>
                    <p className="text-xs text-muted-foreground">{m.user?.email}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {canEdit ? (
                      <Select
                        value={m.role}
                        onChange={(e) => handleRoleChange(m.user_id, e.target.value)}
                        className="w-32"
                      >
                        <option value="manager">Manager</option>
                        <option value="developer">Developer</option>
                        <option value="viewer">Viewer</option>
                      </Select>
                    ) : (
                      <Badge variant="outline" className="capitalize">
                        {m.role}
                      </Badge>
                    )}
                    {canEdit && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleRemove(m.user_id)}
                      >
                        Remove
                      </Button>
                    )}
                  </div>
                </div>
              ))}
              <Pagination
                page={page}
                totalPages={totalPages}
                totalItems={totalItems}
                pageSize={MEMBERS_PAGE_SIZE}
                onPageChange={goToPage}
              />
            </>
          )}
        </CardContent>
      </Card>

      {canEdit && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Add member</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleAdd} className="space-y-4">
              <div className="space-y-2">
                <Label>User</Label>
                <Select value={addUserId} onChange={(e) => setAddUserId(e.target.value)}>
                  <option value="">Select user…</option>
                  {availableUsers.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.full_name} ({u.email})
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Role</Label>
                <Select value={addRole} onChange={(e) => setAddRole(e.target.value)}>
                  <option value="manager">Manager</option>
                  <option value="developer">Developer</option>
                  <option value="viewer">Viewer</option>
                </Select>
              </div>
              <Button type="submit">Add member</Button>
            </form>
          </CardContent>
        </Card>
      )}
    </article>
  );
}
