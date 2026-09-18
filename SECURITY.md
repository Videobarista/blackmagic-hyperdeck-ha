# Security Policy

## Supported Versions

Only the latest released version of this integration is supported with fixes, including security fixes. Please update to the latest release before reporting an issue.

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please **do not** open a public issue. Instead, use GitHub's private reporting feature:

[Report a vulnerability](https://github.com/Videobarista/blackmagic-hyperdeck-ha/security/advisories/new)

This is a hobby project maintained in spare time, not a commercial product with a dedicated security team. You should get an acknowledgement within a few days; please allow time for a fix to be developed and tested, especially for anything that needs access to real HyperDeck hardware to verify.

## Scope

This integration communicates with a HyperDeck device over a local network connection (TCP, HyperDeck Ethernet Protocol). It does not send data anywhere else. As with any local-network integration, only expose the HyperDeck and your Home Assistant instance on networks you trust.
