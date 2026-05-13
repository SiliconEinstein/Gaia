# Security Policy

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for suspected security vulnerabilities. Public
issues are world-readable and would expose the report before a fix is available.

Instead, use GitHub's private vulnerability reporting:

1. Navigate to the repository's **Security** tab on GitHub.
2. Choose **Report a vulnerability**.
3. Fill in a clear description, reproduction steps, affected version, and any proof-of-concept
   or impact analysis you can share.

Reports are received privately by the maintainers and are not disclosed until a fix is ready.

## Supported Versions

Only the current minor release line receives security updates. Older minor lines are not
patched.

| Version | Supported          |
| ------- | ------------------ |
| 0.5.x   | :white_check_mark: |
| < 0.5   | :x:                |

## Response Time

- Acknowledgement within **7 days** of the report.
- Status updates at least **weekly** until the issue is resolved or closed.
- Coordinated disclosure: the fix, advisory, and (where applicable) CVE are published through
  **GitHub Security Advisories** once a release containing the fix is available.
