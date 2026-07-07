import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { usePingSequence } from "./usePingSequence";
import type { RankedResult } from "../routes/results";

const mk = (id: string, rank: number): RankedResult => ({
  rank, shop_id: id, shop_name: id, category: "pharmacy", address: null,
  distance_km: 0.5, item_name: "x", sku: "PHA-0001", price: 1, currency: "EUR",
  stock_qty: 2, lat: 40.4, lng: -3.7,
});

describe("usePingSequence", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("pings shops one by one, 120ms apart, in rank order", () => {
    const results = [mk("osm:node:1", 1), mk("osm:node:2", 2), mk("osm:node:3", 3)];
    const { result } = renderHook(() => usePingSequence(results, "k1"));
    expect(result.current.size).toBe(0);
    act(() => vi.advanceTimersByTime(120));
    expect([...result.current]).toEqual(["osm:node:1"]);
    act(() => vi.advanceTimersByTime(240));
    expect(result.current.size).toBe(3);
  });

  it("restarts when the search key changes", () => {
    const results = [mk("osm:node:1", 1)];
    const { result, rerender } = renderHook(({ k }) => usePingSequence(results, k), { initialProps: { k: "a" } });
    act(() => vi.advanceTimersByTime(120));
    expect(result.current.size).toBe(1);
    rerender({ k: "b" });
    expect(result.current.size).toBe(0);
  });

  it("caps total sequence at 2.5s for long lists", () => {
    const results = Array.from({ length: 50 }, (_, i) => mk(`osm:node:${i}`, i + 1));
    const { result } = renderHook(() => usePingSequence(results, "k"));
    act(() => vi.advanceTimersByTime(2500));
    expect(result.current.size).toBe(50);
  });

  it("returns an empty set for undefined results", () => {
    const { result } = renderHook(() => usePingSequence(undefined, "k"));
    act(() => vi.advanceTimersByTime(1000));
    expect(result.current.size).toBe(0);
  });
});
