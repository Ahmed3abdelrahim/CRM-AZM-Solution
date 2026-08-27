"use client";

import { useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useMutation } from "@tanstack/react-query";

import { LocaleSwitcher } from "@/components/locale-switcher";
import { LtrText } from "@/components/ltr-text";
import { api, ApiError, type PortalTicketView } from "@/lib/api-client";

/** T133 — F08 customer portal, ticket tracking (FR-053). A wrong contact method and an unknown
 * reference number both surface as the identical "not found" message (the backend returns the
 * same 404 either way) — never distinguished here either, so nothing about ticket existence
 * leaks through the UI. */
export default function PortalTrackPage() {
  const t = useTranslations("Portal");
  const [referenceNo, setReferenceNo] = useState("");
  const [contactValue, setContactValue] = useState("");
  const [history, setHistory] = useState<PortalTicketView[] | null>(null);

  const trackMutation = useMutation({
    mutationFn: () => api.trackPortalTicket(referenceNo.trim(), contactValue.trim()),
    onSuccess: () => setHistory(null),
  });

  const historyMutation = useMutation({
    mutationFn: () => api.getPortalCustomerHistory(referenceNo.trim(), contactValue.trim()),
    onSuccess: (data) => setHistory(data),
  });

  const apiError =
    trackMutation.error instanceof ApiError
      ? trackMutation.error
      : historyMutation.error instanceof ApiError
        ? historyMutation.error
        : null;
  const notFound = apiError?.status === 404;

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (referenceNo && contactValue) trackMutation.mutate();
  }

  return (
    <main className="mx-auto max-w-2xl p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold">{t("trackTitle")}</h1>
        <LocaleSwitcher />
      </div>

      <nav className="mt-2 flex gap-4 text-sm">
        <Link href="submit" className="underline">
          {t("submitLink")}
        </Link>
        <Link href="kb" className="underline">
          {t("kbLink")}
        </Link>
      </nav>

      <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-3">
        <label className="flex flex-col gap-1">
          <span className="text-sm text-gray-600">{t("referenceNo")}</span>
          <input
            required
            type="text"
            dir="ltr"
            value={referenceNo}
            onChange={(event) => setReferenceNo(event.target.value)}
            placeholder="TKT-2026-000123"
            className="rounded border px-3 py-2"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-sm text-gray-600">{t("contactValue")}</span>
          <input
            required
            type="text"
            dir="ltr"
            value={contactValue}
            onChange={(event) => setContactValue(event.target.value)}
            className="rounded border px-3 py-2"
          />
        </label>

        {apiError && (
          <div role="alert" className="rounded border border-red-400 p-2 text-sm">
            <p>{notFound ? t("notFound") : apiError.messageEn}</p>
          </div>
        )}

        <div className="flex gap-2">
          <button type="submit" disabled={trackMutation.isPending} className="rounded border px-3 py-2">
            {trackMutation.isPending ? t("loading") : t("trackButton")}
          </button>
          <button
            type="button"
            disabled={!referenceNo || !contactValue || historyMutation.isPending}
            onClick={() => historyMutation.mutate()}
            className="rounded border px-3 py-2"
          >
            {historyMutation.isPending ? t("loading") : t("viewHistoryButton")}
          </button>
        </div>
      </form>

      {trackMutation.data && !history && <TicketCard view={trackMutation.data} />}

      {history && (
        <div className="mt-6 flex flex-col gap-4">
          <h2 className="font-semibold">{t("historyTitle")}</h2>
          {history.length === 0 && <p>{t("noTickets")}</p>}
          {history.map((view) => (
            <TicketCard key={view.reference_no} view={view} />
          ))}
        </div>
      )}
    </main>
  );
}

function TicketCard({ view }: { view: PortalTicketView }) {
  const t = useTranslations("Portal");
  return (
    <div className="mt-6 rounded border p-4">
      <p className="text-sm text-gray-600">
        {t("referenceNo")}: <LtrText>{view.reference_no}</LtrText>
      </p>
      <p className="mt-1 font-semibold" dir="auto">
        {view.subject}
      </p>
      <p className="mt-1 text-sm text-gray-600">
        {t("statusIdLabel")}: <LtrText>{view.status_id}</LtrText>
      </p>

      <h3 className="mt-4 text-sm font-semibold">{t("timelineTitle")}</h3>
      {view.events.length === 0 && <p className="text-sm text-gray-600">{t("noEvents")}</p>}
      <ul className="mt-2 flex flex-col gap-2">
        {view.events.map((event) => (
          <li key={event.id} className="rounded border p-2 text-sm">
            <p className="text-gray-600">
              {event.event_type} — <LtrText>{new Date(event.created_at).toLocaleString()}</LtrText>
            </p>
            {event.body && (
              <p className="mt-1" dir="auto">
                {event.body}
              </p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
