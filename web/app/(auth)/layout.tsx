import { Logo } from "@/components/brand/Logo";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="brand-gradient flex min-h-screen flex-col items-center justify-center p-4">
      <div className="mb-8">
        <Logo size={56} textClassName="text-2xl font-bold" />
      </div>
      <div className="w-full max-w-md">{children}</div>
    </div>
  );
}
