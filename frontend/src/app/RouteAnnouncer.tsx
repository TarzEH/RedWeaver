/**
 * Client-side navigation accessibility for the app shell.
 *
 * A full page load gives you three things for free that React Router does not:
 * focus resets to the top of the document, assistive tech announces the new
 * page, and the browser restores scroll position on Back. Swapping the DOM under
 * a screen-reader user provides none of them — focus stays on the link they just
 * activated (now detached), and nothing says the screen changed.
 *
 * This module restores all three centrally, so the eleven feature screens don't
 * each have to remember to.
 *
 * Why it is hand-rolled: the app mounts `<BrowserRouter>` + `<Routes>`, not
 * `createBrowserRouter`. React Router's own `<ScrollRestoration>` requires the
 * data router and throws outside it, and `<Link prefetch>` is framework-mode
 * only. Migrating the router is a much larger change than this fix warrants.
 *
 * The announcer is deliberately `aria-live="polite"`, not `assertive`. Next.js
 * ships assertive and has been criticised for it: assertive interrupts the
 * reader mid-sentence, which is exactly what you don't want when someone is
 * still hearing the link they activated.
 */

import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { documentTitleFor, nameFromPathname, routeName } from "./routeTitles";

/** Give a screen this long to render its `<h1>` before we stop waiting to focus it. */
const H1_WAIT_MS = 2000;
/** Frames to keep re-applying a restored scroll offset while content streams in. */
const SCROLL_RETRY_FRAMES = 20;
/** Ceiling on the breadth-first scan for a screen's scroll container. */
const SCROLLER_SCAN_LIMIT = 80;

/**
 * Find the screen's scroll container.
 *
 * Screens own their own scrolling (`<div className="flex-1 overflow-y-auto">`)
 * while `<main>` is `overflow-hidden`, so the element whose scroll position
 * matters is a descendant, not `main` itself. A shallow breadth-first walk finds
 * it without the cost of `querySelectorAll("*") + getComputedStyle` on a large
 * findings table.
 */
function findScroller(root: HTMLElement): HTMLElement | null {
  let level: HTMLElement[] = [root];
  let scanned = 0;
  for (let depth = 0; depth <= 4 && level.length > 0; depth++) {
    for (const el of level) {
      if (++scanned > SCROLLER_SCAN_LIMIT) return null;
      const overflowY = getComputedStyle(el).overflowY;
      if (overflowY === "auto" || overflowY === "scroll") return el;
    }
    level = level.flatMap((el) => Array.from(el.children) as HTMLElement[]);
  }
  return null;
}

export function RouteAnnouncer() {
  const { pathname } = useLocation();
  const [announcement, setAnnouncement] = useState("");

  /**
   * Saved scroll offsets, keyed by pathname.
   *
   * This is the `getKey={loc => loc.pathname}` behaviour from
   * `<ScrollRestoration>`, not the default history-key behaviour. For triage
   * that distinction is the whole point: coming back to a long findings list
   * should return you to the row you were reading, whether you got there by
   * Back or by clicking the same link again. Keying on history entries would
   * treat those as different places and dump you at the top.
   */
  const scrollPositions = useRef(new Map<string, number>());
  /** Cached primary scroller, revalidated cheaply via `isConnected`. */
  const scroller = useRef<HTMLElement | null>(null);
  /**
   * A fresh page load already starts at the top with focus on the document.
   * Yanking focus to the `<h1>` there would be an unprompted focus change with
   * no navigation to justify it, so the very first route is observed only.
   */
  const isFirstRoute = useRef(true);

  useEffect(() => {
    const main = document.querySelector("main");
    if (!main) return;

    const firstRoute = isFirstRoute.current;
    isFirstRoute.current = false;

    let cancelled = false;
    let rafId = 0;
    let frames = 0;

    const currentScroller = (): HTMLElement | null => {
      if (!scroller.current || !scroller.current.isConnected) {
        scroller.current = findScroller(main as HTMLElement);
      }
      return scroller.current;
    };

    // ── Scroll ────────────────────────────────────────────────────────────
    // Re-apply across a few frames: the screen often mounts a spinner first, and
    // a scrollTop assignment against short content silently clamps to 0.
    const target = scrollPositions.current.get(pathname) ?? 0;
    const applyScroll = () => {
      if (cancelled) return;
      const el = currentScroller();
      if (el) {
        el.scrollTop = target;
        if (target === 0 || el.scrollTop === target) return;
      }
      if (frames++ < SCROLL_RETRY_FRAMES) rafId = requestAnimationFrame(applyScroll);
    };
    applyScroll();

    // `scroll` doesn't bubble, but it does reach capturing listeners on
    // ancestors — one listener on `main` therefore survives the screen
    // re-rendering its scroll container, which a listener bound to the element
    // itself would not. Filtered to the primary scroller so that nested panes
    // (the hunt detail panel) don't overwrite the page's own position.
    const onScroll = (event: Event) => {
      if (event.target === currentScroller()) {
        scrollPositions.current.set(pathname, (event.target as HTMLElement).scrollTop);
      }
    };
    main.addEventListener("scroll", onScroll, { capture: true, passive: true });

    // ── Title + announcement ──────────────────────────────────────────────
    // Resolution order is document.title → <h1> → pathname. The map feeds
    // document.title, so a mapped route wins; screens outside the map fall back
    // to whatever heading they render, then to the URL.
    const heading = () => main.querySelector<HTMLHeadingElement>("h1");
    const name =
      routeName(pathname) ?? heading()?.textContent?.trim() ?? nameFromPathname(pathname);
    document.title = documentTitleFor(name);
    setAnnouncement(name);

    // ── Focus ─────────────────────────────────────────────────────────────
    // The heading may not exist yet (screens render a spinner while loading), so
    // watch for it instead of assuming it is present on this commit.
    let observer: MutationObserver | undefined;
    let timeoutId = 0;

    const focusHeading = (h1: HTMLHeadingElement) => {
      // `tabIndex={-1}` makes a heading programmatically focusable without
      // adding it to the tab order. PageHeader already sets it; this covers
      // screens that render their own <h1>.
      if (!h1.hasAttribute("tabindex")) h1.setAttribute("tabindex", "-1");
      // preventScroll: the scroll position was just restored above, and focusing
      // would otherwise scroll the heading into view and undo it.
      h1.focus({ preventScroll: true });
    };

    if (!firstRoute) {
      const existing = heading();
      if (existing) {
        focusHeading(existing);
      } else {
        observer = new MutationObserver(() => {
          const h1 = heading();
          if (!h1 || cancelled) return;
          observer?.disconnect();
          window.clearTimeout(timeoutId);
          focusHeading(h1);
        });
        observer.observe(main, { childList: true, subtree: true });
        timeoutId = window.setTimeout(() => observer?.disconnect(), H1_WAIT_MS);
      }
    }

    return () => {
      cancelled = true;
      cancelAnimationFrame(rafId);
      window.clearTimeout(timeoutId);
      observer?.disconnect();
      main.removeEventListener("scroll", onScroll, { capture: true });
    };
  }, [pathname]);

  return (
    // Rendered unconditionally and always in the DOM: assistive tech only
    // announces changes to a live region that existed before the text changed,
    // so mounting the region and its content together would announce nothing.
    <div
      aria-live="polite"
      aria-atomic="true"
      className="sr-only"
      // Not `role="status"` as well — doubling the implicit role with an
      // explicit one makes some readers announce twice.
    >
      {announcement}
    </div>
  );
}
