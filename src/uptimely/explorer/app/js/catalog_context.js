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
const catalogSectionCount = document.querySelector("[data-section-count]");
const catalogDescription = document.querySelector("[data-section-description]");
const catalogSectionDescription = catalogDescription?.textContent;
catalogHeading.setAttribute("tabindex", "-1");
history.scrollRestoration = "manual";

function showCatalogTop() {
  window.scrollTo({ top: 0, left: 0, behavior: "instant" });
}

function selectCatalogItem(hash = location.hash) {
  if (!catalogItems.length) return;
  const link = catalogLinks.find(candidate => candidate.hash === hash) || catalogLinks[0];
  const target = document.getElementById(decodeURIComponent(link.hash.slice(1)));
  const selected = catalogItems.find(item => item === target || target.contains(item));
  const isOverview = selected.id === "catalog-overview";
  if (catalogSectionCount) {
    catalogSectionCount.hidden = !isOverview;
  }
  const itemHeading = selected.querySelector("h2, h3");
  const title = isOverview ? catalogSectionTitle : itemHeading.textContent.trim();
  catalogTitle.textContent = title;
  if (catalogPanel.dataset.contextLabel === "functions" && catalogDescription) {
    const description = selected.querySelector("[data-function-description]");
    catalogDescription.textContent = isOverview ? catalogSectionDescription : description.textContent;
    if (description) description.hidden = true;
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
  requestAnimationFrame(showCatalogTop);
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
window.addEventListener("hashchange", () => selectCatalogItem());
window.addEventListener("popstate", () => selectCatalogItem());
window.addEventListener("load", () => selectCatalogItem());
window.addEventListener("pageshow", () => selectCatalogItem());
