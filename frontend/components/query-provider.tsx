"use client";

import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

/** First consumer of the `@tanstack/react-query` dependency declared in Batch 4a's
 * package.json (T003) — the customers pages (T066/T067) are the first screens to fetch data,
 * and Batch 4e's dashboard (T085) reuses this same provider. One `QueryClient` per browser
 * session, created lazily so it isn't shared across server-rendered requests. */
export function QueryProvider({ children }: { children: ReactNode }) {
  const [client] = useState(() => new QueryClient());
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
