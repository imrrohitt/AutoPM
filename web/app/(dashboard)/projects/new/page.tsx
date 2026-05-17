"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Legacy route — redirects to projects list (create opens in modal). */
export default function NewProjectPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/projects");
  }, [router]);

  return null;
}
