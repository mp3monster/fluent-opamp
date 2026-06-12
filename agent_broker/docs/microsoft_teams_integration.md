# Microsoft Teams Integration Blueprint

This document describes how to implement, configure, and deploy a Microsoft
Teams alternative to the current Slack integration in `opamp_broker`.

## Current Status

The broker already supports a social collaboration abstraction layer:

1. Adapter interface: `opamp_broker/social_collaboration/base.py`
2. Adapter factory: `opamp_broker/social_collaboration/factory.py`
3. Current implementation: Slack adapter in `opamp_broker/social_collaboration/adapters/slack.py`
4. Startup selection in `opamp_broker/broker_app.py` via:
   - `--social-collaboration`
   - `social_collaboration.implementation` config
   - default `slack`

This means Teams can be added as a new adapter without changing graph, session,
planner, or MCP logic.

## Objective

Provide feature parity for broker chat workflows in Teams:

1. Receive prompts in channel, group chat, and personal chat contexts.
2. Route prompts through the existing graph + MCP path.
3. Send normal responses, idle-timeout messages, and shutdown messages.
4. Preserve existing session semantics using Teams conversation references.

## Implementation Work

### 1) Add Teams adapter module

Create a new module, for example:

- `opamp_broker/social_collaboration/adapters/teams.py`

Implement the same contract used by Slack:

1. `register_handlers(...)`
2. `start()`
3. `post_message(...)`
4. `verify_connection()`

Recommended implementation approach:

- Use Bot Framework activity handling for inbound Teams messages.
- Keep Teams activity parsing and Teams-specific response mechanics inside the
  adapter.
- Normalize into the existing broker graph input shape before invoking the
  compiled graph.
- Store Teams conversation references for proactive idle/shutdown messages.

### 2) Extend factory selection

Update `opamp_broker/social_collaboration/factory.py`:

1. Add `teams` to supported implementations.
2. Instantiate a Teams adapter when `implementation == "teams"`.
3. Keep `slack` behavior unchanged.

### 3) Add Teams runtime config

Extend broker config defaults and example config:

```json
{
  "social_collaboration": {
    "implementation": "teams"
  },
  "teams": {
    "endpoint_path": "/api/messages",
    "personal_scope_enabled": true,
    "team_scope_enabled": true,
    "group_chat_scope_enabled": true,
    "command_name": "opamp"
  }
}
```

Suggested config keys:

1. `teams.endpoint_path`
2. `teams.command_name`
3. `teams.personal_scope_enabled`
4. `teams.team_scope_enabled`
5. `teams.group_chat_scope_enabled`
6. optional tenant/cloud overrides for sovereign cloud deployments

### 4) Add Teams credential/env handling

Define and validate required credentials for Teams runtime.

Typical values:

1. `TEAMS_APP_ID`
2. `TEAMS_APP_PASSWORD` or certificate/managed-identity equivalent
3. `TEAMS_TENANT_ID`
4. `TEAMS_BOT_ID` when it differs from the app ID
5. `TEAMS_SERVICE_URL` only when a library requires an override

Keep credentials in `.env` or the deployment secret store, not in broker JSON.

## Teams Setup Information

### 1) Prepare hosting

Teams bot traffic normally reaches the broker through an internet-reachable
HTTPS callback endpoint.

1. Deploy the broker behind HTTPS.
2. Expose the Teams activity endpoint, for example:
   `https://broker.example.com/api/messages`
3. Ensure the endpoint can validate Bot Framework authentication.
4. For local development, use a tunnel and update the bot messaging endpoint to
   the tunnel URL plus `/api/messages`.

### 2) Create identity and bot resources

1. Create or select a Microsoft Entra application registration.
2. Create a client secret, certificate, or managed identity path for the bot.
3. Create an Azure Bot resource or equivalent Bot Framework registration.
4. Configure the bot messaging endpoint to the broker HTTPS endpoint.
5. Add Teams as a supported channel if the bot resource requires explicit
   channel configuration.
6. Record app ID, tenant ID, bot ID, and secret/certificate references.

### 3) Build the Teams app package

Create a Teams app package ZIP containing:

1. `manifest.json`
2. color icon
3. outline icon

The manifest should include:

- bot ID
- scopes: `personal`, `team`, and/or `groupchat`
- command list for the broker entry point
- valid domains for the broker host
- optional `webApplicationInfo` if SSO is added later

### 4) Publish or side-load the app

Development options:

1. Side-load the Teams app package where tenant policy allows it.
2. Upload the app through the Teams Developer Portal.
3. Upload to the organization's Teams app catalog for controlled deployment.

Production options:

1. Publish the package to the organization app catalog.
2. Apply Teams app permission/setup policies.
3. Install the app into target users, chats, teams, or meetings.
4. Verify the bot can receive messages and send replies.

### 5) Configure and start the broker

