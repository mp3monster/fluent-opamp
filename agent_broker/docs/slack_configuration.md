# Slack Configuration Guide

This guide documents the fastest path to configure Slack for `opamp_broker`,
including what is automated and what still requires manual Slack UI work.

Slack is the default social collaboration implementation.
If no explicit implementation is selected, the broker uses Slack.

## What Is Automated

Run one of these scripts:

- Linux/macOS: `./scripts/configure_slack.sh`
- Windows PowerShell: `.\scripts\configure_slack.ps1`

The script will:

1. Create `agent_broker/.env` from `.env.example` if missing.
2. Generate a Slack app manifest file at `agent_broker/opamp_broker/config/slack_app_manifest.yaml`.
3. Optionally write the three Slack credentials into `.env` if you provide them:
   - `SLACK_BOT_TOKEN`
   - `SLACK_SIGNING_SECRET`
   - `SLACK_APP_TOKEN`
4. Set `BROKER_CONFIG_PATH` in `.env` for this broker.

## What Cannot Be Fully Automated

Slack workspace app creation and token issuance require Slack admin/user actions.

### Manual Steps

1. Open your Slack app management page.
2. Create a new app **from manifest** and paste/upload
   `agent_broker/opamp_broker/config/slack_app_manifest.yaml`.
3. Install the app to your workspace.
4. In Slack app settings, collect:
   - **Bot User OAuth Token** (`xoxb-...`)
   - **Signing Secret**
   - **App-Level Token** (`xapp-...`) with `connections:write`
5. Put those values in `agent_broker/.env`.
   - Easiest: rerun `configure_slack` script with token arguments.
6. Start broker:
   - Preferred: `opamp-cli start broker`
   - If `opamp-cli` is not installed yet: `PYTHONPATH=cli/src python3 -m opamp_cli start broker`
   - Optional explicit selection: `python -m opamp_broker.broker_app --social-collaboration slack`
   - Optional connection check only: `python -m opamp_broker.broker_app --verify-startup social`
