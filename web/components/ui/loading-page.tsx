import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";

interface LoadingPageProps {
  label?: string;
  className?: string;
}

export function LoadingPage({ label = "Loading…", className }: LoadingPageProps) {
  return (
    <div
      className={cn(
        "flex min-h-[40vh] flex-col items-center justify-center gap-3",
        className
      )}
    >
      <Spinner className="h-8 w-8 text-primary" />
      <p className="text-sm text-muted-foreground">{label}</p>
    </div>
  );
}
