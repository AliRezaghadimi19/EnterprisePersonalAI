export interface User {
  id: string;
  username: string;
  email?: string;
  first_name: string;
  last_name: string;
  auth_type: 'LOCAL' | 'ACTIVE_DIRECTORY';
  department?: string;
  role_name: string;
  role_display_name_fa: string;
  group_name?: string;
  permissions: string[];
  default_model_id?: string;
  allow_model_selection: boolean;
  policy: 'KNOWLEDGE_ONLY' | 'HYBRID' | 'FREE_AI';
  daily_quota_remaining: number;
  monthly_quota_remaining: number;
  can_upload_files: boolean;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface ActiveDirectoryConfig {
  id: string;
  is_enabled: boolean;
  server_host: string;
  port: number;
  port_ssl: number;
  use_ssl: boolean;
  domain_name: string;
  base_dn: string;
  user_search_base?: string;
  group_search_base?: string;
  bind_dn?: string;
  allowed_groups: string[];
  group_role_mapping: Record<string, string>;
  auto_provision: boolean;
  has_bind_password: boolean;
  updated_at: string;
}

export interface SystemSettings {
  auth_mode: 'BOTH' | 'LOCAL_ONLY' | 'AD_ONLY';
  default_response_policy: 'KNOWLEDGE_ONLY' | 'HYBRID' | 'FREE_AI';
  default_ai_language: string;
  max_file_size_mb: number;
  allow_file_upload_globally: boolean;
  session_timeout_minutes: number;
}
