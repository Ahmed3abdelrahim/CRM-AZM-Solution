import { useTranslations } from "next-intl";

import { LocaleSwitcher } from "@/components/locale-switcher";
import { LtrText } from "@/components/ltr-text";

/**
 * Placeholder page exercising Batch 4a's RTL toggle gate — a locale switcher and one
 * <LtrText>-wrapped sample value. Replaced by the real dashboard views in Batch 4e.
 */
export default function DashboardPage() {
  const t = useTranslations("Dashboard");

  return (
    <main className="p-6">
      <h1 className="text-2xl font-bold">{t("title")}</h1>
      <LocaleSwitcher />
      <p className="mt-4">
        {t("sampleReferenceLabel")}: <LtrText>{t("sampleReferenceValue")}</LtrText>
      </p>
    </main>
  );
}
