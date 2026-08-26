"use client";

import { useLocale, useTranslations } from "next-intl";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { locales, type Locale } from "@/i18n";

/** Client-side locale switch — no full page reload, per T045's gate. Preserves the current
 * search string (e.g. Batch 4e's dashboard `view`/filter query params, FR-027) so switching
 * language mid-screen doesn't silently reset it. */
export function LocaleSwitcher() {
  const t = useTranslations("LocaleSwitcher");
  const locale = useLocale();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();

  function switchTo(nextLocale: Locale) {
    const segments = pathname.split("/");
    segments[1] = nextLocale;
    const query = searchParams.toString();
    router.push(query ? `${segments.join("/")}?${query}` : segments.join("/"));
  }

  return (
    <div className="flex gap-2">
      {locales.map((candidate) => (
        <button
          key={candidate}
          type="button"
          onClick={() => switchTo(candidate)}
          aria-current={candidate === locale}
          className="rounded border px-3 py-1 disabled:opacity-50"
          disabled={candidate === locale}
        >
          {t(candidate)}
        </button>
      ))}
    </div>
  );
}