1. Add Teams environment variables to the runtime secret store.
2. Set `social_collaboration.implementation` to `teams`, or start with:
   `python -m opamp_broker.broker_app --social-collaboration teams`
3. Run a connectivity check:
   `python -m opamp_broker.broker_app --social-collaboration teams --verify-startup social`
4. Send a read-only prompt to the bot in a test chat or team channel.
5. Verify normal replies, idle timeout, shutdown notices, and restart behavior.

## Teams Transport and Hosting Requirements

Unlike Slack Socket Mode, Teams bots usually rely on HTTPS callback delivery.

Expected work:

1. Expose an HTTPS endpoint for Bot Framework activities.
2. Validate/authenticate inbound activity requests.
3. Normalize activity payloads into broker session keys.
4. Preserve conversation reference metadata for proactive messages.

Operational implications:

1. Deployment model needs a public or tenant-reachable HTTPS endpoint.
2. Local development usually requires a tunnel and callback registration.
3. Bot endpoint changes must be reflected in Azure Bot/Bot Framework settings.

## Message and Session Mapping

Normalize Teams payloads into broker context fields:

1. `team_id`: Teams tenant ID or team ID, depending on scope.
2. `channel_id`: conversation ID or channel ID.
3. `thread_ts`: Teams reply chain ID, activity ID, or stable conversation key.
4. `user_id`: Teams sender identity identifier.
5. `text`: cleaned text with bot mention artifacts removed.

For proactive broker messages, persist the Teams conversation reference so
`post_message(...)` can target the original context.

## Command/UX Parity Decisions

Decide and document expected Teams UX behavior before implementation:

1. Whether the first release uses message commands, mention handling, or a
   simple command parser inside bot messages.
2. Mention handling behavior in channels.
3. Personal chat behavior and defaults.
4. Response visibility model because Slack ephemeral behavior has no exact
   Teams equivalent.
5. Whether Adaptive Cards are required for richer tool output later.

## Testing Plan

Add tests in these areas:

1. Unit tests for Teams activity normalization.
2. Unit tests for Teams adapter `post_message(...)` behavior.
3. Factory tests for `teams` selection and unsupported values.
4. Broker startup tests for adapter selection precedence (CLI > config > default).
5. Integration tests using representative Teams activity fixtures.

Regression requirement:

1. Existing Slack adapter tests must remain green.

## Deployment Automation Feasibility

Teams deployment can be highly automated in a Microsoft 365 tenant, but only
with the correct Graph, Azure, Teams, and admin-consent permissions.

Can be automated:

- Entra application registration and credential creation with Graph or Azure
  automation.
- Azure Bot/Bot Framework resource provisioning with Azure automation.
- Messaging endpoint updates through Azure/Bot resource automation.
- Teams app package generation from a manifest template.
- Organization app catalog publishing through Microsoft Graph.
- Installing a catalog app into chats, users, teams, or meetings through
  Microsoft Graph installation APIs.

Likely requires tenant-admin approval or policy work:

- Admin consent for Graph application/delegated permissions.
- App catalog publishing approval when submitted by non-admin users.
- Teams app permission and setup policies.
- Resource-specific consent when the app declares resource-specific permissions.

Do not automate by scripting an admin user's Teams UI login. Use Microsoft
Graph, Azure Resource Manager/Bicep/Terraform, Azure CLI, Microsoft Graph SDK,
or Microsoft 365 CLI with explicit admin consent.

## Documentation and Scripts

Add Teams-specific onboarding assets when implementation starts:

1. `docs/teams_configuration.md`
2. optional Teams app manifest template
3. optional package/build script for the Teams app ZIP
4. optional deployment script for Graph/Azure automation

Also update existing docs to reference that multiple social collaboration
implementations are supported and Slack remains the default.

## Risks and Open Questions

1. Teams hosting/auth model is different from Slack Socket Mode and may change
   deployment topology.
2. Command UX in Teams is not 1:1 with Slack slash commands.
3. Multi-tenant identity and Teams app policies may add complexity.
4. Proactive messaging depends on reliable conversation reference storage.
5. Some Graph Teams app catalog APIs are still exposed under `/beta`, so avoid
   depending on those beta APIs without an explicit production risk acceptance.

## Supporting References

- Teams app upload and publishing:
  https://learn.microsoft.com/en-us/microsoftteams/platform/concepts/deploy-and-publish/apps-upload
- Microsoft Graph `teamsApp` publish API:
  https://learn.microsoft.com/en-us/graph/api/teamsapp-publish
- Microsoft Graph add Teams app to chat:
  https://learn.microsoft.com/en-us/graph/api/chat-post-installedapps
- Teams bot authentication and Azure Bot setup:
  https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/authentication/add-authentication
- Teams bot SSO and messaging endpoint configuration:
  https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/authentication/bot-sso-register-aad
