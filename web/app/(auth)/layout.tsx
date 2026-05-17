import { Wrench } from "lucide-react";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-br from-violet-50 via-background to-slate-50 p-4">
      <div className="mb-8 flex items-center gap-2.5">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
          <Wrench className="h-5 w-5" />
        </div>
        <span className="text-xl font-bold tracking-tight text-foreground">AutoPM</span>
      </div>
      <div className="w-full max-w-md">{children}</div>
    </div>
  );
}
