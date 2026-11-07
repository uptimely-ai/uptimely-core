const PYTHON_KEYWORDS = new Set([
  "and", "as", "assert", "async", "await", "break", "case", "class", "continue", "def", "del",
  "elif", "else", "except", "finally", "for", "from", "global", "if", "import", "in", "is",
  "lambda", "match", "nonlocal", "not", "or", "pass", "raise", "return", "try", "while", "with",
  "yield",
]);

function highlightPythonCalls(element) {
  for (const textNode of [...element.childNodes]) {
    if (textNode.nodeType !== 3) continue;
    const text = textNode.nodeValue;
    const matches = [...text.matchAll(/\b([A-Za-z_]\w*)(?=\s*\()/g)]
      .filter(match => !PYTHON_KEYWORDS.has(match[1]));
    if (!matches.length) continue;

    const replacement = document.createDocumentFragment();
    let offset = 0;
    for (const match of matches) {
      replacement.appendChild(document.createTextNode(text.slice(offset, match.index)));
      const name = document.createElement("span");
      name.className = "hljs-title function_";
      name.textContent = match[1];
      replacement.appendChild(name);
      offset = match.index + match[1].length;
    }
    replacement.appendChild(document.createTextNode(text.slice(offset)));
    element.replaceChild(replacement, textNode);
  }
}

export function initializeHighlighting() {
  document.querySelectorAll("pre code.language-python, code.language-json").forEach((element) => {
    window.hljs.highlightElement(element);
    if (element.classList.contains("language-python")) highlightPythonCalls(element);
  });
}
