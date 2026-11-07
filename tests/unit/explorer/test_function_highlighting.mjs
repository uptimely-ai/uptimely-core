import assert from "node:assert/strict";
import test from "node:test";
import { initializeHighlighting } from "../../../src/uptimely/explorer/app/static/js/catalogs/function_highlighting.js";

function container(childNodes = [], nodeType = 1) {
  return {
    nodeType,
    childNodes,
    appendChild(node) {
      this.childNodes.push(node);
      return node;
    },
    replaceChild(replacement, current) {
      const index = this.childNodes.indexOf(current);
      this.childNodes.splice(index, 1, ...replacement.childNodes);
      return current;
    },
  };
}

const text = nodeValue => ({ nodeType: 3, nodeValue });
const token = (className, textContent) => ({ nodeType: 1, className, textContent });

test("Python function calls are highlighted without changing keywords or existing tokens", t => {
  const python = container([
    text("result = normalize(value)\nif (ready):\n    "),
    token("hljs-built_in", "print"),
    text("(result)\n"),
    token("hljs-string", "'normalize(value)'"),
  ]);
  const json = container([text('{"function": "normalize"}')]);
  python.classList = { contains: name => name === "language-python" };
  json.classList = { contains: () => false };
  const highlighted = [];
  const previousDocument = globalThis.document;
  const previousWindow = globalThis.window;
  globalThis.document = {
    querySelectorAll: () => [python, json],
    createDocumentFragment: () => container([], 11),
    createTextNode: text,
    createElement: () => ({ nodeType: 1, className: "", textContent: "" }),
  };
  globalThis.window = { hljs: { highlightElement: element => highlighted.push(element) } };
  t.after(() => {
    globalThis.document = previousDocument;
    globalThis.window = previousWindow;
  });

  initializeHighlighting();

  assert.deepEqual(highlighted, [python, json]);
  assert.deepEqual(
    python.childNodes.filter(node => node.className === "hljs-title function_")
      .map(node => node.textContent),
    ["normalize"],
  );
  assert.ok(python.childNodes.some(node => node.className === "hljs-built_in" && node.textContent === "print"));
  assert.ok(python.childNodes.some(node => node.className === "hljs-string"));
  assert.deepEqual(json.childNodes.map(node => node.nodeValue), ['{"function": "normalize"}']);
});
