import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import SchedulerPanel from "../components/Scheduler";

const responses: Array<() => Response> = [];

function queue(body: unknown, init: ResponseInit = { status: 200 }) {
  responses.push(() => new Response(JSON.stringify(body), init));
}

describe("SchedulerPanel", () => {
  beforeEach(() => {
    responses.length = 0;
    globalThis.fetch = vi.fn(async () => {
      const fn = responses.shift();
      if (!fn) throw new Error("unexpected fetch");
      return fn();
    }) as unknown as typeof fetch;
  });

  it("renders schedules returned by the api", async () => {
    queue({
      schedules: [
        { id: "a", description: "say hi", cron: "0 9 * * *", next_run: null },
      ],
    });
    render(<SchedulerPanel />);
    await waitFor(() =>
      expect(screen.getByText("say hi")).toBeInTheDocument(),
    );
  });

  it("creates a new schedule on submit", async () => {
    queue({ schedules: [] }); // initial list
    queue({ id: "xx", description: "walk dog", cron: "0 8 * * *", next_run: null });
    queue({ schedules: [{ id: "xx", description: "walk dog", cron: "0 8 * * *", next_run: null }] });
    render(<SchedulerPanel />);
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalled());
    fireEvent.change(screen.getByTestId("schedule-description"), {
      target: { value: "walk dog" },
    });
    fireEvent.change(screen.getByTestId("schedule-cron"), {
      target: { value: "0 8 * * *" },
    });
    fireEvent.click(screen.getByTestId("schedule-add"));
    await waitFor(() => expect(screen.getByText("walk dog")).toBeInTheDocument());
  });
});
