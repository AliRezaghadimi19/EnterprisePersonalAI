/**
 * Admin-specific types — dashboard stats, audit logs, admin conversations, usage reports.
 */

export interface DashboardTotals {
  users: number;
  active_users: number;
  groups: number;
  conversations: number;
  messages: number;
  documents: number;
  providers: number;
  models: number;
}

export interface MessagesPerDay {
  [key: string]: string | number;
  date: string;
  count: number;
  tokens: number;
}

export interface MessagesPerModel {
  [key: string]: string | number | undefined;
  model_id: string;
  model_name: string;
  count: number;
  tokens: number;
}

export interface UsersPerGroup {
  [key: string]: string | number | undefined;
  group_id: string;
  group_name: string;
  count: number;
}

export interface PolicyDistribution {
  [key: string]: string | number;
  policy: string;
  count: number;
}

export interface TopUser {
  user_id: string;
  username: string;
  full_name: string;
  message_count: number;
}

export interface DashboardStats {
  totals: DashboardTotals;
  messages_per_day: MessagesPerDay[];
  messages_per_model: MessagesPerModel[];
  users_per_group: UsersPerGroup[];
  policy_distribution: PolicyDistribution[];
  top_users: TopUser[];
  auth_types: { LOCAL: number; ACTIVE_DIRECTORY: number };
  token_usage: { today: number; month: number; estimated_cost: number; questions_today: number; questions_month: number };
}

export interface AuditLogEntry {
  id: string;
  actor_user_id: string | null;
  actor_username: string | null;
  action_type: string;
  target_resource: string;
  target_id: string | null;
  old_values: Record<string, unknown> | null;
  new_values: Record<string, unknown> | null;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
}

export interface PagedAuditLogs {
  items: AuditLogEntry[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminConversation {
  id: string;
  title: string;
  user_id: string;
  username: string;
  full_name: string;
  model_id: string | null;
  is_pinned: boolean | number;
  messages_count: number;
  last_message_preview: string | null;
  created_at: string;
  updated_at: string;
}

export interface PagedConversations {
  items: AdminConversation[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminConversationMessage {
  id: string;
  sender_role: 'user' | 'assistant';
  content: string;
  model_id: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  processing_time_sec: number | null;
  created_at: string;
}

export interface AdminConversationDetail extends AdminConversation {
  messages: AdminConversationMessage[];
}

export interface UsageReportRow {
  bucket: string;
  label?: string;
  question_count: number;
  total_tokens: number;
  estimated_cost: number;
}

export interface UsageReport {
  rows: UsageReportRow[];
  summary: {
    total_questions: number;
    total_tokens: number;
    total_cost: number;
    active_users: number;
  };
}
