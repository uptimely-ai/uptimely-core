export function initializeMobileContext(signal, closeNavigation) {
  const panel = document.querySelector(".site-context");
  if (!panel) return;
  const bar = document.querySelector(".mobile-context-bar");
  const toggle = bar.querySelector(".mobile-context-toggle");
  const controls = bar.querySelector(".mobile-primary-controls");
  const closeButton = panel.querySelector(".context-sheet-close");
  const backdrop = document.querySelector(".context-backdrop");
  const content = document.querySelector(".site-content");
  const topbar = document.querySelector(".site-topbar");
  const media = window.matchMedia("(max-width: 640px)");
  const movable = [...panel.querySelectorAll(
    ".lineage-control-groups, .animation-dataset-picker, .data-lineage-toolbar",
  )].map(element => {
    const placeholder = document.createComment("Desktop controls");
    element.before(placeholder);
    return { element, placeholder };
  });
  toggle.setAttribute("aria-controls", panel.id);

  function close(restoreFocus = false) {
    const wasOpen = panel.classList.contains("sheet-open");
    panel.classList.remove("sheet-open");
    backdrop.classList.remove("is-open");
    toggle.setAttribute("aria-expanded", "false");
    panel.removeAttribute("role");
    panel.removeAttribute("aria-modal");
    content.inert = topbar.inert = bar.inert = false;
    document.body.classList.remove("context-sheet-open");
    if (wasOpen && restoreFocus) toggle.focus({ preventScroll: true });
  }

  function responsiveControls() {
    const focusInPanel = panel.contains(document.activeElement);
    close();
    movable.forEach(({ element, placeholder }) => {
      if (media.matches) controls.append(element);
      else placeholder.after(element);
    });
    document.documentElement.style.setProperty("--mobile-context-height",
      media.matches ? `${bar.getBoundingClientRect().height}px` : "0px");
    if (focusInPanel && media.matches) toggle.focus({ preventScroll: true });
    else if (!media.matches && document.activeElement === closeButton) {
      panel.querySelector(".context-label-toggle").focus({ preventScroll: true });
    }
  }

  toggle.addEventListener("click", () => {
    closeNavigation();
    panel.classList.add("sheet-open");
    panel.scrollTop = 0;
    backdrop.classList.add("is-open");
    toggle.setAttribute("aria-expanded", "true");
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-modal", "true");
    content.inert = topbar.inert = bar.inert = true;
    document.body.classList.add("context-sheet-open");
    closeButton.focus({ preventScroll: true });
  });
  closeButton.addEventListener("click", () => close(true));
  backdrop.addEventListener("click", () => close(true));
  panel.querySelectorAll('a[href^="#"]').forEach(link => {
    link.addEventListener("click", event => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      close();
    }, { capture: true });
  });
  document.addEventListener("keydown", event => {
    if (!panel.classList.contains("sheet-open")) return;
    if (event.key === "Escape") {
      event.preventDefault();
      close(true);
    } else if (event.key === "Tab") {
      const focusable = [...panel.querySelectorAll("a[href], button, select, summary, [tabindex]")]
        .filter(element => !element.disabled && element.tabIndex >= 0 && element.getClientRects().length);
      const first = focusable[0], last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  }, { signal });
  media.addEventListener("change", responsiveControls, { signal });
  const resize = new ResizeObserver(() => {
    document.documentElement.style.setProperty("--mobile-context-height",
      media.matches ? `${bar.getBoundingClientRect().height}px` : "0px");
  });
  resize.observe(bar);
  signal.addEventListener("abort", () => {
    resize.disconnect();
    close();
    document.documentElement.style.removeProperty("--mobile-context-height");
  }, { once: true });
  responsiveControls();
}
