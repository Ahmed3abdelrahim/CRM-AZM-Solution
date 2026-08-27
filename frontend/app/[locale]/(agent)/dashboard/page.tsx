"use client";

import { useCallback, useMemo } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";

import { LocaleSwitcher } from "@/components/locale-switcher";
import { LtrText } from "@/components/ltr-text";
import { api, type TicketListFilters, type TicketView } from "@/lib/api-client";

/** T085 — replaces Batch 4a's placeholder. F04's five views (`GET /tickets?view=`) plus the
 * shared filter set (status/priority/category/assignee/channel/date-range/free-text) with
 * URL-encoded, shareable filter state (FR-027) — the URL is the only source of truth for the
 * active view/filters, so a shared link reproduces the exact same screen. */
const VIEWS: TicketView[] = ["my_open", "team_queue", "unassigned", "breaching_soon", "recently_closed"];
const CHANNELS = ["web", "email", "whatsapp", "sms", "chat", "portal"] as const;

const FILTER_KEYS = [
  "status_id",
  "priority_id",
  "category_id",
  "assignee_id",
  "channel",
  "date_from",
  "date_to",
  "q",
] as const;

export default function DashboardPage() {
  const t = useTranslations("Dashboard");
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const view = (searchParams.get("view") as TicketView | null) ?? "my_open";
  const values = Object.fromEntries(
    FILTER_KEYS.map((key) => [key, searchParams.get(key) ?? ""]),
  ) as Record<(typeof FILTER_KEYS)[number], string>;

  const setParam = useCallback(
    (key: string, value: string) => {
      const next = new URLSearchParams(searchParams.toString());
      if (value) next.set(key, value);
      else next.delete(key);
      router.replace(`${pathname}?${next.toString()}`);
    },
    [pathname, router, searchParams],
  );

  const filters: TicketListFilters = useMemo(
    () => ({
      view,
      status_id: values.status_id || undefined,
      priority_id: values.priority_id || undefined,
      category_id: values.category_id || undefined,
      assignee_id: values.assignee_id || undefined,
      channel: values.channel || undefined,
      date_from: values.date_from || undefined,
      date_to: values.date_to || undefined,
      q: values.q || undefined,
    }),
    [view, values],
  );

  const ticketsQuery = useQuery({
    queryKey: ["tickets", filters],
    queryFn: () => api.listTickets(filters),
  });
  const statusesQuery = useQuery({ queryKey: ["ticket-statuses"], queryFn: api.listTicketStatuses });
  const prioritiesQuery = useQuery({ queryKey: ["priorities"], queryFn: api.listPriorities });
  const categoriesQuery = useQuery({ queryKey: ["categories"], queryFn: api.listCategories });
  const usersQuery = useQuery({ queryKey: ["users"], queryFn: api.listUsers });

  const statuses = statusesQuery.data ?? [];
  const priorities = prioritiesQuery.data ?? [];
  const categories = categoriesQuery.data ?? [];
  const users = usersQuery.data ?? [];

  const referenceLabel = (item: { label_ar: string; label_en: string } | undefined, fallback: string) =>
    item ? `${item.label_ar} / ${item.label_en}` : fallback;
  const statusLabel = (id: string) => referenceLabel(statuses.find((s) => s.id === id), id);
  const priorityLabel = (id: string) => referenceLabel(priorities.find((p) => p.id === id), id);
  const categoryLabel = (id: string) => referenceLabel(categories.find((c) => c.id === id), id);
  const userLabel = (id: string | null) => {
    if (!id) return t("unassigned");
    const found = users.find((u) => u.id === id);
    return found ? `${found.full_name_ar} / ${found.full_name_en}` : id;
  };

  const viewLabelKey: Record<TicketView, string> = {
    my_open: "viewMyOpen",
    team_queue: "viewTeamQueue",
    unassigned: "viewUnassigned",
    breaching_soon: "viewBreachingSoon",
    recently_closed: "viewRecentlyClosed",
  };

  return (
    <main className="p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold">{t("title")}</h1>
        <LocaleSwitcher />
      </div>
      <p className="mt-1 text-sm text-gray-600">
        {t("sampleReferenceLabel")}: <LtrText>{t("sampleReferenceValue")}</LtrText>
      </p>

      <nav className="mt-4 flex flex-wrap gap-2" aria-label={t("viewsNavLabel")}>
        {VIEWS.map((candidate) => (
          <button
            key={candidate}
            type="button"
            onClick={() => setParam("view", candidate)}
            aria-current={candidate === view}
            className="rounded border px-3 py-2 aria-[current=true]:bg-gray-900 aria-[current=true]:text-white"
          >
            {t(viewLabelKey[candidate])}
          </button>
        ))}
      </nav>

      <fieldset className="mt-4 flex flex-wrap items-end gap-3 rounded border p-3">
        <legend className="text-sm text-gray-600">{t("filtersTitle")}</legend>

        <label className="flex flex-col gap-1">
          <span className="text-sm text-gray-600">{t("filterQ")}</span>
          <input
            type="text"
            value={values.q}
            onChange={(event) => setParam("q", event.target.value)}
            className="rounded border px-3 py-2"
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-sm text-gray-600">{t("filterStatus")}</span>
          <select
            value={values.status_id}
            onChange={(event) => setParam("status_id", event.target.value)}
            className="rounded border px-3 py-2"
          >
            <option value="">{t("filterAny")}</option>
            {statuses.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label_ar} / {s.label_en}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-sm text-gray-600">{t("filterPriority")}</span>
          <select
            value={values.priority_id}
            onChange={(event) => setParam("priority_id", event.target.value)}
            className="rounded border px-3 py-2"
          >
            <option value="">{t("filterAny")}</option>
            {priorities.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label_ar} / {p.label_en}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-sm text-gray-600">{t("filterCategory")}</span>
          <select
            value={values.category_id}
            onChange={(event) => setParam("category_id", event.target.value)}
            className="rounded border px-3 py-2"
          >
            <option value="">{t("filterAny")}</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.label_ar} / {c.label_en}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-sm text-gray-600">{t("filterAssignee")}</span>
          <select
            value={values.assignee_id}
            onChange={(event) => setParam("assignee_id", event.target.value)}
            className="rounded border px-3 py-2"
          >
            <option value="">{t("filterAny")}</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name_ar} / {u.full_name_en}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-sm text-gray-600">{t("filterChannel")}</span>
          <select
            value={values.channel}
            onChange={(event) => setParam("channel", event.target.value)}
            className="rounded border px-3 py-2"
          >
            <option value="">{t("filterAny")}</option>
            {CHANNELS.map((channel) => (
              <option key={channel} value={channel}>
                {t(`channel_${channel}`)}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-sm text-gray-600">{t("filterDateFrom")}</span>
          <input
            type="date"
            value={values.date_from}
            onChange={(event) => setParam("date_from", event.target.value)}
            className="rounded border px-3 py-2"
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-sm text-gray-600">{t("filterDateTo")}</span>
          <input
            type="date"
            value={values.date_to}
            onChange={(event) => setParam("date_to", event.target.value)}
            className="rounded border px-3 py-2"
          />
        </label>

        <button
          type="button"
          onClick={() => router.replace(`${pathname}?view=${view}`)}
          className="rounded border px-3 py-2"
        >
          {t("filtersClear")}
        </button>
      </fieldset>

      <div className="mt-4 flex gap-4">
        <Link href="/customers" className="underline">
          {t("customersLink")}
        </Link>
        <Link href="/kb" className="underline">
          {t("kbLink")}
        </Link>
        <Link href="reports" className="underline">
          {t("reportsLink")}
        </Link>
        <Link href="admin" className="underline">
          {t("adminLink")}
        </Link>
      </div>

      <div className="mt-4">
        {ticketsQuery.isLoading && <p>{t("loading")}</p>}
        {ticketsQuery.isError && (
          <p role="alert">{t("error")}</p>
        )}
        {ticketsQuery.data && ticketsQuery.data.length === 0 && <p>{t("noResults")}</p>}
        {ticketsQuery.data && ticketsQuery.data.length > 0 && (
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b">
                <th className="p-2 text-start">{t("columnReference")}</th>
                <th className="p-2 text-start">{t("columnSubject")}</th>
                <th className="p-2 text-start">{t("columnStatus")}</th>
                <th className="p-2 text-start">{t("columnPriority")}</th>
                <th className="p-2 text-start">{t("columnCategory")}</th>
                <th className="p-2 text-start">{t("columnAssignee")}</th>
                <th className="p-2 text-start">{t("columnChannel")}</th>
                <th className="p-2 text-start" />
              </tr>
            </thead>
            <tbody>
              {ticketsQuery.data.map((ticket) => (
                <tr key={ticket.id} className="border-b">
                  <td className="p-2">
                    <LtrText>{ticket.reference_no}</LtrText>
                    {ticket.needs_triage && (
                      <span className="ms-2 rounded border border-amber-500 px-1 text-xs text-amber-700">
                        {t("needsTriageBadge")}
                      </span>
                    )}
                  </td>
                  <td className="p-2" dir="auto">
                    {ticket.subject}
                  </td>
                  <td className="p-2">{statusLabel(ticket.status_id)}</td>
                  <td className="p-2">{priorityLabel(ticket.priority_id)}</td>
                  <td className="p-2">{categoryLabel(ticket.category_id)}</td>
                  <td className="p-2">{userLabel(ticket.assignee_id)}</td>
                  <td className="p-2">{t(`channel_${ticket.channel}`)}</td>
                  <td className="p-2">
                    <Link href={`tickets/${ticket.id}`} className="underline">
                      {t("viewLink")}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </main>
  );
}
