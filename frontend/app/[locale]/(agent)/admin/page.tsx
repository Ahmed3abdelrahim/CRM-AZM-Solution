"use client";

import { useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { LocaleSwitcher } from "@/components/locale-switcher";
import { LtrText } from "@/components/ltr-text";
import { api, ApiError, type ApiKeyCreate, type ApiKeyCreated } from "@/lib/api-client";

/** T135 — F11 API-key management (issue, list, revoke). `admin.config`-only per
 * contracts/openapi.yaml — every `/api-keys*` call 403s for anyone else, surfaced inline the
 * same way the reports page handles a missing `report.cross_branch`. */
export default function AdminPage() {
  const t = useTranslations("Admin");
  const queryClient = useQueryClient();
  const [justCreated, setJustCreated] = useState<ApiKeyCreated | null>(null);

  const keysQuery = useQuery({ queryKey: ["api-keys"], queryFn: api.listApiKeys });
  const permissionsQuery = useQuery({ queryKey: ["permissions"], queryFn: api.listPermissions });
  const branchesQuery = useQuery({ queryKey: ["branches"], queryFn: api.listBranches });

  const revokeMutation = useMutation({
    mutationFn: (id: string) => api.revokeApiKey(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["api-keys"] }),
  });

  const listError = keysQuery.error instanceof ApiError ? keysQuery.error : null;

  return (
    <main className="mx-auto max-w-3xl p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold">{t("title")}</h1>
        <LocaleSwitcher />
      </div>

      <div className="mt-2 flex gap-4 text-sm">
        <Link href="dashboard" className="underline">
          {t("dashboardLink")}
        </Link>
        <Link href="reports" className="underline">
          {t("reportsLink")}
        </Link>
      </div>

      <h2 className="mt-6 font-semibold">{t("issueTitle")}</h2>
      <IssueForm
        permissions={permissionsQuery.data ?? []}
        branches={branchesQuery.data ?? []}
        onIssued={(created) => {
          setJustCreated(created);
          queryClient.invalidateQueries({ queryKey: ["api-keys"] });
        }}
      />

      {justCreated && (
        <div className="mt-4 rounded border border-amber-500 p-4">
          <p className="text-sm">{t("plaintextWarning")}</p>
          <p className="mt-2 break-all font-mono text-sm">
            <LtrText>{justCreated.plaintext_key}</LtrText>
          </p>
        </div>
      )}

      <h2 className="mt-6 font-semibold">{t("listTitle")}</h2>
      {keysQuery.isLoading && <p>{t("loading")}</p>}
      {listError && <p role="alert">{listError.status === 403 ? t("forbidden") : t("error")}</p>}
      {keysQuery.data && keysQuery.data.length === 0 && <p>{t("noKeys")}</p>}
      {keysQuery.data && keysQuery.data.length > 0 && (
        <table className="mt-2 w-full border-collapse">
          <thead>
            <tr className="border-b">
              <th className="p-2 text-start">{t("columnLabel")}</th>
              <th className="p-2 text-start">{t("columnScopes")}</th>
              <th className="p-2 text-start">{t("columnExpiresAt")}</th>
              <th className="p-2 text-start">{t("columnLastUsedAt")}</th>
              <th className="p-2 text-start" />
            </tr>
          </thead>
          <tbody>
            {keysQuery.data.map((key) => {
              const revoked = key.expires_at !== null && new Date(key.expires_at) <= new Date();
              return (
                <tr key={key.id} className="border-b">
                  <td className="p-2">{key.label}</td>
                  <td className="p-2 text-sm">
                    <LtrText>{key.scopes.join(", ")}</LtrText>
                  </td>
                  <td className="p-2 text-sm">
                    {key.expires_at ? <LtrText>{new Date(key.expires_at).toLocaleString()}</LtrText> : t("never")}
                  </td>
                  <td className="p-2 text-sm">
                    {key.last_used_at ? <LtrText>{new Date(key.last_used_at).toLocaleString()}</LtrText> : t("never")}
                  </td>
                  <td className="p-2">
                    {!revoked && (
                      <button
                        type="button"
                        onClick={() => revokeMutation.mutate(key.id)}
                        disabled={revokeMutation.isPending}
                        className="rounded border px-2 py-1 text-sm"
                      >
                        {t("revokeButton")}
                      </button>
                    )}
                    {revoked && <span className="text-sm text-gray-600">{t("revokedLabel")}</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </main>
  );
}

function IssueForm({
  permissions,
  branches,
  onIssued,
}: {
  permissions: { id: string; code: string; label_ar: string; label_en: string }[];
  branches: { id: string; label_ar: string; label_en: string }[];
  onIssued: (created: ApiKeyCreated) => void;
}) {
  const t = useTranslations("Admin");
  const [label, setLabel] = useState("");
  const [branchId, setBranchId] = useState("");
  const [selectedScopes, setSelectedScopes] = useState<string[]>([]);

  const issueMutation = useMutation({
    mutationFn: (data: ApiKeyCreate) => api.createApiKey(data),
    onSuccess: onIssued,
  });

  function toggleScope(code: string) {
    setSelectedScopes((prev) => (prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]));
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!label || selectedScopes.length === 0) return;
    issueMutation.mutate({ label, branch_id: branchId || null, scopes: selectedScopes });
  }

  return (
    <form onSubmit={handleSubmit} className="mt-3 flex flex-col gap-3 rounded border p-4">
      <label className="flex flex-col gap-1">
        <span className="text-sm text-gray-600">{t("label")}</span>
        <input
          required
          type="text"
          value={label}
          onChange={(event) => setLabel(event.target.value)}
          className="rounded border px-3 py-2"
        />
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-sm text-gray-600">{t("branch")}</span>
        <select
          value={branchId}
          onChange={(event) => setBranchId(event.target.value)}
          className="rounded border px-3 py-2"
        >
          <option value="">{t("noBranchRestriction")}</option>
          {branches.map((branch) => (
            <option key={branch.id} value={branch.id}>
              {branch.label_ar} / {branch.label_en}
            </option>
          ))}
        </select>
      </label>

      <fieldset className="flex flex-col gap-2 rounded border p-3">
        <legend className="text-sm text-gray-600">{t("scopes")}</legend>
        <div className="flex max-h-48 flex-col gap-1 overflow-y-auto">
          {permissions.map((permission) => (
            <label key={permission.id} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={selectedScopes.includes(permission.code)}
                onChange={() => toggleScope(permission.code)}
              />
              <LtrText>{permission.code}</LtrText>
              <span className="text-gray-600">
                ({permission.label_ar} / {permission.label_en})
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      {issueMutation.isError && <p role="alert">{t("error")}</p>}

      <button type="submit" disabled={issueMutation.isPending} className="rounded border px-3 py-2">
        {issueMutation.isPending ? t("loading") : t("issueButton")}
      </button>
    </form>
  );
}
