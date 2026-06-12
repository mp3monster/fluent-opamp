# Social Collaboration Deployment Automation

This page summarizes whether Slack, Microsoft Teams, and Discord deployment can
be automated when an operator provides approved administrative credentials or
tokens.

## Summary Matrix

| Platform | Automation level | What can be automated | Main limits |
| --- | --- | --- | --- |
| Slack | Partial | Manifest generation, app create/update via Manifest APIs, Enterprise Grid app approval/restriction via Admin APIs, broker secret file updates | Configuration token generation/rotation, OAuth install/consent, Socket Mode app-level token handling, non-Enterprise admin policy limits |
| Microsoft Teams | High in managed tenants | Entra app registration, Azure Bot provisioning, messaging endpoint updates, Teams app package build, app catalog upload, app installation via Graph | Admin consent, Teams policies, resource-specific consent, some catalog APIs under Graph `/beta`, public HTTPS endpoint requirement |
| Discord | Partial after app exists | Edit current application properties, register slash commands, configure guild channels/roles after bot invite, send messages | Initial application/bot creation, private server creation, bot token retrieval, OAuth install into server remain portal/client/consent steps |

## Recommended Automation Boundary

Automate platform deployment only through official APIs and tokens:

- Slack: App Manifest APIs, Admin APIs, OAuth, and app configuration tokens.
- Teams: Microsoft Graph, Azure Resource Manager/Bicep/Terraform, Azure CLI,
  Microsoft Graph SDK, or Microsoft 365 CLI.
- Discord: Bot tokens, OAuth2, Gateway, HTTP Interactions, Application API, and
  Application Command APIs.

Avoid automation that controls a human admin's browser session, stores raw
passwords, bypasses MFA, or uses unsupported "self-bot" behavior.

## Broker Deployment Pattern

For all platforms:

1. Generate a platform manifest or configuration from version-controlled
   templates.
2. Apply platform-side resources with official APIs where possible.
3. Store issued tokens/secrets in the target secret store.
4. Set `social_collaboration.implementation` to the selected adapter.
5. Start with `--verify-startup social`.
6. Run read-only command smoke tests before enabling operational commands.

## Platform-Specific Runbooks

- Slack: [Slack Configuration Guide](./slack_configuration.md)
- Teams: [Microsoft Teams Integration Blueprint](./microsoft_teams_integration.md)
- Discord: [Discord Integration Playbook](./discord_integration_playbook.md)
