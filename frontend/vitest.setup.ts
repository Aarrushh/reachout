import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

/**
 * Two things every component test in this project needs, in one place.
 *
 * 1. RTL's automatic per-test cleanup only installs itself when vitest runs
 *    with `globals: true`. This project does not, so without an explicit
 *    `afterEach(cleanup)` every render stacks up in the same document and the
 *    second test onward fails with "found multiple elements".
 *
 * 2. jsdom implements no scrolling, so `Element.prototype.scrollTo` is simply
 *    absent. `ChatPanel` calls it after every render to keep the newest
 *    message in view, which makes it — and anything that mounts it, including
 *    `AppShell` in retail mode — untestable without this stub.
 */
afterEach(cleanup);

Element.prototype.scrollTo = () => {};
