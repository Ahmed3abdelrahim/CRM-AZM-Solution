/**
 * Minimal typed fetch wrapper over the backend's `/api/v1` surface — plan.md's file tree calls
 * this "a typed client generated from contracts/openapi.yaml"; no codegen pipeline exists yet
 * (out of Batch 4c's task list), so this is hand-written and covers only what the customers
 * pages (T066/T067) and their branch/department pickers call. Later batches extend it as they
 * consume more of the API, or replace it with a generated client wholesale.
 *
 * No login page exists anywhere in tasks.md yet (every batch through 4i), so there is
 * deliberately no login() helper here either — this reads whatever bearer token a caller has
 * already put in localStorage (e.g. via `/docs`'s Swagger UI against `POST /auth/login`).
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

const ACCESS_TOKEN_STORAGE_KEY = "crm_access_token";

export interface Branch {
  id: string;
  label_ar: string;
  label_en: string;
  code: string;
  timezone: string;
  is_active: boolean;
}

export interface Department {
  id: string;
  label_ar: string;
  label_en: string;
  branch_id: string;
  code: string;
  is_active: boolean;
}

export type ContactMethodKind = "phone" | "email" | "whatsapp" | "other";

export interface ContactMethod {
  id: string;
  customer_id: string;
  kind: ContactMethodKind;
  value: string;
  is_primary: boolean;
  is_verified: boolean;
}

export interface ContactMethodCreate {
  kind: ContactMethodKind;
  value: string;
  is_primary: boolean;
}

export type CustomerType = "individual" | "organization";
export type Locale = "ar" | "en";

export interface Customer {
  id: string;
  branch_id: string;
  department_id: string;
  customer_type: CustomerType;
  full_name_ar: string;
  full_name_en: string | null;
  national_id: string | null;
  organization_name: string | null;
  preferred_locale: Locale;
  notes: string | null;
  is_active: boolean;
}

export interface CustomerCreate {
  branch_id: string;
  department_id: string;
  customer_type: CustomerType;
  full_name_ar: string;
  full_name_en?: string | null;
  national_id?: string | null;
  organization_name?: string | null;
  preferred_locale: Locale;
  notes?: string | null;
  contact_methods: ContactMethodCreate[];
}

export interface TicketSummary {
  id: string;
  reference_no: string;
  subject: string;
  status_id: string;
  priority_id: string;
  category_id: string;
  assignee_id: string | null;
  team_id: string | null;
  channel: string;
  source_locale: Locale;
  needs_triage: boolean;
  created_at: string;
}

export interface TicketEvent {
  id: string;
  ticket_id: string;
  actor_id: string | null;
  event_type: string;
  field_name: string | null;
  old_value: unknown;
  new_value: unknown;
  body: string | null;
  visibility: "internal" | "customer";
  reason: string | null;
  correlation_id: string;
  created_at: string;
}

export interface CustomerHistory {
  tickets: TicketSummary[];
  events: TicketEvent[];
}

export interface Attachment {
  id: string;
  ticket_id: string | null;
  customer_id: string | null;
  filename: string;
  content_type: string;
  size_bytes: number;
  storage_key: string;
}

export interface TicketStatus {
  id: string;
  label_ar: string;
  label_en: string;
  branch_id: string;
  department_id: string | null;
  code: string;
  is_terminal: boolean;
  pauses_sla: boolean;
  sort_order: number;
}

export interface Ticket {
  id: string;
  reference_no: string;
  subject: string;
  description: string;
  status_id: string;
  priority_id: string;
  category_id: string;
  assignee_id: string | null;
  team_id: string | null;
  channel: string;
  source_locale: Locale;
  needs_triage: boolean;
  created_at: string;
  branch_id: string;
  department_id: string;
  customer_id: string;
  customer?: Customer;
  sla_policy_id: string | null;
  first_response_at: string | null;
  resolved_at: string | null;
  closed_at: string | null;
  reopened_count: number;
  sla_paused_ms: number;
}

export interface TicketCreate {
  branch_id: string;
  department_id: string;
  customer_id: string;
  subject: string;
  description: string;
  category_id: string;
  priority_id: string;
  channel: string;
  source_locale: Locale;
  team_id?: string | null;
}

export interface Category {
  id: string;
  label_ar: string;
  label_en: string;
  branch_id: string;
  department_id: string | null;
  parent_id: string | null;
  is_active: boolean;
  sort_order: number;
}

export interface Priority {
  id: string;
  label_ar: string;
  label_en: string;
  branch_id: string;
  department_id: string | null;
  code: string;
  severity: number;
  color: string;
}

export interface User {
  id: string;
  branch_id: string;
  department_id: string | null;
  email: string;
  full_name_ar: string;
  full_name_en: string;
  phone: string | null;
  locale: Locale;
  is_active: boolean;
}

export interface QuickReply {
  id: string;
  label_ar: string;
  label_en: string;
  branch_id: string;
  department_id: string;
  category_id: string | null;
  body_ar: string;
  body_en: string;
}

export type TicketView = "my_open" | "team_queue" | "unassigned" | "breaching_soon" | "recently_closed";

export interface TicketListFilters {
  view?: TicketView;
  status_id?: string;
  priority_id?: string;
  category_id?: string;
  assignee_id?: string;
  channel?: string;
  date_from?: string;
  date_to?: string;
  q?: string;
}

export class ApiError extends Error {
  status: number;
  messageAr?: string;
  messageEn?: string;
  currentStatusId?: string;
  permittedStatusIds?: string[];

  constructor(
    status: number,
    messageAr?: string,
    messageEn?: string,
    currentStatusId?: string,
    permittedStatusIds?: string[],
  ) {
    super(messageEn ?? `Request failed with status ${status}`);
    this.status = status;
    this.messageAr = messageAr;
    this.messageEn = messageEn;
    this.currentStatusId = currentStatusId;
    this.permittedStatusIds = permittedStatusIds;
  }
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setAccessToken(token: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, token);
  } catch {
    // Best-effort only — see artifact-capabilities guidance on localStorage failures; a missing
    // token simply falls back to an unauthenticated request, which the backend rejects with 401.
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getAccessToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body !== undefined && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });

  if (!response.ok) {
    const body: {
      message_ar?: string;
      message_en?: string;
      current_status_id?: string;
      permitted_status_ids?: string[];
    } | null = await response.json().catch(() => null);
    throw new ApiError(
      response.status,
      body?.message_ar,
      body?.message_en,
      body?.current_status_id,
      body?.permitted_status_ids,
    );
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

function searchParams(params: Record<string, string | number | undefined>): string {
  const usp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") usp.set(key, String(value));
  }
  const qs = usp.toString();
  return qs ? `?${qs}` : "";
}

export const api = {
  listBranches(): Promise<Branch[]> {
    return request(`/branches${searchParams({ limit: 200 })}`);
  },
  listDepartments(): Promise<Department[]> {
    return request(`/departments${searchParams({ limit: 200 })}`);
  },
  listCustomers(q: string | undefined, limit = 50, offset = 0): Promise<Customer[]> {
    return request(`/customers${searchParams({ q, limit, offset })}`);
  },
  createCustomer(data: CustomerCreate): Promise<Customer> {
    return request("/customers", { method: "POST", body: JSON.stringify(data) });
  },
  getCustomer(id: string): Promise<Customer> {
    return request(`/customers/${id}`);
  },
  deactivateCustomer(id: string): Promise<Customer> {
    return request(`/customers/${id}/deactivate`, { method: "POST" });
  },
  getCustomerHistory(id: string): Promise<CustomerHistory> {
    return request(`/customers/${id}/history`);
  },
  listContactMethods(id: string): Promise<ContactMethod[]> {
    return request(`/customers/${id}/contact-methods`);
  },
  addContactMethod(id: string, data: ContactMethodCreate): Promise<ContactMethod> {
    return request(`/customers/${id}/contact-methods`, { method: "POST", body: JSON.stringify(data) });
  },
  uploadCustomerAttachment(id: string, file: File): Promise<Attachment> {
    const form = new FormData();
    form.append("file", file);
    return request(`/customers/${id}/attachments`, { method: "POST", body: form });
  },
  listTicketStatuses(): Promise<TicketStatus[]> {
    return request(`/ticket-statuses${searchParams({ limit: 200 })}`);
  },
  listCategories(): Promise<Category[]> {
    return request(`/categories${searchParams({ limit: 200 })}`);
  },
  listPriorities(): Promise<Priority[]> {
    return request(`/priorities${searchParams({ limit: 200 })}`);
  },
  listUsers(): Promise<User[]> {
    return request(`/users${searchParams({ limit: 200 })}`);
  },
  listQuickReplies(): Promise<QuickReply[]> {
    return request(`/quick-replies${searchParams({ limit: 200 })}`);
  },
  listTickets(filters: TicketListFilters, limit = 50, offset = 0): Promise<TicketSummary[]> {
    return request(
      `/tickets${searchParams({
        view: filters.view,
        status_id: filters.status_id,
        priority_id: filters.priority_id,
        category_id: filters.category_id,
        assignee_id: filters.assignee_id,
        channel: filters.channel,
        date_from: filters.date_from,
        date_to: filters.date_to,
        q: filters.q,
        limit,
        offset,
      })}`,
    );
  },
  getTicket(id: string): Promise<Ticket> {
    return request(`/tickets/${id}`);
  },
  createTicket(data: TicketCreate): Promise<Ticket> {
    return request("/tickets", { method: "POST", body: JSON.stringify(data) });
  },
  getTicketEvents(id: string): Promise<TicketEvent[]> {
    return request(`/tickets/${id}/events`);
  },
  changeTicketStatus(id: string, toStatusId: string, reason?: string): Promise<Ticket> {
    return request(`/tickets/${id}/status`, {
      method: "POST",
      body: JSON.stringify({ to_status_id: toStatusId, reason: reason || null }),
    });
  },
  assignTicket(id: string, assigneeId: string | null): Promise<Ticket> {
    return request(`/tickets/${id}/assign`, { method: "POST", body: JSON.stringify({ assignee_id: assigneeId }) });
  },
  addTicketNote(id: string, body: string): Promise<TicketEvent> {
    return request(`/tickets/${id}/notes`, { method: "POST", body: JSON.stringify({ body }) });
  },
  addTicketReply(id: string, body: string): Promise<TicketEvent> {
    return request(`/tickets/${id}/replies`, { method: "POST", body: JSON.stringify({ body }) });
  },
  uploadTicketAttachment(id: string, file: File): Promise<Attachment> {
    const form = new FormData();
    form.append("file", file);
    return request(`/tickets/${id}/attachments`, { method: "POST", body: form });
  },
};
