import Link from "next/link";
import { ArrowRight, Layers } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { Project } from "@/lib/types";

interface ProjectCardProps {
  project: Project;
}

export function ProjectCard({ project }: ProjectCardProps) {
  return (
    <Link href={`/projects/${project.id}`}>
      <Card className="group transition-colors hover:border-primary/50 hover:bg-accent/5">
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between">
            <CardTitle className="flex items-center gap-2 text-base">
              <Layers className="h-4 w-4 text-primary" />
              {project.name}
            </CardTitle>
            <ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
          </div>
          <CardDescription className="line-clamp-2">
            {project.description || "No description"}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex items-center gap-2">
          <Badge variant={project.status === "active" ? "success" : "secondary"}>
            {project.status}
          </Badge>
          {project.my_role && (
            <Badge variant="outline" className="capitalize">
              {project.my_role}
            </Badge>
          )}
          {project.tech_stack && (
            <span className="truncate text-xs text-muted-foreground">{project.tech_stack}</span>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}
