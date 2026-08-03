import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PicksRail from "./PicksRail";
import type { PicksResponse } from "../../types/PicksResponse";

const RESPONSE: PicksResponse = {
  generated_by: "deterministic",
  picks: [
    {
      id: "p1",
      name: "leche entera 1 L",
      description: "brick",
      category: "grocery",
      price: 1.2,
      stock_qty: 24,
      store_id: "s1",
      neighbourhood: "Lavapiés",
      tags: ["lacteos"],
      image_url: null,
    },
    {
      id: "p2",
      name: "cargador USB-C",
      description: "20W",
      category: "electronics",
      price: 12.9,
      stock_qty: 3,
      store_id: "s2",
      neighbourhood: "Malasaña",
      tags: [],
    },
  ],
};

function mount(neighbourhood: string | null = null, onSelect = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const utils = render(
    <QueryClientProvider client={client}>
      <PicksRail lang="en" neighbourhood={neighbourhood} onSelect={onSelect} />
    </QueryClientProvider>,
  );
  return { ...utils, onSelect };
}

function respondWith(body: PicksResponse) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, status: 200, json: async () => body }) as unknown as Response),
  );
}

describe("PicksRail", () => {
  beforeEach(() => vi.unstubAllGlobals());
  afterEach(() => vi.unstubAllGlobals());

  it("shows one card per pick, with the API's own words", async () => {
    respondWith(RESPONSE);
    mount();

    expect(await screen.findByText("leche entera 1 L")).toBeTruthy();
    // Product and neighbourhood names are data, never translated.
    expect(screen.getByText(/grocery · Lavapiés/)).toBeTruthy();
    expect(screen.getByText("1.20 €")).toBeTruthy();
  });

  it("renders nothing at all when the list is empty", async () => {
    respondWith({ generated_by: "deterministic", picks: [] });
    const { container } = mount();

    // "Absent-cleanly": no heading, no empty-state text, no reserved space.
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalled());
    expect(container.querySelector(".picks")).toBeNull();
    expect(screen.queryByText(/popular near you/i)).toBeNull();
  });

  it("stays silent when the fetch fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: false, status: 502, json: async () => ({}) }) as unknown as Response),
    );
    const { container } = mount();

    // A decoration on the landing page must not tell a shopper the site is
    // broken while the search box beside it still works.
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalled());
    await waitFor(() => expect(container.querySelector(".picks")).toBeNull());
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("does not claim the picks are personalised", async () => {
    respondWith(RESPONSE);
    mount();

    // /api/picks has no per-shopper signal — it ranks by store rating and
    // round-robins categories. Copy saying "for you" would be a claim the
    // backend cannot support.
    expect(await screen.findByText(/popular near you/i)).toBeTruthy();
    expect(screen.getByText(/not by your history/i)).toBeTruthy();
  });

  it("passes the chosen barrio to the API and the product name back up", async () => {
    respondWith(RESPONSE);
    const { onSelect } = mount("Lavapiés");

    fireEvent.click(await screen.findByText("cargador USB-C"));
    expect(onSelect).toHaveBeenCalledWith("cargador USB-C");

    const url = (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toContain("/api/picks?");
    expect(decodeURIComponent(url)).toContain("neighbourhood=Lavapiés");
  });

  it("asks for Madrid-wide picks when no barrio is chosen", async () => {
    respondWith(RESPONSE);
    mount(null);

    await screen.findByText("leche entera 1 L");
    const url = (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    // No empty `neighbourhood=` param: the backend treats absent as city-wide,
    // and an empty string is a different request.
    expect(url).not.toContain("neighbourhood");
  });
});
