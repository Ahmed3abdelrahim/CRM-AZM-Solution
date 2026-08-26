import { notFound } from "next/navigation";
import { getRequestConfig } from "next-intl/server";

export const locales = ["ar", "en"] as const;
export type Locale = (typeof locales)[number];

export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale;
  const locale = locales.includes(requested as Locale) ? (requested as Locale) : undefined;

  if (!locale) {
    notFound();
  }

  return {
    locale,
    messages: (await import(`./messages/${locale}.json`)).default,
  };
});
