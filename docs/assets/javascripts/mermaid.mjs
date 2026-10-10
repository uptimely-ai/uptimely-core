import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.esm.min.mjs";

mermaid.initialize({ startOnLoad: false });
await mermaid.run({ querySelector: "code.language-mermaid" });
