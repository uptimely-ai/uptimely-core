export function initializeHighlighting() {
  document.querySelectorAll("pre code.language-python").forEach((element) => {
    window.hljs.highlightElement(element);
  });
}
