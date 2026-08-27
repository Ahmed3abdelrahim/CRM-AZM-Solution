"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { LtrText } from "@/components/ltr-text";
import {
  api,
  ApiError,
  type Category,
  type KbSearchResult,
  type QuickReply,
  type Ticket,
  type User,
} from "@/lib/api-client";

/** F04 (T086) — substitutes `{{customer_name}}`/`{{reference_no}}`/`{{agent_name}}` into a
 * quick reply's body, matching the ticket's `source_locale` — the client-side mirror of
 * `backend/app/services/quick_reply_render.py`'s pure `render()` (T082); `{{agent_name}}`
 * resolves the ticket's current assignee the same way that function does. */
function renderQuickReply(quickReply: QuickReply, ticket: Ticket, users: User[]): string {
  const body = ticket.source_locale === "ar" ? quickReply.body_ar : quickReply.body_en;
  const customerName = ticket.customer
    ? ticket.source_locale === "ar"
      ? ticket.customer.full_name_ar
      : ticket.customer.full_name_en ?? ticket.customer.full_name_ar
    : "";
  const assignee = ticket.assignee_id ? users.find((u) => u.id === ticket.assignee_id) : undefined;
  const agentName = assignee
    ? ticket.source_locale === "ar"
      ? assignee.full_name_ar
      : assignee.full_name_en
    : "";
  return body
    .replaceAll("{{customer_name}}", customerName)
    .replaceAll("{{reference_no}}", ticket.reference_no)
    .replaceAll("{{agent_name}}", agentName);
}

/** T079 — ticket detail, status-change control (surfacing the localized illegal-transition
 * error), assignment, timeline, notes/replies, attachments, inline customer context (FR-028).
 * T086 adds the quick-reply picker to the composer and visually distinguishes internal notes. */
