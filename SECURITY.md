# Security policy

Security fixes target the current `main` branch. There is no guaranteed
response time or long-term support commitment for this hackathon project.

## Report a vulnerability

Use **Security → Advisories → Report a vulnerability** on the GitHub repository
when private reporting is enabled. Include the affected commit or deployment,
reproduction steps with dummy data, and likely impact. Do not include real
credentials, personal user data, or exploit details in public issues.

If that button is unavailable, open an issue asking the maintainer to enable
private reporting without including vulnerability details. Maintainers can
[enable private reporting](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/configure-for-a-repository).

## Checks included in this repository

- CI scans Git history for secrets using a digest-pinned Gitleaks container.
  Findings are redacted, and the scanner runs without network access.
- CI audits installed Python dependencies for known vulnerabilities.
- Dependabot proposes weekly Python and GitHub Actions updates for review.
- GitHub Actions have read-only repository permissions, pinned action commits,
  job timeouts and no persisted checkout credentials. Pull requests do not
  run with `pull_request_target` or receive repository deployment secrets.
- Credential file patterns are excluded from Git and the Docker build context.
  Ignore rules do not remove files that were committed previously.
- Docker runs as a non-root user. Report rendering uses Chromium, so rebuild
  regularly to receive browser and base-image security updates.

These checks reduce risk; they do not establish that the app is vulnerability-free.

## Maintainer settings before public release

In GitHub repository **Settings → Advanced Security**, review and enable
secret scanning, push protection, Dependabot alerts/security updates and
private vulnerability reporting where available. See
[GitHub's repository security settings](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-security-and-analysis-settings-for-your-repository).
These settings are separate from committed configuration; adding these files
does not enable account or repository settings automatically.

For a public `main` branch, use a ruleset requiring pull requests and passing
checks, and block force pushes and branch deletion where supported. Review
external contributions before running privileged workflows or deploying them.
Enable two-factor authentication on the maintainer's GitHub account.

Commit author names and email addresses, history, screenshots, and tracked
planning documents become public when repository visibility changes. Use a
GitHub-provided no-reply email for future commits if desired. Changing that
setting does not erase historical email addresses; history changes require
separate review and coordination.

## Deployment and evidence handling

The app needs no API keys. Keep any future credentials in host-managed secrets
or environment variables, never source code, screenshots or example files.
If a credential is committed, revoke or rotate it first; deleting the latest
copy or adding an ignore rule does not invalidate it.

Use HTTPS through the hosting provider. Avoid entering confidential information
in this public demo. Notes and quiz progress live in a browser session; exported
reports contain notes and evidence, so review them before sharing. Satellite
and temperature downloads use local caches that may disappear on restarts.

Validate the bundled data and report renderer before release using
`python scripts/check_deployment.py --render-report`, run the Python tests,
and perform the public-URL checks in [DEPLOYMENT.md](DEPLOYMENT.md). Recheck
third-party provenance when replacing datasets or images.
