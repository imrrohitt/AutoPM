"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { authApi } from "@/lib/api";
import { setTokens } from "@/lib/auth";
import { BRAND } from "@/lib/brand";
import { getErrorMessage } from "@/lib/utils";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [loading, setLoading] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const { data } = await authApi.login({ email, password });
      setTokens(data.access_token, data.refresh_token);
      toast.success("Welcome back");
      const from = searchParams.get("from") || "/projects";
      router.push(from);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="shadow-lg">
      <CardHeader className="text-center">
        <CardTitle className="text-2xl">Sign in to {BRAND.name}</CardTitle>
        <CardDescription>{BRAND.tagline}</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? <Spinner /> : "Sign in"}
          </Button>
        </form>
        <p className="mt-4 text-center text-sm text-muted-foreground">
          No account?{" "}
          <Link href="/register" className="text-primary hover:underline">
            Register
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<Spinner className="mx-auto" />}>
      <LoginForm />
    </Suspense>
  );
}