export default function TicketDetailPage() {
  const t = useTranslations("TicketDetail");
  const params = useParams<{ id: string }>();
  const ticketId = params.id;
  const queryClient = useQueryClient();

  const ticketQuery = useQuery({
    queryKey: ["ticket", ticketId],
    queryFn: () => api.getTicket(ticketId),
  });
  const eventsQuery = useQuery({
    queryKey: ["ticket", ticketId, "events"],
    queryFn: () => api.getTicketEvents(ticketId),
  });
  const statusesQuery = useQuery({
    queryKey: ["ticket-statuses"],
    queryFn: api.listTicketStatuses,
  });
  const quickRepliesQuery = useQuery({
    queryKey: ["quick-replies"],
    queryFn: api.listQuickReplies,
  });
  const usersQuery = useQuery({
    queryKey: ["users"],
    queryFn: api.listUsers,
  });
  const categoriesQuery = useQuery({
    queryKey: ["categories"],
    queryFn: api.listCategories,
  });
  const suggestedSolutionQuery = useQuery({
    queryKey: ["ticket", ticketId, "ai-suggested-solution"],
    queryFn: () => api.getAiSuggestedSolution(ticketId),
  });

  const invalidateTicket = () => {
    queryClient.invalidateQueries({ queryKey: ["ticket", ticketId] });
    queryClient.invalidateQueries({ queryKey: ["ticket", ticketId, "events"] });
  };

  if (ticketQuery.isLoading) {
    return <p className="p-6">{t("loading")}</p>;
  }
  if (ticketQuery.isError) {
    return <p className="p-6" role="alert">{t("error")}</p>;
  }
  const ticket = ticketQuery.data;
  if (!ticket) {
    return <p className="p-6">{t("notFound")}</p>;
  }

  const statuses = statusesQuery.data ?? [];
  const statusLabel = (id: string) => {
    const found = statuses.find((s) => s.id === id);
    return found ? `${found.label_ar} / ${found.label_en}` : id;
  };

  return (
    <main className="mx-auto max-w-3xl p-6">
      <Link href="/dashboard" className="underline">
        {t("backLink")}
      </Link>

      <h1 className="mt-2 text-2xl font-bold" dir="auto">
        <LtrText>{ticket.reference_no}</LtrText> — {ticket.subject}
      </h1>
      <p className="mt-1 text-sm text-gray-600" dir="auto">
        {ticket.description}
      </p>

      <section className="mt-4">
        <h2 className="font-semibold">{t("customerTitle")}</h2>
        {ticket.customer ? (
          <p>
            {ticket.customer.full_name_ar}
            {ticket.customer.full_name_en ? ` / ${ticket.customer.full_name_en}` : ""}
          </p>
        ) : (
          <p>{t("noCustomer")}</p>
        )}
      </section>

      <AiCategorizationPanel
        ticketId={ticketId}
        ticket={ticket}
        categories={categoriesQuery.data ?? []}
        onDecided={invalidateTicket}
      />

      <AiSummaryPanel ticketId={ticketId} />

      <section className="mt-6 rounded border p-4">
        <h2 className="font-semibold">{t("statusTitle")}</h2>
        <p className="mt-1">
          {t("currentStatus")}: {statusLabel(ticket.status_id)}
        </p>
        <p className="text-sm text-gray-600">
          {t("reopenedCount")}: {ticket.reopened_count}
        </p>
        {ticket.first_response_at && (
          <p className="text-sm text-gray-600">
            {t("firstResponseAt")}: <LtrText>{new Date(ticket.first_response_at).toISOString()}</LtrText>
          </p>
        )}
        <ChangeStatusForm ticketId={ticketId} statuses={statuses} statusLabel={statusLabel} onChanged={invalidateTicket} />
      </section>

      <section className="mt-6 rounded border p-4">
        <h2 className="font-semibold">{t("assignTitle")}</h2>
        <AssignForm ticketId={ticketId} currentAssigneeId={ticket.assignee_id} onAssigned={invalidateTicket} />
      </section>

      <AiSuggestedSolutionPanel articles={suggestedSolutionQuery.data ?? []} />

      <section className="mt-6">
        <h2 className="font-semibold">{t("composerTitle")}</h2>
        <ComposerForm
          ticketId={ticketId}
          ticket={ticket}
          quickReplies={quickRepliesQuery.data ?? []}
          users={usersQuery.data ?? []}
          onSent={invalidateTicket}
        />
      </section>

      <section className="mt-6">
        <h2 className="font-semibold">{t("timelineTitle")}</h2>
        {(eventsQuery.data ?? []).length === 0 ? (
          <p>{t("noEvents")}</p>
        ) : (
          <ul className="mt-2 flex flex-col gap-1">
            {eventsQuery.data?.map((event) => (
              <li
                key={event.id}
                className={
                  event.visibility === "internal"
                    ? "rounded border border-amber-300 bg-amber-50 p-2 text-sm"
                    : "rounded border border-sky-300 bg-sky-50 p-2 text-sm"
                }
              >
                <span className="font-semibold">{event.event_type}</span>{" "}
                <span
                  className={
                    event.visibility === "internal"
                      ? "rounded bg-amber-200 px-1 text-xs text-amber-900"
                      : "rounded bg-sky-200 px-1 text-xs text-sky-900"
                  }
                >
                  {event.visibility === "internal" ? t("visibilityInternal") : t("visibilityCustomer")}
                </span>
                {event.body && (
                  <p dir="auto">{event.body}</p>
                )}
                {event.reason && (
                  <p className="text-gray-600" dir="auto">
                    {event.reason}
                  </p>
                )}
                <LtrText>{new Date(event.created_at).toISOString()}</LtrText>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="mt-6">
        <h2 className="font-semibold">{t("attachmentsTitle")}</h2>
        <AttachmentUploadForm ticketId={ticketId} />
      </section>
    </main>
  );
}

function ChangeStatusForm({
  ticketId,
  statuses,
  statusLabel,
  onChanged,
}: {
  ticketId: string;
  statuses: { id: string; label_ar: string; label_en: string }[];
  statusLabel: (id: string) => string;
  onChanged: () => void;
}) {
  const t = useTranslations("TicketDetail");
  const [toStatusId, setToStatusId] = useState("");
  const [reason, setReason] = useState("");

  const changeStatusMutation = useMutation({
    mutationFn: () => api.changeTicketStatus(ticketId, toStatusId, reason || undefined),
    onSuccess: onChanged,
  });

  const apiError = changeStatusMutation.error instanceof ApiError ? changeStatusMutation.error : null;

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (toStatusId) changeStatusMutation.mutate();
  }

  return (
    <form onSubmit={handleSubmit} className="mt-3 flex flex-col gap-2">
      <h3 className="text-sm font-semibold text-gray-600">{t("changeStatusTitle")}</h3>
      <label className="flex flex-col gap-1">
        <span className="text-sm text-gray-600">{t("newStatusLabel")}</span>
        <select
          required
          value={toStatusId}
          onChange={(event) => setToStatusId(event.target.value)}
          className="rounded border px-3 py-2"
        >
          <option value="" />
          {statuses.map((s) => (
            <option key={s.id} value={s.id}>
              {s.label_ar} / {s.label_en}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1">
        <span className="text-sm text-gray-600">{t("reasonLabel")}</span>
        <input
          type="text"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          className="rounded border px-3 py-2"
        />
      </label>
      <button type="submit" disabled={changeStatusMutation.isPending} className="w-fit rounded border px-3 py-2">
        {t("changeStatusButton")}
      </button>
      {apiError && (
        <div role="alert" className="rounded border border-red-400 p-2 text-sm">
          <p>{apiError.messageAr}</p>
          <p>{apiError.messageEn}</p>
          {apiError.permittedStatusIds && apiError.permittedStatusIds.length > 0 && (
            <p>
              {t("illegalTransitionPermitted")}: {apiError.permittedStatusIds.map(statusLabel).join(", ")}
            </p>
          )}
        </div>
      )}
    </form>
  );
}

function AssignForm({
  ticketId,
  currentAssigneeId,
  onAssigned,
}: {
  ticketId: string;
  currentAssigneeId: string | null;
  onAssigned: () => void;
}) {
  const t = useTranslations("TicketDetail");
  const [assigneeId, setAssigneeId] = useState(currentAssigneeId ?? "");

  const assignMutation = useMutation({
    mutationFn: (value: string | null) => api.assignTicket(ticketId, value),
    onSuccess: onAssigned,
  });

  return (
    <div className="mt-2 flex flex-wrap items-end gap-2">
      <label className="flex flex-col gap-1">
        <span className="text-sm text-gray-600">{t("assigneeLabel")}</span>
        <input
          type="text"
          value={assigneeId}
          onChange={(event) => setAssigneeId(event.target.value)}
          className="rounded border px-3 py-2"
        />
      </label>
      <button
        type="button"
        onClick={() => assignMutation.mutate(assigneeId || null)}
        disabled={assignMutation.isPending || !assigneeId}
        className="rounded border px-3 py-2"
      >
        {t("assignButton")}
      </button>
      <button
        type="button"
        onClick={() => {
          setAssigneeId("");
          assignMutation.mutate(null);
        }}
        disabled={assignMutation.isPending}
        className="rounded border px-3 py-2"
      >
        {t("unassignButton")}
      </button>
      {assignMutation.isError && <p role="alert">{t("error")}</p>}
    </div>
  );
}

function ComposerForm({
  ticketId,
  ticket,
  quickReplies,
  users,
  onSent,
}: {
  ticketId: string;
  ticket: Ticket;
  quickReplies: QuickReply[];
  users: User[];
  onSent: () => void;
}) {
  const t = useTranslations("TicketDetail");
  const [body, setBody] = useState("");
  const [visibility, setVisibility] = useState<"internal" | "customer">("internal");
  const [quickReplyId, setQuickReplyId] = useState("");

  const applicableQuickReplies = quickReplies.filter(
    (quickReply) => quickReply.category_id === null || quickReply.category_id === ticket.category_id,
  );

  const sendMutation = useMutation({
    mutationFn: () =>
      visibility === "internal" ? api.addTicketNote(ticketId, body) : api.addTicketReply(ticketId, body),
    onSuccess: () => {
      setBody("");
      onSent();
    },
  });

  /* T116 — suggested-reply-into-composer action. On-demand only (FR-046): the draft only ever
   * lands in this textarea for the agent to edit; nothing here ever calls addTicketReply itself. */
  const suggestReplyMutation = useMutation({
    mutationFn: () => api.getAiSuggestedReply(ticketId),
    onSuccess: (response) => {
      if (response.draft) {
        setBody(response.draft);
        setVisibility("customer");
      }
    },
  });

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (body.trim()) sendMutation.mutate();
  }

  return (
    <form onSubmit={handleSubmit} className="mt-2 flex flex-col gap-2 rounded border p-3">
      <div>
        <button
          type="button"
          onClick={() => suggestReplyMutation.mutate()}
          disabled={suggestReplyMutation.isPending}
          className="w-fit rounded border px-3 py-2 text-sm"
        >
          {t("aiSuggestReplyButton")}
        </button>
        {suggestReplyMutation.data?.fallback_used && (
          <p className="mt-1 text-sm text-gray-600">{t("aiSuggestReplyFallbackNote")}</p>
        )}
      </div>
      <label className="flex flex-col gap-1">
        <span className="text-sm text-gray-600">{t("quickReplyLabel")}</span>
        <select
          value={quickReplyId}
          onChange={(event) => {
            const id = event.target.value;
            setQuickReplyId(id);
            const quickReply = applicableQuickReplies.find((candidate) => candidate.id === id);
            if (quickReply) {
              setBody(renderQuickReply(quickReply, ticket, users));
              setVisibility("customer");
            }
          }}
          className="rounded border px-3 py-2"
        >
          <option value="">{t("quickReplyPlaceholder")}</option>
          {applicableQuickReplies.map((quickReply) => (
            <option key={quickReply.id} value={quickReply.id}>
              {quickReply.label_ar} / {quickReply.label_en}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1">
        <span className="text-sm text-gray-600">{t("composerBodyLabel")}</span>
        <textarea
          required
          dir="auto"
          value={body}
          onChange={(event) => setBody(event.target.value)}
          className="rounded border px-3 py-2"
          rows={3}
        />
      </label>
      <div className="flex items-center gap-4">
        <label className="flex items-center gap-1">
          <input
            type="radio"
            checked={visibility === "internal"}
            onChange={() => setVisibility("internal")}
          />
          <span className="text-sm text-gray-600">{t("composerInternalNote")}</span>
        </label>
        <label className="flex items-center gap-1">
          <input
            type="radio"
            checked={visibility === "customer"}
            onChange={() => setVisibility("customer")}
          />
          <span className="text-sm text-gray-600">{t("composerCustomerReply")}</span>
        </label>
      </div>
      {sendMutation.isError && <p role="alert">{t("error")}</p>}
      <button type="submit" disabled={sendMutation.isPending} className="w-fit rounded border px-3 py-2">
        {t("composerSubmit")}
      </button>
    </form>
  );
}

function AttachmentUploadForm({ ticketId }: { ticketId: string }) {
  const t = useTranslations("TicketDetail");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadMutation = useMutation({
    mutationFn: (file: File) => api.uploadTicketAttachment(ticketId, file),
  });

  return (
    <div>
      <input
        ref={fileInputRef}
        type="file"
        className="mt-2"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) uploadMutation.mutate(file);
        }}
      />
      {uploadMutation.isPending && <p>{t("uploading")}</p>}
      {uploadMutation.isError && <p role="alert">{t("error")}</p>}
    </div>
  );
}

/** T116 — on-demand AI summary panel (FR-045/FR-047). Fallback (first 300 chars of the
 * description) is surfaced identically to a real summary, with a note distinguishing the two. */
function AiSummaryPanel({ ticketId }: { ticketId: string }) {
  const t = useTranslations("TicketDetail");
  const summaryMutation = useMutation({
    mutationFn: () => api.getAiSummary(ticketId),
  });

  return (
    <section className="mt-6 rounded border p-4">
      <h2 className="font-semibold">{t("aiSummaryTitle")}</h2>
      <button
        type="button"
        onClick={() => summaryMutation.mutate()}
        disabled={summaryMutation.isPending}
        className="mt-2 w-fit rounded border px-3 py-2 text-sm"
      >
        {t("aiSummaryButton")}
      </button>
      {summaryMutation.data && (
        <div className="mt-2">
          <p dir="auto">{summaryMutation.data.summary}</p>
          {summaryMutation.data.fallback_used && (
            <p className="mt-1 text-sm text-gray-600">{t("aiSummaryFallbackNote")}</p>
          )}
        </div>
      )}
      {summaryMutation.isError && <p role="alert">{t("error")}</p>}
    </section>
  );
}

/** T116 — suggested-solution panel (FR-047). Fallback is an empty list; per PLAN.md F07 the
 * panel simply does not render rather than showing an empty-state message. `KbService` (Batch
 * 4g) is not built in this run, so `articles` is always `[]` for now — see
 * `backend/app/services/ai_service.py::suggest_solution`. */
function AiSuggestedSolutionPanel({ articles }: { articles: KbSearchResult[] }) {
  const t = useTranslations("TicketDetail");
  if (articles.length === 0) return null;

  return (
    <section className="mt-6 rounded border p-4">
      <h2 className="font-semibold">{t("aiSuggestedSolutionTitle")}</h2>
      <ul className="mt-2 flex flex-col gap-2">
        {articles.map((article, index) => (
          <li key={index} className="rounded border p-2 text-sm" dir="auto">
            {JSON.stringify(article)}
          </li>
        ))}
      </ul>
    </section>
  );
}

/** T116 — categorization-suggestion accept/override control (FR-044). Renders nothing until the
 * async `categorization_job` has actually populated a suggestion (or it fell back to none). */
function AiCategorizationPanel({
  ticketId,
  ticket,
  categories,
  onDecided,
}: {
  ticketId: string;
  ticket: Ticket;
  categories: Category[];
  onDecided: () => void;
}) {
  const t = useTranslations("TicketDetail");
  const [overrideCategoryId, setOverrideCategoryId] = useState("");

  const decisionMutation = useMutation({
    mutationFn: (payload: { accepted: boolean; overrideCategoryId?: string | null }) =>
      api.acceptAiCategorization(ticketId, payload.accepted, payload.overrideCategoryId),
    onSuccess: onDecided,
  });

  if (!ticket.ai_suggested_category_id) return null;

  const suggested = categories.find((category) => category.id === ticket.ai_suggested_category_id);

  return (
    <section className="mt-6 rounded border p-4">
      <h2 className="font-semibold">{t("aiCategorizationTitle")}</h2>
      <p className="mt-1" dir="auto">
        {suggested ? `${suggested.label_ar} / ${suggested.label_en}` : ticket.ai_suggested_category_id}
        {ticket.ai_category_confidence !== null && (
          <>
            {" — "}
            {t("aiCategorizationConfidence")}: {Math.round(ticket.ai_category_confidence * 100)}%
          </>
        )}
      </p>
      <div className="mt-2 flex flex-wrap items-end gap-2">
        <button
          type="button"
          onClick={() => decisionMutation.mutate({ accepted: true })}
          disabled={decisionMutation.isPending}
          className="rounded border px-3 py-2 text-sm"
        >
          {t("aiCategorizationAcceptButton")}
        </button>
        <label className="flex flex-col gap-1">
          <span className="text-sm text-gray-600">{t("aiCategorizationOverrideLabel")}</span>
          <select
            value={overrideCategoryId}
            onChange={(event) => setOverrideCategoryId(event.target.value)}
            className="rounded border px-3 py-2"
          >
            <option value="" />
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.label_ar} / {category.label_en}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={() => decisionMutation.mutate({ accepted: false, overrideCategoryId })}
          disabled={decisionMutation.isPending || !overrideCategoryId}
          className="rounded border px-3 py-2 text-sm"
        >
          {t("aiCategorizationOverrideButton")}
        </button>
      </div>
      {decisionMutation.isError && <p role="alert">{t("error")}</p>}
    </section>
  );
}
