import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import ModelPicker from "../components/ModelPicker";

function mockFetchOnce(url: RegExp, body: unknown, init: ResponseInit = { status: 200 }) {
  const current = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
  current.mockImplementationOnce(async (input: RequestInfo) => {
    const u = typeof input === "string" ? input : input.toString();
    if (!url.test(u)) throw new Error(`unexpected fetch: ${u}`);
    return new Response(JSON.stringify(body), init);
  });
}

describe("ModelPicker", () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn();
  });

  it("loads models and shows them in the dropdown", async () => {
    mockFetchOnce(/\/api\/models/, {
      provider: "ollama",
      base_url: "http://x",
      models: [
        { id: "a", supports_vision: null },
        { id: "b", supports_vision: true },
      ],
      selected: "a",
    });
    render(<ModelPicker />);
    await waitFor(() =>
      expect(screen.getByTestId("model-select")).toHaveValue("a"),
    );
    const options = screen.getAllByRole("option");
    const labels = options.map((o) => o.textContent);
    expect(labels).toContain("a");
    expect(labels.some((l) => l?.includes("b"))).toBe(true);
  });

  it("posts the selection when the user changes the dropdown", async () => {
    mockFetchOnce(/\/api\/models/, {
      provider: "ollama",
      base_url: "http://x",
      models: [{ id: "a", supports_vision: null }, { id: "b", supports_vision: null }],
      selected: "a",
    });
    render(<ModelPicker />);
    await screen.findByDisplayValue("a");
    mockFetchOnce(/\/api\/models\/select/, { selected: "b" });
    fireEvent.change(screen.getByTestId("model-select"), { target: { value: "b" } });
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledTimes(2));
    const callUrl = (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[1][0];
    expect(callUrl).toContain("/api/models/select");
  });
});
