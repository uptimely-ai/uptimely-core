import { initializeMobileContext } from "./mobile_context.js";

export function initializeIcons(signal) {
  const navigation = document.querySelector("#explorer-navigation");
  const navigationToggle = document.querySelector(".mobile-nav-toggle");
  const labelToggle = document.querySelector(".nav-label-toggle");
  const contextPanel = document.querySelector(".site-context");
  const contextLabelToggle = document.querySelector(".context-label-toggle");

  const closeNavigation = () => {
    navigation?.classList.remove("is-open");
    navigationToggle?.setAttribute("aria-expanded", "false");
    navigationToggle?.setAttribute("aria-label", "Open navigation");
  };

  if (navigation && labelToggle) {
    labelToggle.addEventListener("click", () => {
      const labelsHidden = navigation.classList.toggle("labels-hidden");
      const label = labelsHidden ? "Show navigation labels" : "Hide navigation labels";
      labelToggle.setAttribute("aria-pressed", String(labelsHidden));
      labelToggle.setAttribute("aria-label", label);
      labelToggle.setAttribute("title", label);
    });
  }

  if (navigation && navigationToggle) {
    navigationToggle.addEventListener("click", () => {
      const isOpen = navigationToggle.getAttribute("aria-expanded") !== "true";
      if (isOpen) navigation.scrollTop = 0;
      navigation.classList.toggle("is-open", isOpen);
      navigationToggle.setAttribute("aria-expanded", String(isOpen));
      navigationToggle.setAttribute("aria-label", isOpen ? "Close navigation" : "Open navigation");
    });

    navigation.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", closeNavigation);
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && navigation.classList.contains("is-open")) {
        closeNavigation();
        navigationToggle.focus();
      }
    }, { signal });

    window.matchMedia("(max-width: 640px)").addEventListener("change", () => {
      const focusInMenus = navigation.contains(document.activeElement)
        || contextPanel?.contains(document.activeElement);
      closeNavigation();
      if (focusInMenus && window.matchMedia("(max-width: 640px)").matches) navigationToggle.focus();
    }, { signal });
  }

  if (contextPanel) {
    contextPanel.querySelectorAll('a[href^="#"]').forEach((link) => {
      link.addEventListener("click", event => {
        if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        if (window.matchMedia("(max-width: 640px)").matches) {
          closeNavigation();
          const target = contextPanel.id === "catalog-context"
            ? document.querySelector("main h1")
            : contextPanel.id === "animation-context"
              ? document.querySelector("main")
              : document.getElementById(decodeURIComponent(link.hash.slice(1)));
          if (target) {
            target.setAttribute("tabindex", "-1");
            target.focus({ preventScroll: true });
          }
        }
      });
    });
  }

  if (contextPanel && contextLabelToggle) {
    contextLabelToggle.addEventListener("click", () => {
      const collapsed = contextPanel.classList.toggle("is-collapsed");
      const contextLabel = contextPanel.dataset.contextLabel || "lineage";
      const label = `${collapsed ? "Expand" : "Collapse"} ${contextLabel} context`;
      contextLabelToggle.setAttribute("aria-pressed", String(collapsed));
      contextLabelToggle.setAttribute("aria-label", label);
      contextLabelToggle.setAttribute("title", label);
    });
  }

  initializeMobileContext(signal, closeNavigation);
  lucide.createIcons();
}
