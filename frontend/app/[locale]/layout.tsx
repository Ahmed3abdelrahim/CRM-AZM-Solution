import type { ReactNode } from "react";
import { NextIntlClientProvider } from "next-intl";
import { getMessages } from "next-intl/server";
import { notFound } from "next/navigation";

import { QueryProvider } from "@/components/query-provider";
import { locales, type Locale } from "@/i18n";
import "../globals.css";

const RTL_LOCALES: readonly Locale[] = ["ar"];

export function generateStaticParams() {
  return locales.map((locale) => ({ locale }));
}

/**
 * Sets <html dir> from the active locale via next-intl — the only place `dir` is set anywhere
 * in the frontend (docs/architecture/stack.md; constitution Principle III).
 */
export default async function LocaleLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!locales.includes(locale as Locale)) {
    notFound();
  }

  const messages = await getMessages();
  const dir = RTL_LOCALES.includes(locale as Locale) ? "rtl" : "ltr";

  return (
    <html lang={locale} dir={dir}>
      <body className={locale === "ar" ? "font-arabic" : undefined}>
        <NextIntlClientProvider messages={messages}>
          <QueryProvider>{children}</QueryProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
