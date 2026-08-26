"use client";

import { useLocale, useTranslations } from "next-intl";
import { usePathname, useRouter } from "next/navigation";

import { locales, type Locale } from "@/i18n";

/** Client-side locale switch — no full page reload, per T045's gate. */
export function LocaleSwitcher() {
  const t = useTranslations("LocaleSwitcher");
  const locale = useLocale();
  const pathname = usePathname();
  const router = useRouter();

  function switchTo(nextLocale: Locale) {
    const segments = pathname.split("/");
    segments[1] = nextLocale;
    router.push(segments.join("/"));
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
