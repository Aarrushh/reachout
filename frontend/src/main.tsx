/**
 * Router + QueryClientProvider bootstrap.
 */
import "@fontsource/space-grotesk/600.css";
import "@fontsource/ibm-plex-mono/500.css";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "./styles/tokens.css";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { ApiError } from "./api/client";
import SearchRoute from "./routes/search";
import ResultsRoute from "./routes/results";
import AppShell from "./shell/AppShell";

// A 4xx is permanent (bad query, bad params) — retrying only delays the
// error state. Keep TanStack's default 3 retries for everything else.
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) =>
        !(error instanceof ApiError && error.status >= 400 && error.status < 500) && failureCount < 3,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        {/* One shell, both modes. It is INSIDE the router on purpose: mode
            comes from `?mode=`, so the shell needs the router's search
            params, and both routes keep the same toggle in the same place. */}
        <AppShell>
          <Routes>
            <Route path="/" element={<SearchRoute />} />
            <Route path="/results" element={<ResultsRoute />} />
          </Routes>
        </AppShell>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
