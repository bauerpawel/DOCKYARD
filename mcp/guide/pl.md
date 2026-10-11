# Dockyard — serwer MCP z katalogiem aplikacji

Katalog Dockyard opisuje gotowe aplikacje Dockera (te same, które Portainer bierze z `templates.json`). Po dodaniu serwera MCP agent potrafi znaleźć aplikację i wdrożyć ją u Ciebie: w lokalnym Dockerze albo w Twoim Portainerze.

Serwer katalogu nie łączy się z Twoją siecią. Adres Portainera i klucz API zostają na Twoim komputerze. Agent, który ma ten serwer MCP, sam odzywa się do Dockera i do Portainera.

Adres serwera:

```text
https://YOUR-DOMAIN/mcp
```

## Claude Code

W terminalu, raz dla wszystkich projektów:

```bash
claude mcp add --scope user --transport http dockyard https://YOUR-DOMAIN/mcp
```

Albo plik `.mcp.json` w katalogu projektu. Pole `type` jest wymagane:

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

Nową sesję Claude Code otwórz po zapisaniu pliku. Sprawdzenie: `claude mcp list`.

## Claude Desktop

Gdy w ustawieniach jest dodawanie własnego złącza (Connectors), wklej tam adres `https://YOUR-DOMAIN/mcp`.

Gdy Twoja wersja Desktop uruchamia tylko lokalny program, w pliku konfiguracyjnym dopisz serwer przez `mcp-remote`. Potrzebny jest Node.js.

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

Zapisz plik i uruchom Claude Desktop ponownie.

## Codex

```bash
codex mcp add dockyard --url https://YOUR-DOMAIN/mcp
```

Plik jest wspólny dla CLI i rozszerzenia:

- Windows: `%USERPROFILE%\.codex\config.toml`
- macOS i Linux: `~/.codex/config.toml`

```toml
[mcp_servers.dockyard]
url = "https://YOUR-DOMAIN/mcp"
```

W sesji Codex polecenie `/mcp` pokazuje serwer `dockyard`. Po ręcznej edycji pliku uruchom Codex ponownie.

## Grok

```bash
grok mcp add --transport http dockyard https://YOUR-DOMAIN/mcp
```

To samo w pliku konfiguracyjnym:

- Windows: `%USERPROFILE%\.grok\config.toml`
- macOS i Linux: `~/.grok/config.toml`

```toml
[mcp_servers.dockyard]
url = "https://YOUR-DOMAIN/mcp"
```

Sprawdzenie: `grok mcp list`. Nowa sesja Grok po zmianie pliku.

## Gemini CLI

```bash
gemini mcp add --transport http dockyard https://YOUR-DOMAIN/mcp
```

To samo w pliku `~/.gemini/settings.json`:

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

Plik `~/.cursor/mcp.json` (wszystkie projekty) albo `.cursor/mcp.json` w katalogu projektu:

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

Plik `.vscode/mcp.json` w katalogu projektu albo konfiguracja użytkownika otwierana poleceniem **MCP: Open User Configuration**:

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

## Inne klienty MCP

Każdy klient, który obsługuje zdalne serwery przez Streamable HTTP, przyjmuje adres serwera podany na górze. Klient, który uruchamia tylko lokalne programy, łączy się przez `mcp-remote`, tak jak w pliku Claude Desktop powyżej.

## Co zostaje u Ciebie

Do konfiguracji MCP wpisujesz tylko adres katalogu. Nie dopisuj tam klucza Portainera.

Dane Portainera trzymaj w środowisku, z którego startuje agent, albo podaj je agentowi w rozmowie, gdy o nie poprosi:

```text
PORTAINER_URL=https://192.168.1.10:9443
PORTAINER_API_KEY=ptr_...
PORTAINER_ENDPOINT_ID=1
```

Klucz: w Portainerze **My account → Access tokens**. Numer środowiska to `Id` z listy środowisk. Jest też widoczny w adresie po otwarciu środowiska. Agent może odczytać listę sam, wywołaniem API z Twojego komputera, gdy dostanie adres i klucz.

Do celu Docker agent używa polecenia `docker` na tym komputerze, na którym sam działa. Docker Desktop albo silnik Dockera musi być uruchomiony.

## Jak prosić agenta

```text
Wyszukaj w Dockyard n8n i postaw go w Dockerze na tym komputerze.
```

```text
Postaw AdGuard w moim Portainerze.
```

Agent pokaże plan (porty, wolumeny, hasła do zmiany) i ruszy dopiero po Twojej zgodzie. Hasła domyślne z szablonu, takie jak `admin`, trzeba zamienić na własne. Przy kontenerze privileged agent ma zapytać osobno.
