"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { BackLink } from "@/components/ui/back-link";
import { LoadingPage } from "@/components/ui/loading-page";
import { Spinner } from "@/components/ui/spinner";
import { llmApi } from "@/lib/api";
import { useAuth } from "@/lib/hooks/useAuth";
import { useProject } from "@/lib/hooks/useProjects";
import { canConfigureIntegrations } from "@/lib/permissions";
import type { LLMConfig, LLMProviderInfo } from "@/lib/types";
import { getErrorMessage } from "@/lib/utils";

const FALLBACK_PROVIDERS: LLMProviderInfo[] = [
  {
    id: "anthropic",
    label: "Anthropic (Claude)",
    description: "Cloud Claude API — API key + model name only",
    default_model: "claude-sonnet-4-20250514",
    default_base_url: null,
    requires_api_key: true,
    requires_base_url: false,
  },
  {
    id: "ollama",
    label: "Ollama (local)",
    description: "Local Ollama — base URL + model (uses /api/generate)",
    default_model: "gemma:2b",
    default_base_url: "http://localhost:11434",
    requires_api_key: false,
    requires_base_url: true,
  },
  {
    id: "litellm",
    label: "LiteLLM / OpenAI-compatible",
    description: "LiteLLM proxy — base URL, API key (optional), model",
    default_model: "gemma:2b",
    default_base_url: "http://localhost:4000",
    requires_api_key: false,
    requires_base_url: true,
  },
  {
    id: "openai",
    label: "OpenAI",
    description: "OpenAI API",
    default_model: "gpt-4o-mini",
    default_base_url: "https://api.openai.com/v1",
    requires_api_key: true,
    requires_base_url: true,
  },
  {
    id: "groq",
    label: "Groq",
    description: "Groq OpenAI-compatible API",
    default_model: "llama-3.3-70b-versatile",
    default_base_url: "https://api.groq.com/openai/v1",
    requires_api_key: true,
    requires_base_url: true,
  },
];

