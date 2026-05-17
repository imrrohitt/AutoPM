import { redirect } from "next/navigation";

export default function SettingsMembersRedirect({
  searchParams,
}: {
  searchParams: { projectId?: string };
}) {
  if (searchParams.projectId) {
    redirect(`/projects/${searchParams.projectId}/settings/members`);
  }
  redirect("/projects");
}
