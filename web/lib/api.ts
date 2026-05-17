import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";
import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  isAuthPath,
  setTokens,
} from "./auth";
import type {
  AgentLog,
  AgentRun,
  Comment,
  Company,
  GitHubConnection,
  GitHubRepo,
  LLMConfig,
  LLMProviderInfo,
  Project,
  ProjectMember,
  Story,
  Ticket,
  TokenResponse,
  User,
  UserProfile,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_BASE = `${API_URL}/api/v1`;

export const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

let refreshPromise: Promise<string> | null = null;

async function refreshAccessToken(): Promise<string> {
  const refresh = getRefreshToken();
  if (!refresh) throw new Error("No refresh token");
  const { data } = await axios.post<TokenResponse>(`${API_BASE}/auth/refresh`, {
    refresh_token: refresh,
  });
  setTokens(data.access_token, data.refresh_token);
  return data.access_token;
}

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

function isAuthEndpoint(url?: string): boolean {
  if (!url) return false;
  return (
    url.includes("/auth/login") ||
    url.includes("/auth/register") ||
    url.includes("/auth/refresh")
  );
}

api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & { _retry?: boolean };
    if (error.response?.status === 401 && original && !original._retry) {
      const requestUrl = original.url ?? "";

      if (isAuthEndpoint(requestUrl)) {
        return Promise.reject(error);
      }

      if (!getRefreshToken()) {
        clearTokens();
        if (typeof window !== "undefined" && !isAuthPath()) {
          window.location.href = "/login";
        }
        return Promise.reject(error);
      }

      original._retry = true;
      try {
        if (!refreshPromise) {
          refreshPromise = refreshAccessToken().finally(() => {
            refreshPromise = null;
          });
        }
        const token = await refreshPromise;
        original.headers.Authorization = `Bearer ${token}`;
        return api(original);
      } catch {
        clearTokens();
        if (typeof window !== "undefined" && !isAuthPath()) {
          window.location.href = "/login";
        }
      }
    }
    return Promise.reject(error);
  }
);

// Auth
export const authApi = {
  register: (body: {
    company_name: string;
    email: string;
    full_name: string;
    password: string;
  }) => api.post<TokenResponse>("/auth/register", body),
  login: (body: { email: string; password: string }) =>
    api.post<TokenResponse>("/auth/login", body),
  logout: () => api.post("/auth/logout"),
  me: () => api.get<UserProfile>("/auth/me"),
};

// Company & users
export const companyApi = {
  get: () => api.get<Company>("/company"),
};

export const usersApi = {
  list: () => api.get<User[]>("/users"),
  invite: (body: { email: string; full_name: string; global_role?: string }) =>
    api.post<User>("/users/invite", body),
  updateRole: (userId: string, global_role: string) =>
    api.patch<User>(`/users/${userId}/role`, { global_role }),
  deactivate: (userId: string) => api.delete<User>(`/users/${userId}`),
};

// Projects
export const projectsApi = {
  list: () => api.get<Project[]>("/projects"),
  create: (body: Partial<Project>) => api.post<Project>("/projects", body),
  get: (id: string) => api.get<Project>(`/projects/${id}`),
  update: (id: string, body: Partial<Project>) =>
    api.patch<Project>(`/projects/${id}`, body),
  delete: (id: string) => api.delete(`/projects/${id}`),
  members: {
    list: (projectId: string) =>
      api.get<ProjectMember[]>(`/projects/${projectId}/members`),
    add: (projectId: string, body: { user_id: string; role: string }) =>
      api.post<ProjectMember>(`/projects/${projectId}/members`, body),
    update: (projectId: string, userId: string, role: string) =>
      api.patch<ProjectMember>(`/projects/${projectId}/members/${userId}`, {
        role,
      }),
    remove: (projectId: string, userId: string) =>
      api.delete(`/projects/${projectId}/members/${userId}`),
  },
};

