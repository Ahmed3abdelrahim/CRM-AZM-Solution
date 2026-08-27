"use client";

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Category, type KbArticle, type KbArticleCreate, type KbSearchResult } from "@/lib/api-client";

/** T106 — article list, editor (bilingual title/body fields, publish action), search box (F06).
 * Search runs KbService's hybrid trigram+vector query; the editor covers create, edit, and
 * publish — everything `contracts/openapi.yaml`'s `/kb/articles*`/`/kb/search` expose. */
export default function KbPage() {
  const t = useTranslations("Kb");
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");

  const articlesQuery = useQuery({ queryKey: ["kb-articles"], queryFn: () => api.listKbArticles() });
  const categoriesQuery = useQuery({ queryKey: ["categories"], queryFn: api.listCategories });
  const branchesQuery = useQuery({ queryKey: ["branches"], queryFn: api.listBranches });
  const departmentsQuery = useQuery({ queryKey: ["departments"], queryFn: api.listDepartments });

  const searchResultsQuery = useQuery({
    queryKey: ["kb-search", submittedQuery],
    queryFn: () => api.searchKb(submittedQuery),
    enabled: submittedQuery.length > 0,
  });

  const selectedArticle = useMemo(
    () => articlesQuery.data?.find((article) => article.id === selectedId) ?? null,
    [articlesQuery.data, selectedId],
  );

  function invalidateArticles() {
    queryClient.invalidateQueries({ queryKey: ["kb-articles"] });
  }

  return (
    <main className="mx-auto max-w-4xl p-6">
      <h1 className="text-2xl font-bold">{t("title")}</h1>

      <section className="mt-4 flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1">
          <span className="text-sm text-gray-600">{t("searchLabel")}</span>
          <input
            type="text"
            dir="auto"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder={t("searchPlaceholder")}
            className="w-80 rounded border px-3 py-2"
          />
        </label>
        <button
          type="button"
          onClick={() => setSubmittedQuery(searchQuery)}
          className="rounded border px-3 py-2"
        >
          {t("searchButton")}
        </button>
      </section>

      {submittedQuery.length > 0 && (
        <section className="mt-4">
          {searchResultsQuery.isLoading && <p>{t("loading")}</p>}
          {searchResultsQuery.isError && <p role="alert">{t("error")}</p>}
          {searchResultsQuery.data && searchResultsQuery.data.length === 0 && <p>{t("noSearchResults")}</p>}
          {searchResultsQuery.data && searchResultsQuery.data.length > 0 && (
            <ul className="flex flex-col gap-2">
              {searchResultsQuery.data.map((result: KbSearchResult) => (
                <SearchResultRow key={result.article.id} result={result} />
              ))}
            </ul>
          )}
        </section>
      )}

      <div className="mt-6 flex items-center justify-between">
        <h2 className="font-semibold">{t("articlesTitle")}</h2>
        <button
          type="button"
          onClick={() => {
            setSelectedId(null);
            setShowCreateForm((prev) => !prev);
          }}
          className="rounded border px-3 py-2"
        >
          {showCreateForm ? t("cancelButton") : t("newArticleButton")}
        </button>
      </div>

      {showCreateForm && (
        <ArticleForm
          categories={categoriesQuery.data ?? []}
          branches={branchesQuery.data ?? []}
          departments={departmentsQuery.data ?? []}
          onSaved={() => {
            setShowCreateForm(false);
            invalidateArticles();
          }}
        />
      )}

      <div className="mt-4">
        {articlesQuery.isLoading && <p>{t("loading")}</p>}
        {articlesQuery.isError && <p role="alert">{t("error")}</p>}
        {articlesQuery.data && articlesQuery.data.length === 0 && <p>{t("noArticles")}</p>}
        {articlesQuery.data && articlesQuery.data.length > 0 && (
          <table className="w-full border-collapse">
            <thead>
              <tr className="border-b text-start">
                <th className="p-2 text-start">{t("columnTitle")}</th>
                <th className="p-2 text-start">{t("columnStatus")}</th>
                <th className="p-2 text-start" />
              </tr>
            </thead>
            <tbody>
              {articlesQuery.data.map((article) => (
                <tr key={article.id} className="border-b">
                  <td className="p-2" dir="auto">
                    {article.title_ar} / {article.title_en}
                  </td>
                  <td className="p-2">{article.is_published ? t("statusPublished") : t("statusDraft")}</td>
                  <td className="p-2">
                    <button
                      type="button"
                      onClick={() => {
                        setShowCreateForm(false);
                        setSelectedId(article.id === selectedId ? null : article.id);
                      }}
                      className="underline"
                    >
                      {article.id === selectedId ? t("closeEditorLink") : t("editLink")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {selectedArticle && (
        <ArticleEditor
          article={selectedArticle}
          categories={categoriesQuery.data ?? []}
          onSaved={invalidateArticles}
        />
      )}
    </main>
  );
}

function SearchResultRow({ result }: { result: KbSearchResult }) {
  const isAr = result.matched_locale === "ar";
  const title = isAr ? result.article.title_ar : result.article.title_en;
  const body = isAr ? result.article.body_ar : result.article.body_en;
  return (
    <li className="rounded border p-3 text-sm" dir="auto">
      <p className="font-medium">{title}</p>
      <p className="text-gray-600">{body}</p>
    </li>
  );
}

function ArticleForm({
  categories,
  branches,
  departments,
  onSaved,
}: {
  categories: Category[];
  branches: { id: string; label_ar: string; label_en: string }[];
  departments: { id: string; branch_id: string; label_ar: string; label_en: string }[];
  onSaved: () => void;
}) {
  const t = useTranslations("Kb");
  const [branchId, setBranchId] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [slug, setSlug] = useState("");
  const [titleAr, setTitleAr] = useState("");
  const [titleEn, setTitleEn] = useState("");
  const [bodyAr, setBodyAr] = useState("");
  const [bodyEn, setBodyEn] = useState("");

  const categoriesForBranch = useMemo(
    () => categories.filter((category) => category.branch_id === branchId),
    [categories, branchId],
  );

  const createMutation = useMutation({
    mutationFn: (data: KbArticleCreate) => api.createKbArticle(data),
    onSuccess: onSaved,
  });

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    createMutation.mutate({
      branch_id: branchId,
      category_id: categoryId,
      slug,
      title_ar: titleAr,
      title_en: titleEn,
      body_ar: bodyAr,
      body_en: bodyEn,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3 rounded border p-4">
      <h3 className="font-semibold">{t("newArticleButton")}</h3>

      <label className="flex flex-col gap-1">
        <span className="text-sm text-gray-600">{t("branch")}</span>
        <select
          required
          value={branchId}
          onChange={(event) => {
            setBranchId(event.target.value);
            setCategoryId("");
          }}
          className="rounded border px-3 py-2"
        >
          <option value="">{t("selectPlaceholder")}</option>
          {branches.map((branch) => (
            <option key={branch.id} value={branch.id}>
              {branch.label_ar} / {branch.label_en}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-sm text-gray-600">{t("category")}</span>
        <select
          required
          value={categoryId}
          onChange={(event) => setCategoryId(event.target.value)}
          className="rounded border px-3 py-2"
        >
          <option value="">{t("selectPlaceholder")}</option>
          {categoriesForBranch.map((category) => (
            <option key={category.id} value={category.id}>
              {category.label_ar} / {category.label_en}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-sm text-gray-600">{t("slug")}</span>
        <input
          required
          type="text"
          value={slug}
          onChange={(event) => setSlug(event.target.value)}
          className="rounded border px-3 py-2"
        />
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-sm text-gray-600">{t("titleAr")}</span>
        <input
          required
          type="text"
          dir="rtl"
          value={titleAr}
          onChange={(event) => setTitleAr(event.target.value)}
          className="rounded border px-3 py-2"
        />
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-sm text-gray-600">{t("titleEn")}</span>
        <input
          required
          type="text"
          value={titleEn}
          onChange={(event) => setTitleEn(event.target.value)}
          className="rounded border px-3 py-2"
        />
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-sm text-gray-600">{t("bodyAr")}</span>
        <textarea
          required
          dir="rtl"
          rows={4}
          value={bodyAr}
          onChange={(event) => setBodyAr(event.target.value)}
          className="rounded border px-3 py-2"
        />
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-sm text-gray-600">{t("bodyEn")}</span>
        <textarea
          required
          rows={4}
          value={bodyEn}
          onChange={(event) => setBodyEn(event.target.value)}
          className="rounded border px-3 py-2"
        />
      </label>

      {createMutation.isError && <p role="alert">{t("error")}</p>}

      <button type="submit" disabled={createMutation.isPending} className="rounded border px-3 py-2">
        {createMutation.isPending ? t("loading") : t("submitButton")}
      </button>
    </form>
  );
}

function ArticleEditor({
  article,
  categories,
  onSaved,
}: {
  article: KbArticle;
  categories: Category[];
  onSaved: () => void;
}) {
  const t = useTranslations("Kb");
  const [titleAr, setTitleAr] = useState(article.title_ar);
  const [titleEn, setTitleEn] = useState(article.title_en);
  const [bodyAr, setBodyAr] = useState(article.body_ar);
  const [bodyEn, setBodyEn] = useState(article.body_en);
  const [categoryId, setCategoryId] = useState(article.category_id);

  const categoriesForBranch = useMemo(
    () => categories.filter((category) => category.branch_id === article.branch_id),
    [categories, article.branch_id],
  );

  const updateMutation = useMutation({
    mutationFn: () =>
      api.updateKbArticle(article.id, {
        title_ar: titleAr,
        title_en: titleEn,
        body_ar: bodyAr,
        body_en: bodyEn,
        category_id: categoryId,
      }),
    onSuccess: onSaved,
  });

  const publishMutation = useMutation({
    mutationFn: () => api.publishKbArticle(article.id),
    onSuccess: onSaved,
  });

  return (
    <div className="mt-4 flex flex-col gap-3 rounded border p-4">
      <h3 className="font-semibold">{t("editTitle")}</h3>

      <label className="flex flex-col gap-1">
        <span className="text-sm text-gray-600">{t("category")}</span>
        <select
          value={categoryId}
          onChange={(event) => setCategoryId(event.target.value)}
          className="rounded border px-3 py-2"
        >
          {categoriesForBranch.map((category) => (
            <option key={category.id} value={category.id}>
              {category.label_ar} / {category.label_en}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-sm text-gray-600">{t("titleAr")}</span>
        <input
          type="text"
          dir="rtl"
          value={titleAr}
          onChange={(event) => setTitleAr(event.target.value)}
          className="rounded border px-3 py-2"
        />
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-sm text-gray-600">{t("titleEn")}</span>
        <input
          type="text"
          value={titleEn}
          onChange={(event) => setTitleEn(event.target.value)}
          className="rounded border px-3 py-2"
        />
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-sm text-gray-600">{t("bodyAr")}</span>
        <textarea
          dir="rtl"
          rows={4}
          value={bodyAr}
          onChange={(event) => setBodyAr(event.target.value)}
          className="rounded border px-3 py-2"
        />
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-sm text-gray-600">{t("bodyEn")}</span>
        <textarea
          rows={4}
          value={bodyEn}
          onChange={(event) => setBodyEn(event.target.value)}
          className="rounded border px-3 py-2"
        />
      </label>

      {(updateMutation.isError || publishMutation.isError) && <p role="alert">{t("error")}</p>}

      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => updateMutation.mutate()}
          disabled={updateMutation.isPending}
          className="rounded border px-3 py-2"
        >
          {updateMutation.isPending ? t("loading") : t("saveButton")}
        </button>
        {!article.is_published && (
          <button
            type="button"
            onClick={() => publishMutation.mutate()}
            disabled={publishMutation.isPending}
            className="rounded border px-3 py-2"
          >
            {publishMutation.isPending ? t("loading") : t("publishButton")}
          </button>
        )}
      </div>
    </div>
  );
}
