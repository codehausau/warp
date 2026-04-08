# Security Policy

## Reporting a Vulnerability

Please do not open a public GitHub issue for an unpatched security vulnerability.

If you discover a vulnerability, report it privately to the maintainers. If GitHub private vulnerability reporting is enabled for the repository, please use that channel. Otherwise, contact the maintainers directly and include:

- a short description of the issue
- affected versions or deployment details
- reproduction steps or proof of concept
- any suggested mitigation, if known

We will aim to acknowledge reports promptly and work toward a fix before public disclosure.

## Security Baseline

This repository uses GitHub-native security automation as a baseline:

- Dependabot for dependency and GitHub Actions updates
- CodeQL for static analysis of Python and JavaScript
- dependency review on pull requests targeting `main`
- explicit GitHub Actions permissions instead of broad defaults

## Secrets Handling

- Never commit plaintext credentials, personal access tokens, session secrets, or database passwords.
- Use local environment variables or an untracked local secrets file for development.
- Use GitHub Actions secrets or organization secrets for CI/CD credentials.
- Rotate any credential immediately if it is exposed in a branch, issue, PR, workflow log, or local tracked file.

## Repository Admin Checklist

Repository administrators should enable or verify the following settings:

- Dependabot alerts
- Dependabot security updates
- secret scanning and push protection, where available
- code scanning alerts
- branch protection for `main`
- required status checks for CI, CodeQL, and dependency review
- least-privilege workflow permissions at the repository level