// GitHub
export const githubApi = {
  getConnection: (projectId: string) =>
    api.get<GitHubConnection | null>(`/projects/${projectId}/github`),
  saveToken: (projectId: string, github_token: string) =>
    api.put<GitHubConnection>(`/projects/${projectId}/github/token`, { github_token }),
  listRepos: (projectId: string) =>
    api.get<GitHubRepo[]>(`/projects/${projectId}/github/repos`),
  connect: (
    projectId: string,
    body: {
      repo_owner: string;
      repo_name: string;
      default_branch?: string;
      github_token?: string;
    }
  ) => api.post<GitHubConnection>(`/projects/${projectId}/github/connect`, body),
  disconnect: (projectId: string) =>
    api.delete(`/projects/${projectId}/github/disconnect`),
  triggerIndex: (projectId: string) =>
    api.post(`/projects/${projectId}/github/index`),
  indexStatus: (projectId: string) =>
    api.get<{ index_status: string }>(`/projects/${projectId}/github/index/status`),
};

// LLM
export const llmApi = {
  listProviders: () => api.get<LLMProviderInfo[]>("/llm/providers"),
  get: (projectId: string) => api.get<LLMConfig | null>(`/projects/${projectId}/llm`),
  save: (
    projectId: string,
    body: {
      provider: string;
      model: string;
      api_key?: string;
      base_url?: string;
      max_tokens?: number;
    }
  ) => api.post<LLMConfig>(`/projects/${projectId}/llm`, body),
  test: (projectId: string) =>
    api.post<{ success: boolean; message: string }>(`/projects/${projectId}/llm/test`),
};

// Stories
export const storiesApi = {
  list: (projectId: string) =>
    api.get<Story[]>(`/projects/${projectId}/stories`),
  create: (projectId: string, body: Partial<Story>) =>
    api.post<Story>(`/projects/${projectId}/stories`, body),
  get: (projectId: string, storyId: string) =>
    api.get<Story>(`/projects/${projectId}/stories/${storyId}`),
  update: (projectId: string, storyId: string, body: Partial<Story>) =>
    api.patch<Story>(`/projects/${projectId}/stories/${storyId}`, body),
  delete: (projectId: string, storyId: string) =>
    api.delete(`/projects/${projectId}/stories/${storyId}`),
};

// Tickets
export const ticketsApi = {
  list: (storyId: string) => api.get<Ticket[]>(`/stories/${storyId}/tickets`),
  create: (storyId: string, body: Partial<Ticket>) =>
    api.post<Ticket>(`/stories/${storyId}/tickets`, body),
  get: (id: string) => api.get<Ticket>(`/tickets/${id}`),
  update: (id: string, body: Partial<Ticket>) =>
    api.patch<Ticket>(`/tickets/${id}`, body),
  delete: (id: string) => api.delete(`/tickets/${id}`),
  enableAgent: (id: string) => api.post<Ticket>(`/tickets/${id}/enable-agent`),
  comments: {
    list: (ticketId: string) =>
      api.get<Comment[]>(`/tickets/${ticketId}/comments`),
    create: (ticketId: string, body: string) =>
      api.post<Comment>(`/tickets/${ticketId}/comments`, { body }),
  },
};

// Agent
export const agentApi = {
  runStory: (storyId: string, projectId: string) =>
    api.post<AgentRun>(`/stories/${storyId}/agent/run`, null, {
      params: { project_id: projectId },
    }),
  listStoryRuns: (storyId: string) =>
    api.get<AgentRun[]>(`/stories/${storyId}/agent/runs`),
  run: (ticketId: string) =>
    api.post<AgentRun>(`/tickets/${ticketId}/agent/run`),
  cancel: (runId: string) => api.post(`/agent/runs/${runId}/cancel`),
  listRuns: (ticketId: string) =>
    api.get<AgentRun[]>(`/tickets/${ticketId}/agent/runs`),
  getRun: (runId: string) => api.get<AgentRun>(`/agent/runs/${runId}`),
  getLogs: (runId: string) => api.get<AgentLog[]>(`/agent/runs/${runId}/logs`),
  streamUrl: (runId: string) => `${API_BASE}/agent/runs/${runId}/stream`,
};

export { API_BASE, API_URL };
