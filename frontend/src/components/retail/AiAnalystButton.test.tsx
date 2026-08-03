import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import AiAnalystButton from "./AiAnalystButton";

describe("AiAnalystButton (U6, deliberately dead)", () => {
  it("is present but disabled, and says so to assistive tech", () => {
    render(<AiAnalystButton lang="en" />);
    const button = screen.getByRole("button", { name: /ask ai about my analytics/i });

    expect((button as HTMLButtonElement).disabled).toBe(true);
    expect(button.getAttribute("aria-disabled")).toBe("true");
  });

  it("prints why it is unavailable on screen, not in a tooltip", () => {
    render(<AiAnalystButton lang="en" />);
    const button = screen.getByRole("button", { name: /ask ai/i });

    // A `title` would hide the reason behind a hover the phone cannot
    // perform, leaving a greyed button that looks like a bug.
    expect(button.getAttribute("title")).toBeNull();
    const why = screen.getByText(/not connected yet/i);
    expect(button.getAttribute("aria-describedby")).toBe(why.getAttribute("id"));
  });

  it("does nothing when clicked", () => {
    const { container } = render(<AiAnalystButton lang="en" />);
    const button = container.querySelector(".retail-askai__button") as HTMLButtonElement;

    // No handler exists to spy on, so assert the negative that matters: a
    // click raises nothing and the DOM is unchanged by it.
    const before = container.innerHTML;
    fireEvent.click(button);
    expect(container.innerHTML).toBe(before);
  });

  it("carries both strings in Spanish", () => {
    render(<AiAnalystButton lang="es" />);
    expect(screen.getByRole("button", { name: /pregunta a la ia/i })).toBeTruthy();
    expect(screen.getByText(/todavía no disponible/i)).toBeTruthy();
  });
});
