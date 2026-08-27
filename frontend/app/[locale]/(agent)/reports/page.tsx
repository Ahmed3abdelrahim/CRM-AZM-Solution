"use client";

import { useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";

import { LocaleSwitcher } from "@/components/locale-switcher";
import { LtrText } from "@/components/ltr-text";
import { api, ApiError, type ReportFilters } from "@/lib/api-client";

/** T134 — F09 management reporting (FR-059). The three report aggregates plus a cross-branch
 * toggle: the toggle itself is a plain client-side control (always shown) — the server is the
 * actual enforcement boundary (`ReportService`, FR-060), so a caller without `report.cross_branch`
 * simply gets a 403 back, surfaced inline rather than the toggle trying to pre-guess permissions
 * the frontend has no endpoint to read (no `/auth/me` exists in contracts/openapi.yaml). */
export default function ReportsPage() {
  const t = useTranslations("Reports");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [crossBranch, setCrossBranch] = useState(false);

  const filters: ReportFilters = {
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    cross_branch: crossBranch,
  };

  const statusesQuery = useQuery({ queryKey: ["ticket-statuses"], queryFn: api.listTicketStatuses });
  const usersQuery = useQuery({ queryKey: ["users"], queryFn: api.listUsers });

  const byStatusQuery = useQuery({
    queryKey: ["report-tickets-by-status", filters],
    queryFn: () => api.getTicketsByStatusReport(filters),
  });
  const slaQuery = useQuery({
    queryKey: ["report-sla-compliance", filters],
    queryFn: () => api.getSlaComplianceReport(filters),
  });
  const volumeQuery = useQuery({
    queryKey: ["report-agent-volume", filters],
    queryFn: () => api.getAgentVolumeReport(filters),
  });

  const statuses = statusesQuery.data ?? [];
  const users = usersQuery.data ?? [];
  const statusLabel = (id: string) => {
    const found = statuses.find((s) => s.id === id);
    return found ? `${found.label_ar} / ${found.label_en}` : id;
  };
  const userLabel = (id: string) => {
    const found = users.find((u) => u.id === id);
    return found ? `${found.full_name_ar} / ${found.full_name_en}` : id;
  };

  function forbiddenMessage(error: unknown) {
    if (error instanceof ApiError && error.status === 403) return t("crossBranchForbidden");
    return t("error");
  }

  return (
    <main className="mx-auto max-w-4xl p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold">{t("title")}</h1>
        <LocaleSwitcher />
      </div>

      <div className="mt-2 flex gap-4 text-sm">
        <Link href="dashboard" className="underline">
          {t("dashboardLink")}
        </Link>
        <Link href="admin" className="underline">
          {t("adminLink")}
        </Link>
      </div>

      <fieldset className="mt-4 flex flex-wrap items-end gap-3 rounded border p-3">
        <legend className="text-sm text-gray-600">{t("filtersTitle")}</legend>
        <label className="flex flex-col gap-1">
          <span className="text-sm text-gray-600">{t("filterDateFrom")}</span>
          <input
            type="date"
            value={dateFrom}
            onChange={(event) => setDateFrom(event.target.value)}
            className="rounded border px-3 py-2"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-sm text-gray-600">{t("filterDateTo")}</span>
          <input
            type="date"
            value={dateTo}
            onChange={(event) => setDateTo(event.target.value)}
            className="rounded border px-3 py-2"
          />
        </label>
        <label className="flex items-center gap-2 pb-2">
          <input
            type="checkbox"
            checked={crossBranch}
            onChange={(event) => setCrossBranch(event.target.checked)}
          />
          <span className="text-sm text-gray-600">{t("crossBranchToggle")}</span>
        </label>
      </fieldset>

      <section className="mt-6">
        <h2 className="font-semibold">{t("byStatusTitle")}</h2>
        {byStatusQuery.isLoading && <p>{t("loading")}</p>}
        {byStatusQuery.isError && <p role="alert">{forbiddenMessage(byStatusQuery.error)}</p>}
        {byStatusQuery.data && byStatusQuery.data.rows.length === 0 && <p>{t("noResults")}</p>}
        {byStatusQuery.data && byStatusQuery.data.rows.length > 0 && (
          <table className="mt-2 w-full border-collapse">
            <thead>
              <tr className="border-b">
                <th className="p-2 text-start">{t("columnStatus")}</th>
                <th className="p-2 text-start">{t("columnBranch")}</th>
                <th className="p-2 text-start">{t("columnCount")}</th>
              </tr>
            </thead>
            <tbody>
              {byStatusQuery.data.rows.map((row, index) => (
                <tr key={`${row.status_id}-${row.branch_id}-${row.department_id}-${index}`} className="border-b">
                  <td className="p-2">{statusLabel(row.status_id)}</td>
                  <td className="p-2">
                    <LtrText>{row.branch_id}</LtrText>
                  </td>
                  <td className="p-2">{row.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="mt-6">
        <h2 className="font-semibold">{t("slaTitle")}</h2>
        {slaQuery.isLoading && <p>{t("loading")}</p>}
        {slaQuery.isError && <p role="alert">{forbiddenMessage(slaQuery.error)}</p>}
        {slaQuery.data && (
          <dl className="mt-2 grid grid-cols-2 gap-3">
            <div className="rounded border p-3">
              <dt className="text-sm text-gray-600">{t("firstResponseCompliance")}</dt>
              <dd className="text-xl font-semibold">{slaQuery.data.first_response_compliance_pct}%</dd>
            </div>
            <div className="rounded border p-3">
              <dt className="text-sm text-gray-600">{t("resolutionCompliance")}</dt>
              <dd className="text-xl font-semibold">{slaQuery.data.resolution_compliance_pct}%</dd>
            </div>
          </dl>
        )}
      </section>

      <section className="mt-6">
        <h2 className="font-semibold">{t("volumeTitle")}</h2>
        {volumeQuery.isLoading && <p>{t("loading")}</p>}
        {volumeQuery.isError && <p role="alert">{forbiddenMessage(volumeQuery.error)}</p>}
        {volumeQuery.data && volumeQuery.data.rows.length === 0 && <p>{t("noResults")}</p>}
        {volumeQuery.data && volumeQuery.data.rows.length > 0 && (
          <table className="mt-2 w-full border-collapse">
            <thead>
              <tr className="border-b">
                <th className="p-2 text-start">{t("columnAgent")}</th>
                <th className="p-2 text-start">{t("columnAssigned")}</th>
                <th className="p-2 text-start">{t("columnResolved")}</th>
                <th className="p-2 text-start">{t("columnAvgResolution")}</th>
              </tr>
            </thead>
            <tbody>
              {volumeQuery.data.rows.map((row) => (
                <tr key={row.agent_id} className="border-b">
                  <td className="p-2">{userLabel(row.agent_id)}</td>
                  <td className="p-2">{row.assigned_count}</td>
                  <td className="p-2">{row.resolved_count}</td>
                  <td className="p-2">{row.avg_resolution_minutes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}
