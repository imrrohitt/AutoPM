"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { githubApi } from "@/lib/api";
import { useAuth } from "@/lib/hooks/useAuth";
import { useProject } from "@/lib/hooks/useProjects";
import { canConfigureIntegrations } from "@/lib/permissions";
import type { GitHubConnection, GitHubRepo } from "@/lib/types";
import { getErrorMessage } from "@/lib/utils";

export default function GitHubSettingsPage() {
  const params = useParams();
  const projectId = params.projectId as string;
  const { user } = useAuth();
  const { project } = useProject(projectId);
  const [connection, setConnection] = useState<GitHubConnection | null>(null);
  const [repos, setRepos] = useState<GitHubRepo[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingToken, setSavingToken] = useState(false);
  const [listingRepos, setListingRepos] = useState(false);
  const [saving, setSaving] = useState(false);
  const [token, setToken] = useState("");
  const [selectedRepo, setSelectedRepo] = useState("");

  const canEdit =
    user && project
      ? canConfigureIntegrations(user.global_role, project.my_role)
      : false;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await githubApi.getConnection(projectId);
      setConnection(data);
    } catch {
      setConnection(null);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  const saveToken = async () => {
    if (!token.trim()) {
      toast.error("Enter a GitHub token first");
      return;
    }
    setSavingToken(true);
    try {
      const { data } = await githubApi.saveToken(projectId, token.trim());
      setConnection(data);
      setToken("");
      toast.success("Token saved securely for this project");
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setSavingToken(false);
    }
  };

  const fetchRepos = async () => {
    setListingRepos(true);
    try {
      const { data } = await githubApi.listRepos(projectId);
      setRepos(data);
      toast.success(`Found ${data.length} repositories`);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setListingRepos(false);
    }
  };

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    const repo = repos.find((r) => r.full_name === selectedRepo);
    if (!repo) {
      toast.error("Select a repository");
      return;
    }
    setSaving(true);
    try {
      const { data } = await githubApi.connect(projectId, {
        repo_owner: repo.owner,
        repo_name: repo.name,
        default_branch: repo.default_branch,
      });
      setConnection(data);
      toast.success("GitHub repository connected");
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const handleDisconnect = async () => {
    try {
      await githubApi.disconnect(projectId);
      setConnection(null);
      setRepos([]);
      setSelectedRepo("");
      toast.success("Disconnected");
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  const handleIndex = async () => {
    try {
      await githubApi.triggerIndex(projectId);
      toast.success("Indexing started");
      await load();
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Spinner />
      </div>
    );
  }

  const isFullyConnected = connection?.is_connected ?? Boolean(connection?.repo_owner);

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <Link
        href={`/projects/${projectId}`}
        className="text-sm text-muted-foreground hover:text-primary"
      >
        ← Back to project
      </Link>
      <h2 className="text-2xl font-bold">GitHub integration</h2>

      {isFullyConnected && connection ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Connected repository</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="font-mono text-sm">
              {connection.repo_owner}/{connection.repo_name}
            </p>
            <Badge variant="outline" className="capitalize">
              Index: {connection.index_status}
            </Badge>
            {canEdit && (
              <div className="flex gap-2">
                <Button variant="outline" onClick={handleIndex}>
                  Re-index codebase
                </Button>
                <Button variant="destructive" onClick={handleDisconnect}>
                  Disconnect
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      ) : canEdit ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Connect repository</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleConnect} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="token">GitHub personal access token</Label>
                <p className="text-xs text-muted-foreground">
                  Token is encrypted and stored per project — never sent in the URL.
                </p>
                <div className="flex flex-wrap gap-2">
                  <Input
                    id="token"
                    type="password"
                    value={token}
                    onChange={(e) => setToken(e.target.value)}
                    placeholder="github_pat_… or ghp_…"
                    className="min-w-[200px] flex-1"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    onClick={saveToken}
                    disabled={savingToken}
                  >
                    {savingToken ? <Spinner /> : "Save token"}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={fetchRepos}
                    disabled={listingRepos || !connection?.has_token}
                  >
                    {listingRepos ? <Spinner /> : "List repos"}
                  </Button>
                </div>
                {connection?.has_token && (
                  <Badge variant="secondary">Token saved for this project</Badge>
                )}
              </div>
              {repos.length > 0 && (
                <div className="space-y-2">
                  <Label htmlFor="repo">Repository</Label>
                  <Select
                    id="repo"
                    value={selectedRepo}
                    onChange={(e) => setSelectedRepo(e.target.value)}
                  >
                    <option value="">Select…</option>
                    {repos.map((r) => (
                      <option key={r.full_name} value={r.full_name}>
                        {r.full_name}
                      </option>
                    ))}
                  </Select>
                </div>
              )}
              <Button type="submit" disabled={saving || !selectedRepo}>
                {saving ? <Spinner /> : "Connect repository"}
              </Button>
            </form>
          </CardContent>
        </Card>
      ) : (
        <p className="text-muted-foreground">No GitHub connection configured.</p>
      )}
    </div>
  );
}
