/**
 * Admin entity types — list items returned by users/groups/roles/providers/models/knowledge endpoints.
 */

export interface AdminUserListItem {
  id: string;
  username: string;
  email?: string | null;
  first_name: string;
  last_name: string;
  full_name?: string;
  auth_type: 'LOCAL' | 'ACTIVE_DIRECTORY';
  department?: string | null;
  role_id?: string | null;
  role_name?: string | null;
  role_display_name_fa?: string | null;
  group_id?: string | null;
  group_name?: string | null;
  is_active: boolean | number;
  expires_at?: string | null;
  default_model_id?: string | null;
  allow_model_selection?: boolean | number;
  override_policy?: string | null;
  custom_daily_limit?: number | null;
  custom_monthly_limit?: number | null;
  can_upload_files?: boolean | number;
  created_at?: string;
  today_questions?: number;
  month_questions?: number;
  daily_quota_remaining?: number;
  monthly_quota_remaining?: number;
}

export interface AdminGroup {
  id: string;
  name: string;
  description?: string | null;
  default_policy: 'KNOWLEDGE_ONLY' | 'HYBRID' | 'FREE_AI';
  default_model_id?: string | null;
  allow_model_selection: boolean | number;
  daily_question_limit: number;
  monthly_question_limit: number;
  daily_token_limit: number;
  monthly_token_limit: number;
  max_file_size_mb: number;
  allowed_file_types?: string[] | string | null;
  created_at?: string;
  member_count?: number;
}

export interface AdminRole {
  id: string;
  name: string;
  display_name_fa: string;
  permissions: string[];
  is_system: boolean | number;
  created_at?: string;
}

export interface AdminProvider {
  id: string;
  name: string;
  provider_type: 'OPENAI' | 'ANTHROPIC' | 'GEMINI' | 'CUSTOM' | 'OPENAI_COMPATIBLE' | 'MOCK';
  base_url?: string | null;
  is_active: boolean | number;
  has_api_key?: boolean;
  created_at?: string;
}

export interface AdminModel {
  id: string;
  provider_id: string;
  provider_name?: string;
  model_identifier: string;
  display_name_fa: string;
  is_active: boolean | number;
  is_default: boolean | number;
  input_cost_per_k_tokens: number;
  output_cost_per_k_tokens: number;
  max_context_tokens: number;
  fallback_model_id?: string | null;
  created_at?: string;
}

export interface KnowledgeCategory {
  id: string;
  name: string;
  description?: string | null;
  created_at?: string;
  documents_count?: number;
}

export interface KnowledgeDocument {
  id: string;
  category_id: string | null;
  category_name?: string | null;
  title: string;
  document_type: 'FAQ' | 'PDF' | 'DOCX' | 'TXT' | string;
  content_text: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | string;
  version?: number;
  created_by?: string | null;
  created_at?: string;
  tags?: string[];
  keywords?: string[];
  allowed_group_ids?: string[];
}