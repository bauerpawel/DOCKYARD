# Dockyard — MCP-Server für den App-Katalog

Der Dockyard-Katalog beschreibt fertige Docker-Apps (dieselben, die Portainer aus `templates.json` liest). Sobald du diesen MCP-Server hinzugefügt hast, kann dein Agent eine App finden und sie bei dir bereitstellen: im lokalen Docker oder in deinem eigenen Portainer.

Der Katalogserver verbindet sich nicht mit deinem Netzwerk. Deine Portainer-Adresse und dein API-Schlüssel bleiben auf deinem Rechner. Der Agent, der diesen MCP-Server nutzt, spricht selbst mit Docker und mit Portainer.

Serveradresse:

```text
https://YOUR-DOMAIN/mcp
```

## Claude Code

Im Terminal, einmal für alle Projekte:

```bash
claude mcp add --scope user --transport http dockyard https://YOUR-DOMAIN/mcp
```

Oder eine Datei `.mcp.json` im Projektverzeichnis. Das Feld `type` ist erforderlich:

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

Öffne nach dem Speichern der Datei eine neue Claude-Code-Sitzung. Zur Kontrolle: `claude mcp list`.

## Claude Desktop

Wenn sich in den Einstellungen ein eigener Connector (Connectors) hinzufügen lässt, füge dort die Adresse `https://YOUR-DOMAIN/mcp` ein.

Wenn deine Desktop-Version nur lokale Programme startet, trage den Server in der Konfigurationsdatei über `mcp-remote` ein. Node.js wird benötigt.

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

Speichere die Datei und starte Claude Desktop neu.

## Codex

```bash
codex mcp add dockyard --url https://YOUR-DOMAIN/mcp
```

Die Datei gilt für die CLI und die Erweiterung gemeinsam:

- Windows: `%USERPROFILE%\.codex\config.toml`
- macOS und Linux: `~/.codex/config.toml`

```toml
[mcp_servers.dockyard]
url = "https://YOUR-DOMAIN/mcp"
```

In einer Codex-Sitzung zeigt der Befehl `/mcp` den Server `dockyard` an. Starte Codex neu, wenn du die Datei von Hand bearbeitet hast.

## Grok

```bash
grok mcp add --transport http dockyard https://YOUR-DOMAIN/mcp
```

Dasselbe in der Konfigurationsdatei:

- Windows: `%USERPROFILE%\.grok\config.toml`
- macOS und Linux: `~/.grok/config.toml`

```toml
[mcp_servers.dockyard]
url = "https://YOUR-DOMAIN/mcp"
```

Zur Kontrolle: `grok mcp list`. Öffne nach einer Änderung der Datei eine neue Grok-Sitzung.

## Gemini CLI

```bash
gemini mcp add --transport http dockyard https://YOUR-DOMAIN/mcp
```

Dasselbe in der Datei `~/.gemini/settings.json`:

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

Die Datei `~/.cursor/mcp.json` (alle Projekte) oder `.cursor/mcp.json` im Projektverzeichnis:

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

Die Datei `.vscode/mcp.json` im Projektverzeichnis oder die Benutzerkonfiguration, die der Befehl **MCP: Open User Configuration** öffnet:

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

## Andere MCP-Clients

Jeder Client, der entfernte Server über Streamable HTTP unterstützt, nimmt die oben angegebene Serveradresse. Ein Client, der nur lokale Programme startet, verbindet sich über `mcp-remote`, so wie in der Claude-Desktop-Datei oben.

## Was bei dir bleibt

In die MCP-Konfiguration gehört nur die Adresse des Katalogs. Trage dort keinen Portainer-Schlüssel ein.

Bewahre die Portainer-Daten in der Umgebung auf, aus der der Agent startet, oder gib sie dem Agenten im Gespräch, wenn er danach fragt:

```text
PORTAINER_URL=https://192.168.1.10:9443
PORTAINER_API_KEY=ptr_...
PORTAINER_ENDPOINT_ID=1
```

Der Schlüssel: in Portainer unter **My account → Access tokens**. Die Nummer der Umgebung ist die `Id` aus der Liste der Umgebungen. Sie steht auch in der Adresse, nachdem du die Umgebung geöffnet hast. Der Agent kann die Liste selbst lesen, mit einem API-Aufruf von deinem Rechner aus, sobald er Adresse und Schlüssel hat.

Für das Ziel Docker verwendet der Agent den Befehl `docker` auf dem Rechner, auf dem er selbst läuft. Docker Desktop oder die Docker-Engine muss laufen.

## So bittest du den Agenten

```text
Suche n8n in Dockyard und starte es in Docker auf diesem Rechner.
```

```text
Stelle AdGuard in meinem Portainer bereit.
```

Der Agent zeigt einen Plan (Ports, Volumes, zu ändernde Passwörter) und legt erst nach deiner Zustimmung los. Standardpasswörter aus der Vorlage, etwa `admin`, müssen durch eigene ersetzt werden. Bei einem privilegierten Container soll der Agent gesondert nachfragen.
