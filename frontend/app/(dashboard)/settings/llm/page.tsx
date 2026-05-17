import { redirect } from "next/navigation";

export default function SettingsLLMRedirect({
  searchParams,
}: {
  searchParams: { projectId?: string };
}) {
  if (searchParams.projectId) {
    redirect(`/projects/${searchParams.projectId}/settings/llm`);
  }
  redirect("/projects");
}
