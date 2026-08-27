"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useMutation, useQuery } from "@tanstack/react-query";

import { LocaleSwitcher } from "@/components/locale-switcher";
import { LtrText } from "@/components/ltr-text";
import { api, ApiError, type ContactMethodKind, type PortalTicketSubmit } from "@/lib/api-client";

/** T133 — F08 customer portal, ticket submission (FR-052). No account required
 * (`security: []`, contracts/openapi.yaml `/portal/tickets`). `category_id` has no public
 * listing endpoint in the contract (`/categories` is staff-only) — the topic picker below is
 * derived from the public `/portal/kb/articles` catalog instead, the same "pick the topic
 * closest to your question" pattern most help-desk portals already use, and it stays entirely
 * within endpoints `contracts/openapi.yaml` actually exposes unauthenticated. */
export default function PortalSubmitPage() {
  const t = useTranslations("Portal");
  const [fullName, setFullName] = useState("");
  const [contactKind, setContactKind] = useState<ContactMethodKind>("email");
  const [contactValue, setContactValue] = useState("");
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [categoryId, setCategoryId] = useState("");

  const articlesQuery = useQuery({ queryKey: ["portal-kb-articles"], queryFn: api.listPortalKbArticles });

  const topics = useMemo(() => {
    const seen = new Map<string, string>();
    for (const article of articlesQuery.data ?? []) {
      if (!seen.has(article.category_id)) {
        seen.set(article.category_id, `${article.title_ar} / ${article.title_en}`);
      }
    }
    return Array.from(seen.entries()).map(([id, label]) => ({ id, label }));
  }, [articlesQuery.data]);

  const submitMutation = useMutation({
    mutationFn: (data: PortalTicketSubmit) => api.submitPortalTicket(data),
  });

  const apiError = submitMutation.error instanceof ApiError ? submitMutation.error : null;

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    submitMutation.mutate({
      full_name: fullName,
      contact_kind: contactKind,
      contact_value: contactValue,
      subject,
      description,
      category_id: categoryId,
    });
  }

  return (
    <main className="mx-auto max-w-2xl p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold">{t("submitTitle")}</h1>
        <LocaleSwitcher />
      </div>

      <nav className="mt-2 flex gap-4 text-sm">
        <Link href="track" className="underline">
          {t("trackLink")}
        </Link>
        <Link href="kb" className="underline">
          {t("kbLink")}
        </Link>
      </nav>

      {submitMutation.isSuccess ? (
        <div className="mt-6 rounded border border-green-500 p-4">
          <p>{t("submitSuccess")}</p>
          <p className="mt-2 text-lg font-semibold">
            <LtrText>{submitMutation.data.reference_no}</LtrText>
          </p>
          <p className="mt-2 text-sm text-gray-600">{t("submitSuccessHint")}</p>
          <Link href="track" className="mt-3 inline-block underline">
            {t("trackLink")}
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-sm text-gray-600">{t("fullName")}</span>
            <input
              required
              type="text"
              dir="auto"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
              className="rounded border px-3 py-2"
            />
          </label>

          <div className="flex gap-2">
            <label className="flex flex-1 flex-col gap-1">
              <span className="text-sm text-gray-600">{t("contactKind")}</span>
              <select
                value={contactKind}
                onChange={(event) => setContactKind(event.target.value as ContactMethodKind)}
                className="rounded border px-3 py-2"
              >
                <option value="email">{t("contactKindEmail")}</option>
                <option value="phone">{t("contactKindPhone")}</option>
                <option value="whatsapp">{t("contactKindWhatsapp")}</option>
                <option value="other">{t("contactKindOther")}</option>
              </select>
            </label>
            <label className="flex flex-1 flex-col gap-1">
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
          </div>

          <label className="flex flex-col gap-1">
            <span className="text-sm text-gray-600">{t("topic")}</span>
            <select
              required
              value={categoryId}
              onChange={(event) => setCategoryId(event.target.value)}
              className="rounded border px-3 py-2"
            >
              <option value="">{t("selectPlaceholder")}</option>
              {topics.map((topic) => (
                <option key={topic.id} value={topic.id}>
                  {topic.label}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-sm text-gray-600">{t("subject")}</span>
            <input
              required
              type="text"
              dir="auto"
              value={subject}
              onChange={(event) => setSubject(event.target.value)}
              className="rounded border px-3 py-2"
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-sm text-gray-600">{t("description")}</span>
            <textarea
              required
              dir="auto"
              rows={5}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              className="rounded border px-3 py-2"
            />
          </label>

          {apiError && (
            <div role="alert" className="rounded border border-red-400 p-2 text-sm">
              <p>{apiError.messageAr}</p>
              <p>{apiError.messageEn}</p>
            </div>
          )}

          <button type="submit" disabled={submitMutation.isPending} className="rounded border px-3 py-2">
            {submitMutation.isPending ? t("loading") : t("submitButton")}
          </button>
        </form>
      )}
    </main>
  );
}
