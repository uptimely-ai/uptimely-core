# Release 15: Explorer frontend and FastAPI package separation

This is a planned release grouping, not a published software version.

## Work package: Separate Explorer frontend and FastAPI packages

Move the Explorer browser frontend and FastAPI server into their own packages
under `src/uptimely`, instead of keeping both within the existing Explorer
package.

**Prerequisites:** Existing Explorer frontend, FastAPI server, and static export.

| title | breaking | description |
|---|---|---|
| Create a dedicated frontend package | No | Move browser code and assets into a package under `src/uptimely`. Keep it usable by both live serving and static export. |
| Create a separate FastAPI package | No | Move the FastAPI server and frontend integration into a separate package under `src/uptimely`. |
| Preserve Explorer entry points and assets | No | Preserve behavior, supported imports, CLI entry points, and installed static assets. Add compatibility imports where paths change. |
| Verify Explorer package delivery | No | Test imports, installed asset availability, live serving, and static export. Update relevant documentation. |
