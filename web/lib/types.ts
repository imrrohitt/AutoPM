export type GlobalRole = "owner" | "admin" | "member";
export type ProjectRole = "manager" | "developer" | "viewer";

export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  global_role: GlobalRole;
  company_id: string;
  is_active: boolean;
}

export interface Company {
  id: string;
  name: string;
  slug: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  global_role: GlobalRole;
  is_active: boolean;
}

export interface Project {
  id: string;
  company_id: string;
  name: string;
  description?: string | null;
  goals?: string | null;
  tech_stack?: string | null;
  status: string;
  created_by?: string | null;
  created_at?: string;
  updated_at?: string;
  my_role?: ProjectRole | null;
}

export interface ProjectMember {
  id: string;
  project_id: string;
  user_id: string;
  role: ProjectRole;
  user?: User;
}

export interface Story {
  id: string;
  project_id: string;
  title: string;
  description?: string | null;
  acceptance_criteria?: string | null;
  priority: string;
  status: string;
  auto_merge?: boolean;
  created_by?: string | null;
  created_at?: string;
  updated_at?: string;
  tickets?: Ticket[];
}

export interface Ticket {
  id: string;
  story_id: string;
  project_id: string;
  title: string;
  description: string;
  type: string;
  priority: string;
  status: string;
  assigned_to?: string | null;
  agent_enabled: boolean;
  created_by?: string | null;
  created_at?: string;
  updated_at?: string;
  story?: Story;
}

export interface Comment {
  id: string;
  ticket_id: string;
  author_id?: string | null;
  is_agent: boolean;
  body: string;
  created_at: string;
}

export interface GitHubConnection {
  id: string;
  project_id: string;
  repo_owner: string | null;
  repo_name: string | null;
  default_branch: string;
  connected_at: string;
  last_indexed_at?: string | null;
  index_status: string;
  has_token?: boolean;
  is_connected?: boolean;
}

export interface GitHubRepo {
  owner: string;
  name: string;
  full_name: string;
  default_branch: string;
  private: boolean;
}

export interface LLMConfig {
  id: string;
  project_id: string;
  provider: string;
  model: string;
  api_key_masked?: string | null;
  base_url?: string | null;
  max_tokens: number;
  uses_base_url?: boolean;
  uses_api_key?: boolean;
}

export interface LLMProviderInfo {
  id: string;
  label: string;
  description: string;
  default_model: string;
  default_base_url: string | null;
  requires_api_key: boolean;
  requires_base_url: boolean;
}

export interface AgentRun {
  id: string;
  ticket_id?: string | null;
  story_id?: string | null;
  project_id: string;
  run_type?: string;
  current_ticket_id?: string | null;
  status: string;
  branch_name?: string | null;
  pr_url?: string | null;
  pr_number?: number | null;
  started_at?: string | null;
  completed_at?: string | null;
  error_message?: string | null;
  created_at: string;
}

export interface AgentLog {
  id: string;
  run_id: string;
  level: string;
  step?: string | null;
  message: string;
  metadata?: Record<string, unknown> | null;
  created_at: string;
}

export interface AgentFileChange {
  path: string;
  change_type: "read" | "staged" | "committed" | string;
  before_content?: string | null;
  after_content?: string | null;
  thought?: string | null;
  updated_at: string;
}

export interface AgentWorkspace {
  repo_owner?: string | null;
  repo_name?: string | null;
  branch?: string | null;
  tree: string[];
  changes: AgentFileChange[];
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface ApiError {
  detail?: string | { msg: string }[];
}
