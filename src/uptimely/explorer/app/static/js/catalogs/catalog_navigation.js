export function initializeCatalog(signal) {
  const catalogPanel = document.getElementById("catalog-context");
  const catalogItems = [...document.querySelectorAll("main [data-context-item]")];
  const catalogGroups = [...document.querySelectorAll("main [data-function-group]")];
  const catalogLinks = [...catalogPanel.querySelectorAll('a[href^="#"]')];
  const catalogNavigationLinks = [...document.querySelectorAll(
    '#catalog-context a[href^="#"], main a[href^="#"]')];
  const catalogTitle = document.querySelector("main h1 span");
  const catalogSectionTitle = catalogTitle.textContent;
  const catalogDocumentTitle = document.title;
  const catalogHeading = document.querySelector("main h1");
  const catalogIcon = catalogHeading.querySelector("[data-lucide]").cloneNode(true);
  const catalogSectionCount = document.querySelector("[data-section-count]");
  const catalogDescription = document.querySelector("[data-section-description]");
  const catalogSectionDescription = catalogDescription?.textContent;
  catalogHeading.setAttribute("tabindex", "-1");
  history.scrollRestoration = "manual";
  let scrollFrame;
  signal.addEventListener("abort", () => cancelAnimationFrame(scrollFrame), { once: true });

  function showCatalogTop() {
    window.scrollTo({ top: 0, left: 0, behavior: "instant" });
  }

  function selectCatalogItem(hash = location.hash) {
    if (!catalogItems.length) return;
    const link = catalogLinks.find(candidate => candidate.hash === hash) || catalogLinks[0];
    const target = document.getElementById(decodeURIComponent(link.hash.slice(1)));
    const selected = catalogItems.find(item => item === target || target.contains(item));
    const isOverview = selected.id === "catalog-overview";
    const dimensionLabel = document.querySelector("[data-dimension-label]");
    if (dimensionLabel) dimensionLabel.hidden = isOverview;
    if (catalogSectionCount) {
      catalogSectionCount.hidden = !isOverview;
    }
    const itemHeading = selected.querySelector("h2, h3");
    const title = isOverview ? catalogSectionTitle : itemHeading.textContent.trim();
    catalogTitle.textContent = title;
    if (catalogPanel.dataset.contextLabel === "features") {
      const selectedIcon = isOverview ? catalogIcon : itemHeading.querySelector("[data-lucide]");
      const headingIcon = catalogHeading.querySelector("[data-lucide]");
      if (selectedIcon) {
        const icon = selectedIcon.cloneNode(true);
        icon.setAttribute("class", "title-icon");
        headingIcon.replaceWith(icon);
      } else {
        headingIcon.replaceWith(catalogIcon.cloneNode(true));
      }
      if (!isOverview) {
        catalogHeading.setAttribute("title", itemHeading.querySelector(".typed-name").title);
      } else {
        catalogHeading.removeAttribute("title");
      }
    }
    if (["functions", "features", "dimensions", "profiles"].includes(catalogPanel.dataset.contextLabel) && catalogDescription) {
      const descriptionSelector = {
        functions: "[data-function-description]",
        features: "[data-feature-description]",
        dimensions: "[data-dimension-description]",
        profiles: "[data-profile-description]",
      }[catalogPanel.dataset.contextLabel];
      const description = selected.querySelector(descriptionSelector);
      catalogDescription.textContent = isOverview
        ? catalogSectionDescription : description?.textContent || "";
      catalogDescription.hidden = !catalogDescription.textContent.trim();
      if (description && !isOverview) description.hidden = true;
    }
    document.title = isOverview ? catalogDocumentTitle : `${title} · ${catalogSectionTitle}`;
    catalogItems.forEach(item => {
      const heading = item.querySelector("h2, h3");
      if (heading) heading.hidden = item === selected && !isOverview;
    });
    catalogItems.forEach(item => { item.hidden = item !== selected; });
    catalogGroups.forEach(group => { group.hidden = !group.contains(selected); });
    catalogLinks.forEach(candidate => {
      if (decodeURIComponent(candidate.hash.slice(1)) === selected.id) {
        candidate.setAttribute("aria-current", "location");
      } else {
        candidate.removeAttribute("aria-current");
      }
    });
    showCatalogTop();
    cancelAnimationFrame(scrollFrame);
    scrollFrame = requestAnimationFrame(showCatalogTop);
  }

  selectCatalogItem();
  catalogNavigationLinks.forEach(link => {
    link.addEventListener("click", event => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      if (location.hash !== link.hash) history.pushState(null, "", link.hash);
      selectCatalogItem(link.hash);
      catalogHeading.focus({ preventScroll: true });
    });
  });
  return { update: () => selectCatalogItem() };
}
