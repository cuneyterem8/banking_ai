import { describe, expect, it } from "vitest";

import { STARTUP_USE_CASE_SLUGS } from "./startupTraining";
import { USE_CASES } from "./useCases";

describe("use case navigation", () => {
  it("contains exactly ten staged use cases", () => {
    expect(USE_CASES).toHaveLength(10);
    expect(USE_CASES.map((item) => item.order)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
  });

  it("marks the first eight staged use cases as implemented in stage eight", () => {
    expect(USE_CASES.filter((item) => item.status === "implemented").map((item) => item.slug)).toEqual([
      "fraud-detection",
      "credit-risk",
      "document-ocr",
      "support-chatbot",
      "liquidity-forecast",
      "aml-monitoring",
      "kyc-kyb",
      "email-automation"
    ]);
  });

  it("keeps the frontend startup order aligned with the implemented use cases", () => {
    expect(STARTUP_USE_CASE_SLUGS).toEqual(USE_CASES.slice(0, 8).map((item) => item.slug));
  });
});
