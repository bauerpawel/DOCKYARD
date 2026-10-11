# Dockyard — MCP server for the app catalog

The Dockyard catalog describes ready-made Docker apps (the same ones Portainer reads from `templates.json`). Once you add this MCP server, your agent can find an app and deploy it for you: in local Docker or in your own Portainer.

The catalog server does not connect to your network. Your Portainer address and API key stay on your computer. The agent that has this MCP server talks to Docker and to Portainer itself.

Server address:

```text
https://YOUR-DOMAIN/mcp
```

## Claude Code

In a terminal, once for all projects:

```bash
claude mcp add --scope user --transport http dockyard https://YOUR-DOMAIN/mcp
```

Or a `.mcp.json` file in the project directory. The `type` field is required:

```json
{
  "mcpServers": {
    "dockyard": {
      "type": "http",
      "url": "https://YOUR-DOMAIN/mcp"
    }
  }
}
```

Open a new Claude Code session after saving the file. To check: `claude mcp list`.

## Claude Desktop

If the settings let you add a custom connector (Connectors), paste the address `https://YOUR-DOMAIN/mcp` there.

If your version of Desktop only starts local programs, add the server through `mcp-remote` in the configuration file. Node.js is required.

- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "dockyard": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://YOUR-DOMAIN/mcp"]
    }
  }
}
```

Save the file and restart Claude Desktop.

## Codex

```bash
codex mcp add dockyard --url https://YOUR-DOMAIN/mcp
```

The file is shared by the CLI and the extension:

- Windows: `%USERPROFILE%\.codex\config.toml`
- macOS and Linux: `~/.codex/config.toml`

```toml
[mcp_servers.dockyard]
url = "https://YOUR-DOMAIN/mcp"
```

In a Codex session the `/mcp` command shows the `dockyard` server. Restart Codex after editing the file by hand.

## Grok

```bash
grok mcp add --transport http dockyard https://YOUR-DOMAIN/mcp
```

The same in the configuration file:

- Windows: `%USERPROFILE%\.grok\config.toml`
- macOS and Linux: `~/.grok/config.toml`

```toml
[mcp_servers.dockyard]
url = "https://YOUR-DOMAIN/mcp"
```

To check: `grok mcp list`. Open a new Grok session after changing the file.

## Gemini CLI

```bash
gemini mcp add --transport http dockyard https://YOUR-DOMAIN/mcp
```

The same in the `~/.gemini/settings.json` file:

```json
{
  "mcpServers": {
    "dockyard": {
      "httpUrl": "https://YOUR-DOMAIN/mcp"
    }
  }
}
```

## Cursor

The `~/.cursor/mcp.json` file (all projects) or `.cursor/mcp.json` in the project directory:

```json
{
  "mcpServers": {
    "dockyard": {
      "url": "https://YOUR-DOMAIN/mcp"
    }
  }
}
```

## VS Code

The `.vscode/mcp.json` file in the project directory, or the user configuration opened with the **MCP: Open User Configuration** command:

```json
{
  "servers": {
    "dockyard": {
      "type": "http",
      "url": "https://YOUR-DOMAIN/mcp"
    }
  }
}
```

## Other MCP clients

Any client that supports remote servers over Streamable HTTP takes the server address shown at the top. A client that only starts local programs connects through `mcp-remote`, the same way as in the Claude Desktop file above.

## What stays with you

Only the catalog address goes into the MCP configuration. Do not put your Portainer key there.

Keep the Portainer details in the environment the agent starts from, or give them to the agent in the conversation when it asks:

```text
PORTAINER_URL=https://192.168.1.10:9443
PORTAINER_API_KEY=ptr_...
PORTAINER_ENDPOINT_ID=1
```

The key: in Portainer, **My account → Access tokens**. The environment number is the `Id` from the list of environments. It is also visible in the address after you open the environment. The agent can read the list itself, with an API call from your computer, once it has the address and the key.

For the Docker target the agent uses the `docker` command on the computer it runs on. Docker Desktop or the Docker engine must be running.

## How to ask the agent

```text
Find n8n in Dockyard and run it in Docker on this computer.
```

```text
Deploy AdGuard in my Portainer.
```

The agent shows a plan (ports, volumes, passwords to change) and starts only after you agree. Default passwords from the template, such as `admin`, have to be replaced with your own. For a privileged container the agent should ask separately.
