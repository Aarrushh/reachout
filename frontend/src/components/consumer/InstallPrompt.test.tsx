import { fireEvent, render, screen } from "@testing-library/react";
import { act } from "react";
import { describe, expect, it, vi } from "vitest";

import InstallPrompt from "./InstallPrompt";

/** The event Chrome fires when it judges the app installable. */
function firePrompt() {
  const event: Event & { prompt?: () => Promise<void>; userChoice?: unknown } = new Event(
    "beforeinstallprompt",
  );
  const prompt = vi.fn(async () => {});
  event.prompt = prompt;
  act(() => {
    window.dispatchEvent(event);
  });
  return prompt;
}

describe("InstallPrompt", () => {
  it("renders nothing until the browser offers a prompt", () => {
    const { container } = render(<InstallPrompt lang="en" />);

    // Without the deferred event there is no prompt to open, so a button
    // rendered anyway would do nothing when pressed.
    expect(container.querySelector(".install-prompt")).toBeNull();
  });

  it("appears once the browser offers one", () => {
    render(<InstallPrompt lang="en" />);
    firePrompt();

    expect(screen.getByRole("button", { name: /install the app/i })).toBeTruthy();
  });

  it("opens the browser's prompt and then removes itself", () => {
    render(<InstallPrompt lang="en" />);
    const prompt = firePrompt();

    fireEvent.click(screen.getByRole("button", { name: /install the app/i }));

    expect(prompt).toHaveBeenCalledTimes(1);
    // The browser will not replay a deferred prompt, so a button left on
    // screen would be dead on its second press.
    expect(screen.queryByRole("button", { name: /install the app/i })).toBeNull();
  });

  it("disappears when the app is installed elsewhere", () => {
    render(<InstallPrompt lang="en" />);
    firePrompt();
    act(() => {
      window.dispatchEvent(new Event("appinstalled"));
    });

    expect(screen.queryByRole("button", { name: /install the app/i })).toBeNull();
  });

  it("speaks Spanish", () => {
    render(<InstallPrompt lang="es" />);
    firePrompt();

    expect(screen.getByRole("button", { name: /instalar la app/i })).toBeTruthy();
  });
});
