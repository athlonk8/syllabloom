import { describe, expect, it } from "vitest";
import { formatPercent, formatSeconds } from "./format";

describe("learning display formatting", () => {
  it("renders durations without impossible negative values", () => {
    expect(formatSeconds(-5)).toBe("0s");
    expect(formatSeconds(3660)).toBe("1h 1m");
  });

  it("clamps progress for UI display", () => {
    expect(formatPercent(0.853)).toBe("85%");
    expect(formatPercent(4)).toBe("100%");
  });
});
