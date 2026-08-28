# Security Policy

## Reporting a vulnerability

Scanipy is a security tool, so we take vulnerabilities in it seriously.

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, use one of:

- GitHub's **private vulnerability reporting** ("Report a vulnerability" under the repository's
  **Security** tab), or
- email the maintainer at the address on the GitHub profile of the repository owner.

Please include:

- a description of the issue and its impact,
- steps to reproduce (a minimal PoC if possible),
- affected version / commit,
- any suggested remediation.

We aim to acknowledge reports within a few business days and will keep you updated on the fix and
disclosure timeline. We support coordinated disclosure and will credit reporters who wish to be
credited.

## Scope

In scope: the Scanipy platform code in this repository (analysis core, services, deploy tooling, CI).

Out of scope: vulnerabilities in third-party analysis engines Scanipy invokes (Semgrep, CodeQL, Joern)
— report those upstream — and issues that require a pre-compromised host or a malicious operator with
shell access to the deployment.

## A note on analysis safety

Scanipy analyzes source code; it does **not execute** the code it scans. The self-host deployment runs
analysis on a freshly cloned working tree only. When self-hosting, run the stack on infrastructure you
control and treat scanned repositories as untrusted input.