export default function LLMSettingsPage() {
  const params = useParams();
  const projectId = params.projectId as string;
  const { user } = useAuth();
  const { project } = useProject(projectId);
  const [config, setConfig] = useState<LLMConfig | null>(null);
  const [providers, setProviders] = useState<LLMProviderInfo[]>(FALLBACK_PROVIDERS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [form, setForm] = useState({
    provider: "ollama",
    model: "gemma:2b",
    api_key: "",
    base_url: "http://localhost:11434",
    max_tokens: 8192,
  });

  const selectedProvider =
    providers.find((p) => p.id === form.provider) ??
    FALLBACK_PROVIDERS.find((p) => p.id === form.provider);

  const showBaseUrl = selectedProvider?.requires_base_url ?? form.provider !== "anthropic";
  const showApiKey = selectedProvider?.requires_api_key ?? form.provider === "anthropic";

  const canEdit =
    user && project
      ? canConfigureIntegrations(user.global_role, project.my_role)
      : false;

  const applyProviderDefaults = (providerId: string) => {
    const p = providers.find((x) => x.id === providerId) ?? FALLBACK_PROVIDERS.find((x) => x.id === providerId);
    if (!p) return;
    setForm((prev) => ({
      ...prev,
      provider: providerId,
      model: p.default_model,
      base_url: p.default_base_url || "",
      api_key: "",
    }));
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [configRes, providersRes] = await Promise.all([
        llmApi.get(projectId),
        llmApi.listProviders().catch(() => ({ data: FALLBACK_PROVIDERS })),
      ]);
      setProviders(providersRes.data);
      setConfig(configRes.data);
      if (configRes.data) {
        setForm({
          provider: configRes.data.provider,
          model: configRes.data.model,
          api_key: "",
          base_url: configRes.data.base_url || "",
          max_tokens: configRes.data.max_tokens,
        });
      }
    } catch {
      setConfig(null);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const { data } = await llmApi.save(projectId, {
        provider: form.provider,
        model: form.model.trim(),
        api_key: form.api_key.trim() || undefined,
        base_url: showBaseUrl ? form.base_url.trim() || undefined : undefined,
        max_tokens: form.max_tokens,
      });
      setConfig(data);
      setForm((f) => ({ ...f, api_key: "" }));
      toast.success("LLM configuration saved");
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    try {
      const { data } = await llmApi.test(projectId);
      if (data.success) toast.success(data.message || "Connection OK");
      else toast.error(data.message || "Connection failed");
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setTesting(false);
    }
  };

  if (loading) return <LoadingPage label="Loading LLM settings…" />;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <BackLink href={`/projects/${projectId}`}>Back to project</BackLink>
      <div>
        <h2 className="text-2xl font-bold tracking-tight">LLM configuration</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Per-project model settings. Ollama uses{" "}
          <code className="rounded bg-muted px-1">/api/generate</code>; LiteLLM uses OpenAI-compatible{" "}
          <code className="rounded bg-muted px-1">/v1/chat/completions</code>.
        </p>
      </div>

      {config && (
        <Card className="border-primary/20 bg-primary/5">
          <CardContent className="pt-4 text-sm">
            <p>
              <span className="text-muted-foreground">Saved: </span>
              <Badge variant="secondary" className="capitalize">
                {config.provider}
              </Badge>{" "}
              <span className="font-mono">{config.model}</span>
            </p>
            {config.base_url && (
              <p className="mt-1 font-mono text-xs text-muted-foreground">{config.base_url}</p>
            )}
            <p className="mt-1 text-muted-foreground">
              API key: {config.api_key_masked || "not set (optional for local)"}
            </p>
          </CardContent>
        </Card>
      )}

      {canEdit ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Connection settings</CardTitle>
            <CardDescription>
              {selectedProvider?.description ||
                "Choose a provider and enter base URL, API key, and model name."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSave} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="provider">Provider</Label>
                <Select
                  id="provider"
                  value={form.provider}
                  onChange={(e) => applyProviderDefaults(e.target.value)}
                >
                  {providers.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label}
                    </option>
                  ))}
                </Select>
              </div>

              {showBaseUrl && (
                <div className="space-y-2">
                  <Label htmlFor="base_url">Base URL</Label>
                  <Input
                    id="base_url"
                    value={form.base_url}
                    onChange={(e) => setForm({ ...form, base_url: e.target.value })}
                    placeholder={
                      form.provider === "ollama"
                        ? "http://localhost:11434"
                        : "http://localhost:4000"
                    }
                  />
                  <p className="text-xs text-muted-foreground">
                    {form.provider === "ollama"
                      ? "Ollama server URL (no /api/generate suffix)."
                      : "LiteLLM or OpenAI-compatible root URL."}
                  </p>
                </div>
              )}

              <div className="space-y-2">
                <Label htmlFor="model">Model name</Label>
                <Input
                  id="model"
                  value={form.model}
                  onChange={(e) => setForm({ ...form, model: e.target.value })}
                  placeholder={selectedProvider?.default_model || "gemma:2b"}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="api_key">
                  API key {showApiKey ? "" : "(optional)"}
                </Label>
                <Input
                  id="api_key"
                  type="password"
                  placeholder={
                    config?.api_key_masked
                      ? `Saved: ${config.api_key_masked} — leave blank to keep`
                      : showApiKey
                        ? "Required"
                        : "Optional for local Ollama / LiteLLM"
                  }
                  value={form.api_key}
                  onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                />
                <p className="text-xs text-muted-foreground">
                  Encrypted and stored per project — never sent in the URL.
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="max_tokens">Max tokens</Label>
                <Input
                  id="max_tokens"
                  type="number"
                  value={form.max_tokens}
                  onChange={(e) =>
                    setForm({ ...form, max_tokens: parseInt(e.target.value, 10) || 8192 })
                  }
                />
              </div>

              <div className="flex flex-wrap gap-2">
                <Button type="submit" disabled={saving}>
                  {saving ? <Spinner /> : "Save configuration"}
                </Button>
                {config && (
                  <Button type="button" variant="outline" onClick={handleTest} disabled={testing}>
                    {testing ? <Spinner /> : "Test connection"}
                  </Button>
                )}
              </div>
            </form>
          </CardContent>
        </Card>
      ) : (
        <p className="text-muted-foreground">You do not have permission to edit LLM settings.</p>
      )}
    </div>
  );
}
