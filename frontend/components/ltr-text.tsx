import type { ReactNode } from "react";

/**
 * Sets dir="ltr" locally for reference numbers/emails/phones/URLs (constitution Principle III's
 * rtl-exempt: exception mechanism) — the page's overall reading direction is unaffected.
 */
export function LtrText({ children }: { children: ReactNode }) {
  return (
    <span dir="ltr" className="inline-block">
      {children}
    </span>
  );
}
