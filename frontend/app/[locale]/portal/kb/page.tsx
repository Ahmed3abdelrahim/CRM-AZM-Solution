"use client";

import { useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useQuery } from "@tanstack/react-query";

import { LocaleSwitcher } from "@/components/locale-switcher";
import { api } from "@/lib/api-client";

/** T133 — F08 customer portal, published KB browsing (FR-055). No authentication, no search box
 * (`/kb/search` is staff-only in the contract — `/portal/kb/articles` is a plain published-only
 * list, so browsing here is by title, not query). */
export default function PortalKbPage() {
  const t = useTranslations("Portal");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const articlesQuery = useQuery({ queryKey: ["portal-kb-articles"], queryFn: api.listPortalKbArticles });

  return (
    <main className="mx-auto max-w-2xl p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold">{t("kbTitle")}</h1>
        <LocaleSwitcher />
      </div>

      <nav className="mt-2 flex gap-4 text-sm">
        <Link href="submit" className="underline">
          {t("submitLink")}
        </Link>
        <Link href="track" className="underline">
          {t("trackLink")}
        </Link>
      </nav>

      <div className="mt-6">
        {articlesQuery.isLoading && <p>{t("loading")}</p>}
        {articlesQuery.isError && <p role="alert">{t("error")}</p>}
        {articlesQuery.data && articlesQuery.data.length === 0 && <p>{t("noArticles")}</p>}
        <ul className="flex flex-col gap-2">
          {(articlesQuery.data ?? []).map((article) => {
            const expanded = article.id === expandedId;
            return (
              <li key={article.id} className="rounded border p-3">
                <button
                  type="button"
                  onClick={() => setExpandedId(expanded ? null : article.id)}
                  className="w-full text-start font-medium"
                  dir="auto"
                >
                  {article.title_ar} / {article.title_en}
                </button>
                {expanded && (
                  <div className="mt-2 flex flex-col gap-2 text-sm text-gray-700">
                    <p dir="rtl">{article.body_ar}</p>
                    <p dir="ltr">{article.body_en}</p>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </div>
    </main>
  );
}
