export function initializeHighlighting() {
  document.querySelectorAll("pre code.language-python, code.language-json").forEach((element) => {
    window.hljs.highlightElement(element);
  });
}
