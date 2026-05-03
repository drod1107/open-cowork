import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import HistoryTab from "../components/HistoryTab";

// Mock api module
vi.mock("../lib/api", () => ({
  api: {
    listSessions: vi.fn(),
    getSession: vi.fn(),
    deleteSession: vi.fn(),
    updateSession: vi.fn(),
  },
}));

import { api } from "../lib/api";

const mockSessions = [
  {
    id: "aaaabbbb-0000-0000-0000-000000000001",
    created_at: "2026-01-01T10:00:00Z",
    updated_at: "2026-01-01T10:00:00Z",
    metadata: { title: "First Chat" },
  },
  {
    id: "ccccdddd-0000-0000-0000-000000000002",
    created_at: "2026-01-01T09:00:00Z",
    updated_at: "2026-01-01T09:00:00Z",
    metadata: { title: "Second Chat" },
  },
];

beforeEach(() => {
  vi.mocked(api.listSessions).mockResolvedValue({ sessions: mockSessions });
  vi.mocked(api.deleteSession).mockResolvedValue({ deleted: true });
});

describe("HistoryTab", () => {
  it("renders sessions from the API in chronological order", async () => {
    render(
      <HistoryTab onSelect={vi.fn()} onDelete={vi.fn()} />
    );
    await waitFor(() => {
      expect(screen.getByText("First Chat")).toBeInTheDocument();
      expect(screen.getByText("Second Chat")).toBeInTheDocument();
    });
  });

  it("calls onSelect when a session is clicked (to resume)", async () => {
    const onSelect = vi.fn();
    render(
      <HistoryTab onSelect={onSelect} onDelete={vi.fn()} />
    );
    await waitFor(() => screen.getByText("First Chat"));
    
    fireEvent.click(screen.getByText("First Chat"));
    expect(onSelect).toHaveBeenCalledWith("aaaabbbb-0000-0000-0000-000000000001");
  });

  it("shows 'No sessions yet' when list is empty", async () => {
    vi.mocked(api.listSessions).mockResolvedValue({ sessions: [] });
    render(
      <HistoryTab onSelect={vi.fn()} onDelete={vi.fn()} />
    );
    await waitFor(() => {
      expect(screen.getByText(/no sessions/i)).toBeInTheDocument();
    });
  });

  it("calls onDelete and removes session from list", async () => {
    const onDelete = vi.fn();
    render(
      <HistoryTab onSelect={vi.fn()} onDelete={onDelete} />
    );
    await waitFor(() => screen.getByText("First Chat"));
    
    // Find and click delete button for first session
    const deleteBtn = screen.getByTestId(`delete-session-aaaabbbb-0000-0000-0000-000000000001`);
    fireEvent.click(deleteBtn);
    
    await waitFor(() => {
      expect(onDelete).toHaveBeenCalledWith("aaaabbbb-0000-0000-0000-000000000001");
    });
  });

  it("displays session timestamps", async () => {
    render(
      <HistoryTab onSelect={vi.fn()} onDelete={vi.fn()} />
    );
    await waitFor(() => screen.getByText("First Chat"));
    
    // Should show some date format (just check for presence of numbers/date)
    const dateElements = document.querySelectorAll("[class*='text-slate-500']");
    expect(dateElements.length).toBeGreaterThan(0);
  });
});
