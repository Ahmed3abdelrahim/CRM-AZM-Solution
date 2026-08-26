"use client";

import { useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useMutation } from "@tanstack/react-query";

import { LocaleSwitcher } from "@/components/locale-switcher";
import { api, ApiError, setAccessToken } from "@/lib/api-client";

/** The one page every unauthenticated visitor (and every 401 redirect from `api-client.ts`'s
 * `request()`) lands on. `next` is restricted to a same-locale relative path — an allowlist
 * against turning this into an open redirect — and falls back to the dashboard. */
export default function LoginPage() {
  const t = useTranslations("Login");
  const params = useParams<{ locale: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const loginMutation = useMutation({
    mutationFn: () => api.login(email, password),
    onSuccess: (tokens) => {
      setAccessToken(tokens.access_token);
      const next = searchParams.get("next");
      const safeNext = next && next.startsWith(`/${params.locale}/`) ? next : `/${params.locale}/dashboard`;
      router.replace(safeNext);
    },
  });

  const apiError = loginMutation.error instanceof ApiError ? loginMutation.error : null;

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (email && password) loginMutation.mutate();
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">{t("title")}</h1>
          <LocaleSwitcher />
        </div>
        <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-sm text-gray-600">{t("emailLabel")}</span>
            <input
              required
              type="email"
              dir="ltr"
              autoComplete="username"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="rounded border px-3 py-2"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-sm text-gray-600">{t("passwordLabel")}</span>
            <input
              required
              type="password"
              dir="ltr"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="rounded border px-3 py-2"
            />
          </label>
          {apiError && (
            <div role="alert" className="rounded border border-red-400 p-2 text-sm">
              <p>{apiError.messageAr}</p>
              <p>{apiError.messageEn}</p>
            </div>
          )}
          <button type="submit" disabled={loginMutation.isPending} className="rounded border px-3 py-2">
            {loginMutation.isPending ? t("loading") : t("submitButton")}
          </button>
        </form>
      </div>
    </main>
  );
}
