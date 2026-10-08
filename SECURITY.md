# Security Policy

## Scope

Uptimely Core executes Python functions declared in specifications and plans
(`module:function` entrypoints are imported and run by the engine and the MCP
server's `execute_feature` tool). Only run specifications, plans, and function
entrypoints from sources you trust — a specification is code.

## Supported Versions

While the project is in `0.x`, only the latest minor release receives security
fixes.

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

Please do not open public issues for security vulnerabilities.

Report them privately via GitHub's **Report a vulnerability** feature on the
repository's Security tab, or by emailing the maintainers found from https://uptimely.ai.

We aim to acknowledge reports within 3 working days and to provide an
assessment within 10 working days.
