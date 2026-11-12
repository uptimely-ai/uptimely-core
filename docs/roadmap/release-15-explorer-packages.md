# Release 15: Explorer frontend and FastAPI package separation

This is a planned release grouping, not a published software version.

## Work package: Separate Explorer frontend and FastAPI packages

Move the Explorer browser frontend and FastAPI server into their own packages
under `src/uptimely`, instead of keeping both within the existing Explorer
package.

**Prerequisites:** Existing Explorer frontend, FastAPI server, and static export.

| title | breaking | description |
|---|---|---|
| Split Explorer frontend and FastAPI packages | No | Give the browser frontend and its assets a dedicated package, and give the FastAPI server and its integration a separate package under `src/uptimely`. Keep the frontend usable by both the live server and static export. Preserve existing Explorer behavior, supported imports, CLI entry points, and static-asset inclusion in built distributions, or provide clear compatibility imports where paths must change. Test package imports, installed asset availability, live serving, and static export. Update relevant documentation. |
