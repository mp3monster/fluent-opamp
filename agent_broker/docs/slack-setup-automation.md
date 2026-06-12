# Slack seup automation

## Deployment Automation Feasibility

Slack deployment is partially automatable.

Can be automated:

1. Generate the broker's Slack manifest from local defaults.
2. Validate, create, update, export, or delete Slack apps through Slack App
   Manifest APIs when an app configuration token is available.
3. In Enterprise Grid, approve or restrict app installation requests through
   Slack Admin APIs with an admin/owner-approved app that has `admin.apps:write`.
4. Write broker runtime secrets into `.env` or a deployment secret store once
   tokens are provided through an approved process.

Usually remains manual or consent-driven:

1. Generating an app configuration token. Slack configuration tokens are
   user/workspace scoped and expire, so automation must handle rotation.
2. OAuth installation and granting app scopes in non-Enterprise or
   policy-controlled workspaces.
3. Creating and retrieving the app-level token used by Socket Mode.
4. Final admin approval where the workspace requires review and no Enterprise
   app-management automation has been installed.

Do not automate a Slack admin's browser login or password flow. Use Slack App
Manifest APIs, Slack Admin APIs, Slack OAuth, and short-lived configuration
tokens where the workspace policy allows it.

## Implementation Selection Notes

The broker selects the social collaboration implementation in this order:

1. `--social-collaboration` command-line parameter
2. `social_collaboration.implementation` in broker config
3. Default `slack`

For full broker CLI option details (`--config-path`, `--social-collaboration`,
`--verify-startup`), see:
- [Broker Startup and Shutdown](./broker_startup_and_shutdown.md)

For details on when to use `.env` versus `broker.json`, see:
- [Broker Startup and Shutdown](./broker_startup_and_shutdown.md)

## Supporting References

- Slack app manifests:
  https://api.slack.com/reference/manifests
- Slack App Manifest APIs and configuration tokens:
  https://docs.slack.dev/app-manifests/configuring-apps-with-app-manifests/
- Slack Admin app approval API:
  https://docs.slack.dev/reference/methods/admin.apps.approve/
- Slack app management:
  https://api.slack.com/apps
- Slack token types:
  https://api.slack.com/authentication/token-types
- Slack Socket Mode:
  https://api.slack.com/apis/connections/socket
- Slack slash commands:
  https://api.slack.com/interactivity/slash-commands
- Project-specific baseline:
  [README.md](../README.md)
