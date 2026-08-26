"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { LtrText } from "@/components/ltr-text";
import { api, ApiError } from "@/lib/api-client";

/** T079 — ticket detail, status-change control (surfacing the localized illegal-transition
 * error), assignment, timeline, notes/replies, attachments, inline customer context (FR-028). */
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

      <h1 className="mt-2 text-2xl font-bold">
        <LtrText>{ticket.reference_no}</LtrText> — {ticket.subject}
      </h1>
      <p className="mt-1 text-sm text-gray-600">{ticket.description}</p>

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

      <section className="mt-6">
        <h2 className="font-semibold">{t("composerTitle")}</h2>
        <ComposerForm ticketId={ticketId} onSent={invalidateTicket} />
      </section>

      <section className="mt-6">
        <h2 className="font-semibold">{t("timelineTitle")}</h2>
        {(eventsQuery.data ?? []).length === 0 ? (
          <p>{t("noEvents")}</p>
        ) : (
          <ul className="mt-2 flex flex-col gap-1">
            {eventsQuery.data?.map((event) => (
              <li key={event.id} className="rounded border p-2 text-sm">
                <span className="font-semibold">{event.event_type}</span>{" "}
                <span className="text-gray-600">
                  ({event.visibility === "internal" ? t("visibilityInternal") : t("visibilityCustomer")})
                </span>
                {event.body && <p>{event.body}</p>}
                {event.reason && <p className="text-gray-600">{event.reason}</p>}
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

function ComposerForm({ ticketId, onSent }: { ticketId: string; onSent: () => void }) {
  const t = useTranslations("TicketDetail");
  const [body, setBody] = useState("");
  const [visibility, setVisibility] = useState<"internal" | "customer">("internal");

  const sendMutation = useMutation({
    mutationFn: () =>
      visibility === "internal" ? api.addTicketNote(ticketId, body) : api.addTicketReply(ticketId, body),
    onSuccess: () => {
      setBody("");
      onSent();
    },
  });

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (body.trim()) sendMutation.mutate();
  }

  return (
    <form onSubmit={handleSubmit} className="mt-2 flex flex-col gap-2 rounded border p-3">
      <label className="flex flex-col gap-1">
        <span className="text-sm text-gray-600">{t("composerBodyLabel")}</span>
        <textarea
          required
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
