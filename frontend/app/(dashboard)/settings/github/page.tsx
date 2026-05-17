import { redirect } from "next/navigation";

export default function SettingsGitHubRedirect({
  searchParams,
}: {
  searchParams: { projectId?: string };
}) {
  if (searchParams.projectId) {
    redirect(`/projects/${searchParams.projectId}/settings/github`);
  }
  redirect("/projects");
}
