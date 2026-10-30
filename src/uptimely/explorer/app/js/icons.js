const navigation = document.querySelector("#explorer-navigation");
const navigationToggle = document.querySelector(".mobile-nav-toggle");
const labelToggle = document.querySelector(".nav-label-toggle");

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

lucide.createIcons();
