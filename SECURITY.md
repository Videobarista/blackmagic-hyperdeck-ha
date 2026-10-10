# Security Policy

## Supported versions

Only the most recent release receives security fixes.

| Version | Supported |
| --- | --- |
| Latest release | Yes |
| Older releases | No |

## Reporting a vulnerability

Please report security issues privately through GitHub's
[security advisory form](https://github.com/Videobarista/blackmagic-teranex-ha/security/advisories/new)
rather than in a public issue.

Expect an initial response within 14 days. This is a hobby project maintained
in spare time, so please allow reasonable time for a fix before any public
disclosure.

## Scope

This integration talks to a Teranex over the Blackmagic Teranex Ethernet
Protocol on TCP port 9800. Relevant to note:

- **The protocol has no authentication or encryption.** Anyone able to reach
  port 9800 can read and change the device configuration. Keep video equipment
  on a management VLAN that is not routed to the internet.
- The integration stores only the host and port in the Home Assistant config
  entry. No credentials are involved, because the protocol has none.
- Connections are outbound only. The integration opens no listening ports.

Vulnerabilities in the Teranex firmware itself belong to Blackmagic Design,
not to this repository.
