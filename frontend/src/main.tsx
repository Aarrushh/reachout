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
        <Routes>
          <Route path="/" element={<SearchRoute />} />
          <Route path="/results" element={<ResultsRoute />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
