import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { vi } from "vitest";

import { I18nProvider } from "../lib/i18n";
import { ToastProvider } from "../lib/toast";
import type { Mathom } from "../lib/types";
import MathomDetail from "./MathomDetail";

const { api } = vi.hoisted(() => ({
  api: {
    getMathom: vi.fn(),
    listTemplates: vi.fn(),
    listCollections: vi.fn(),
    updateSummary: vi.fn(),
    audioUrl: vi.fn(() => "/audio"),
    exportUrl: vi.fn(() => "/export"),
    updateMathom: vi.fn(),
    addTag: vi.fn(),
    streamChat: vi.fn(),
    streamSummary: vi.fn(),
    deleteSummary: vi.fn(),
    deleteMathom: vi.fn(),
    removeTag: vi.fn(),
    removeFromCollection: vi.fn(),
    addToCollection: vi.fn(),
    clearChat: vi.fn(),
  },
}));

vi.mock("../lib/api", () => ({ api }));

Object.defineProperty(Element.prototype, "scrollIntoView", {
  configurable: true,
  value: vi.fn(),
});

const mathom: Mathom = {
  id: 1,
  title: "A recording",
  status: "ready",
  duration_seconds: null,
  language: "en",
  favorite: false,
  archived: false,
  created_at: "2025-01-01T00:00:00Z",
  tags: [],
  original_filename: "recording.wav",
  error_message: null,
  transcript: "Transcript",
  segments: [],
  summaries: [
    {
      id: 7,
      template_slug: "tldr",
      template_name: "TL;DR",
      content: "Old summary",
      model: "mock",
      created_at: "2025-01-01T00:00:00Z",
    },
  ],
  chat_messages: [],
  collections: [],
  queue_position: null,
};

describe("MathomDetail summary editing", () => {
  it("saves an edited summary through the API", async () => {
    api.getMathom.mockResolvedValue(mathom);
    api.listTemplates.mockResolvedValue([]);
    api.listCollections.mockResolvedValue([]);
    api.updateSummary.mockResolvedValue(mathom.summaries[0]);
    render(
      <MemoryRouter initialEntries={["/mathoms/1"]}>
        <I18nProvider>
          <ToastProvider>
            <Routes>
              <Route path="/mathoms/:id" element={<MathomDetail />} />
            </Routes>
          </ToastProvider>
        </I18nProvider>
      </MemoryRouter>,
    );

    const summary = await screen.findByText("Old summary");
    const card = summary.closest("div.relative") as HTMLElement | null;
    expect(card).not.toBeNull();
    fireEvent.click(within(card!).getByRole("button", { name: "Edit" }));
    fireEvent.change(screen.getByDisplayValue("Old summary"), {
      target: { value: "Updated summary" },
    });
    fireEvent.click(within(card!).getByRole("button", { name: "Save" }));

    await waitFor(() => expect(api.updateSummary).toHaveBeenCalledWith(1, 7, "Updated summary"));
  });
});
