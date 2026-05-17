"use client";

import Link from "next/link";
import { ArrowRight, Layers, Pencil } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { Project } from "@/lib/types";

interface ProjectCardProps {
  project: Project;
  onEdit?: () => void;
}

export function ProjectCard({ project, onEdit }: ProjectCardProps) {
  return (
    <Card className="group relative transition-colors hover:border-primary/50 hover:bg-accent/5">
      {onEdit && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="absolute right-3 top-3 z-10 h-8 w-8 p-0 opacity-0 transition-opacity group-hover:opacity-100"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onEdit();
          }}
          aria-label="Edit project"
        >
          <Pencil className="h-3.5 w-3.5" />
        </Button>
      )}
      <Link href={`/projects/${project.id}`} className="block">
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between pr-8">
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
      </Link>
    </Card>
  );
}
