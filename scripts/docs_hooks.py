"""Page navigation settings for the documentation."""

from mkdocs.structure import pages, toc


def on_page_content(html: str, *, page: pages.Page, **kwargs: object) -> str:
    """Limit local navigation to Python API reference pages.

    Args:
        html: Rendered page content.
        page: Page being rendered, including its visibility metadata.
        **kwargs: Additional MkDocs event arguments.

    Returns:
        The unchanged page content.
    """
    if not page.file.src_uri.startswith("python/"):
        hidden = page.meta.setdefault("hide", [])
        if "toc" not in hidden:
            hidden.append("toc")
    if "toc" in page.meta.get("hide", []):
        page.toc = toc.TableOfContents([])
    return html
