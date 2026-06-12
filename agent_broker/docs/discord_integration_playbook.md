# Discord Integration Playbook

This playbook describes how to extend the broker's Slack-oriented social
collaboration capabilities to Discord while preserving the existing graph,
planner, MCP, and session-management flow.

## Current Broker Extension Point

The broker already isolates chat-platform concerns behind the social
collaboration abstraction:

1. Contract: `opamp_broker/social_collaboration/base.py`
2. Factory: `opamp_broker/social_collaboration/factory.py`
3. Current implementation: `opamp_broker/social_collaboration/adapters/slack.py`
4. Runtime selector:
   - `python -m opamp_broker.broker_app --social-collaboration <name>`
   - `social_collaboration.implementation` in broker config
   - default `slack`

Discord support should therefore be implemented as a new adapter, not by
forking graph nodes, MCP clients, or planner logic.

## Target User Experience

Discord should provide the same broker capabilities that Slack exposes:

1. Ask OpAMP questions from a controlled collaboration surface.
2. Run slash-command style diagnostics and operational requests.
3. Support direct/private troubleshooting where practical.
4. Preserve thread/session continuity across follow-up messages.
5. Send idle-timeout and shutdown notices to active conversations.

Prefer Discord slash commands and interactions for first implementation. This
avoids depending on broad message-content access and makes command discovery
native to Discord.

## Implementation Steps

### 1) Add a Discord adapter

Create:

- `opamp_broker/social_collaboration/adapters/discord.py`

Implement the existing contract:

1. `register_handlers(session_manager, compiled_graph, config)`
2. `start()`
3. `post_message(channel_id, thread_ts, text)`
4. `verify_connection()`

Recommended implementation choices:

- Use a maintained Discord Python library for Gateway handling, or implement
  Discord HTTP interactions directly if the deployment will expose an HTTPS
  interactions endpoint.
- Keep adapter-specific request parsing in the adapter.
- Pass normalized broker inputs into the existing compiled graph.
- Keep Slack-specific response formatting out of the Discord adapter where
  possible; rename shared formatting later if needed.

### 2) Extend factory selection

Update `opamp_broker/social_collaboration/factory.py`:

1. Add `discord` to `SUPPORTED_SOCIAL_COLLABORATION_IMPLEMENTATIONS`.
2. Instantiate `DiscordSocialCollaborationAdapter.from_environment()` when
   `implementation == "discord"`.
3. Preserve `slack` as the default.

### 3) Add config and environment variables

Extend broker defaults with a `discord` section, for example:

```json
{
  "social_collaboration": {
    "implementation": "discord"
  },
  "discord": {
    "command_name": "opamp",
    "guild_command_registration": true,
    "dm_enabled": true,
    "channel_mentions_enabled": false,
    "transport": "gateway"
  }
}
```

Expected environment variables:

- `DISCORD_BOT_TOKEN`
- `DISCORD_APPLICATION_ID`
- `DISCORD_PUBLIC_KEY` when using HTTP interactions
- `DISCORD_GUILD_ID` for private-server/guild command registration
- `DISCORD_INTERACTIONS_ENDPOINT` when using HTTP interactions

Keep secrets in `.env` or the deployment secret store, not in broker JSON.

### 4) Normalize Discord payloads

Map Discord events/interactions into broker session coordinates:

- `team_id`: Discord `guild_id`
- `channel_id`: Discord channel ID
- `thread_ts`: Discord thread ID, message ID, or interaction conversation key
- `user_id`: Discord user ID
- `text`: slash-command argument text or cleaned message content

For follow-up and proactive messages, persist enough context to reply by:

- interaction follow-up webhook/token for short-lived replies
- channel/thread message send for longer-lived session notices
- original channel ID plus thread/message ID for idle and shutdown messages

### 5) Register Discord commands

Register a Discord slash command equivalent to the Slack slash command:

- recommended command: `/opamp`
- guild-scoped commands for private server rollout and fast iteration
- global commands only after the UX is stable

The command should accept either:

- a single free-text `request` argument, or
- subcommands that mirror broker capabilities once the command grammar is
  stable.

### 6) Add tests

Add tests for:

1. Discord slash-command payload normalization.
2. Discord DM/channel event normalization if Gateway events are supported.
3. `post_message(...)` behavior for channel and thread replies.
4. Factory selection for `discord`.
5. Startup precedence: CLI value, config value, default.
6. Regression tests ensuring Slack behavior stays unchanged.

## Private Discord Server Setup

Use a private Discord server, also called a guild, for development and initial
deployment.

### Server creation

1. Create a Discord server from the Discord client.
2. Give it a clear name, for example `OpAMP Broker Lab`.
3. Disable broad public discovery/invites unless explicitly needed.
4. Create roles:
   - `opamp-admins`
   - `opamp-operators`
   - `opamp-observers`
5. Restrict `@everyone` from posting in broker channels.
6. Create channels:
   - `#opamp-broker` for normal broker use
   - `#opamp-incidents` for operational workflows
   - `#opamp-dev` for adapter testing
7. Grant the broker bot only the channel permissions it needs.

### Discord application and bot

1. Create a Discord application in the Developer Portal.
2. Add a bot user to the application and capture the bot token.
3. Configure installation contexts and install link settings.
4. Use scopes:
   - `bot`
   - `applications.commands`
5. Start with minimal bot permissions:
   - View Channels
   - Send Messages
   - Read Message History
   - Use Slash Commands
6. Invite the bot to the private server using the generated OAuth2 install URL.
7. Register guild-scoped `/opamp` commands for immediate testing.

### Broker deployment

1. Deploy the broker with the Discord adapter dependencies installed.
2. Set the Discord secret variables in the runtime environment.
3. Set `social_collaboration.implementation` to `discord`, or start with:
   `python -m opamp_broker.broker_app --social-collaboration discord`
4. Run startup verification:
   `python -m opamp_broker.broker_app --social-collaboration discord --verify-startup social`
5. Test `/opamp list agents` or another read-only command in `#opamp-dev`.
6. Promote to `#opamp-broker` after command registration, replies, idle notices,
   and shutdown notices are verified.

## Deployment Automation Feasibility

Discord deployment is partially automatable, but not fully automatable from only
an admin user's username/password.

Can be automated after the application and bot exist:

- editing current application properties via Discord's Application API
- registering global or guild application commands via HTTP
- creating channels and roles in a guild where the bot has the required
  permissions
- posting messages and managing command permissions with the correct bot or
  bearer token

Usually remains manual or consent-driven:

- creating the initial Discord application and bot in the Developer Portal
- retrieving and storing the initial bot token
- creating the private server through the Discord client
- authorizing the app into the server through the OAuth2 install flow by a user
  with `MANAGE_GUILD`

Do not automate a normal Discord user account as a "self-bot". Use official bot
tokens, OAuth2, Gateway, and HTTP APIs only.

## Supporting References

- Discord Bots and Companion Apps:
  https://docs.discord.com/developers/platform/bots
- Discord Application Resource:
  https://docs.discord.com/developers/resources/application
- Discord Application Commands:
  https://docs.discord.com/developers/interactions/application-commands
- Discord OAuth2 and Permissions:
  https://docs.discord.com/developers/platform/oauth2-and-permissions
