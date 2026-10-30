const navigation = document.querySelector("#explorer-navigation");
const navigationToggle = document.querySelector(".mobile-nav-toggle");
const labelToggle = document.querySelector(".nav-label-toggle");
const contextPanel = document.querySelector("#lineage-context");
const contextToggle = document.querySelector(".context-toggle");
const contextClose = document.querySelector(".context-close");
const contextLabelToggle = document.querySelector(".context-label-toggle");

const closeContext = () => {
  contextPanel?.classList.remove("is-open");
  contextToggle?.setAttribute("aria-expanded", "false");
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
  const closeNavigation = () => {
    navigation.classList.remove("is-open");
    navigationToggle.setAttribute("aria-expanded", "false");
    navigationToggle.setAttribute("aria-label", "Open navigation");
  };

  navigationToggle.addEventListener("click", () => {
    closeContext();
    const isOpen = navigationToggle.getAttribute("aria-expanded") !== "true";
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
  });

  window.matchMedia("(max-width: 640px)").addEventListener("change", closeNavigation);
}

if (contextPanel && contextToggle && contextClose) {
  contextToggle.addEventListener("click", () => {
    const isOpen = contextToggle.getAttribute("aria-expanded") !== "true";
    if (navigationToggle?.getAttribute("aria-expanded") === "true") navigationToggle.click();
    contextPanel.classList.toggle("is-open", isOpen);
    contextToggle.setAttribute("aria-expanded", String(isOpen));
    if (isOpen) contextClose.focus();
  });
  contextClose.addEventListener("click", () => {
    closeContext();
    contextToggle.focus();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && contextPanel.classList.contains("is-open")) {
      closeContext();
      contextToggle.focus();
    }
  });
  window.matchMedia("(max-width: 640px)").addEventListener("change", () => {
    const focusInContext = contextPanel.contains(document.activeElement);
    closeContext();
    if (focusInContext && window.matchMedia("(max-width: 640px)").matches) contextToggle.focus();
  });
}

if (contextPanel && contextLabelToggle) {
  contextLabelToggle.addEventListener("click", () => {
    const collapsed = contextPanel.classList.toggle("is-collapsed");
    const label = collapsed ? "Expand lineage context" : "Collapse lineage context";
    contextLabelToggle.setAttribute("aria-pressed", String(collapsed));
    contextLabelToggle.setAttribute("aria-label", label);
    contextLabelToggle.setAttribute("title", label);
  });
}

lucide.createIcons();
