# Dockyard — serwer MCP z katalogiem aplikacji

Katalog Dockyard opisuje gotowe aplikacje Dockera (te same, które Portainer bierze z `templates.json`). Po dodaniu serwera MCP agent potrafi znaleźć aplikację i wdrożyć ją u Ciebie: w lokalnym Dockerze albo w Twoim Portainerze.

Serwer katalogu nie łączy się z Twoją siecią. Adres Portainera i klucz API zostają na Twoim komputerze. Agent, który ma ten serwer MCP, sam odzywa się do Dockera i do Portainera.

Adres serwera (bez `.php` i bez nazwy pliku):

```text
https://TWOJA-DOMENA/mcp
```

Podmień `TWOJA-DOMENA` na adres, który dostałeś od osoby prowadzącej katalog. Na końcu nie dopisuj `index.php` ani `mcp.php`.

## Claude Code

W terminalu, raz dla wszystkich projektów:

```bash
claude mcp add --scope user --transport http dockyard https://TWOJA-DOMENA/mcp
```

Albo plik `.mcp.json` w katalogu projektu. Pole `type` jest wymagane:

```json
{
  "mcpServers": {
    "dockyard": {
      "type": "http",
      "url": "https://TWOJA-DOMENA/mcp"
    }
  }
}
```

Nową sesję Claude Code otwórz po zapisaniu pliku. Sprawdzenie: `claude mcp list`.

## Claude Desktop

Gdy w ustawieniach jest dodawanie własnego złącza (Connectors), wklej tam adres `https://TWOJA-DOMENA/mcp`.

Gdy Twoja wersja Desktop uruchamia tylko lokalny program, w pliku konfiguracyjnym dopisz serwer przez `mcp-remote`. Potrzebny jest Node.js.

- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "dockyard": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://TWOJA-DOMENA/mcp"]
    }
  }
}
```

Zapisz plik i uruchom Claude Desktop ponownie.

## Grok

```bash
grok mcp add --transport http dockyard https://TWOJA-DOMENA/mcp
```

To samo w pliku konfiguracyjnym:

- Windows: `%USERPROFILE%\.grok\config.toml`
- macOS i Linux: `~/.grok/config.toml`

```toml
[mcp_servers.dockyard]
url = "https://TWOJA-DOMENA/mcp"
```

Sprawdzenie: `grok mcp list`. Nowa sesja Grok po zmianie pliku.

## Codex

```bash
codex mcp add dockyard --url https://TWOJA-DOMENA/mcp
```

Plik jest wspólny dla CLI i rozszerzenia:

- Windows: `%USERPROFILE%\.codex\config.toml`
- macOS i Linux: `~/.codex/config.toml`

```toml
[mcp_servers.dockyard]
url = "https://TWOJA-DOMENA/mcp"
```

W sesji Codex polecenie `/mcp` pokazuje serwer `dockyard`. Po ręcznej edycji pliku uruchom Codex ponownie.

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

Gdy POST na adres katalogu kończy się przekierowaniem, osoba prowadząca serwer musi poprawić Apache. Do agenta wklejasz ten wariant adresu (ze slashem albo bez), który na POST odpowiada kodem 200.

---

## Wdrożenie katalogu na Apache

Ta część jest dla osoby, która publikuje serwer. Użytkownikom końcowym wystarczy część powyżej.

PHP 8.1 lub nowszy, Apache 2.4 z modułami `rewrite` i `alias`, w `php.ini` włączone `allow_url_fopen` (publiczne pliki Compose są dociągane z GitHuba).

Na dysku serwera:

```text
/var/www/dockyard/templates.json    wygenerowany feed
/var/www/dockyard/stacks/           opcjonalnie, lokalne Compose z tego repo
/var/www/dockyard/mcp/              ten katalog
```

`templates.json` może też leżeć w `mcp/templates.json`. Skrypt szuka najpierw zmiennej `DOCKYARD_TEMPLATES`, potem pliku obok siebie, potem katalog wyżej.

Feed może też przychodzić z CDN, bez kopiowania `templates.json` na serwer. Przydaje się na hostingu bez crona, gdzie wgrywasz tylko katalog `mcp/`. Ustaw zmienną `DOCKYARD_TEMPLATES_URL` w `apache.conf` albo w `.htaccess`:

```apache
SetEnv DOCKYARD_TEMPLATES_URL https://cdn.jsdelivr.net/gh/bauerpawel/DOCKYARD@main/templates.json
```

- Adres musi być `https` na `cdn.jsdelivr.net` albo `raw.githubusercontent.com`.
- Pobrany feed leży w `mcp/cache/` przez 15 minut. Katalog `mcp/cache/` musi być zapisywalny dla serwera WWW, inaczej feed schodzi z CDN przy każdym żądaniu.
- Gdy CDN nie odpowiada albo zwraca coś innego niż feed, serwer używa ostatniej pobranej kopii i próbuje ponownie po 15 minutach. Bez takiej kopii bierze lokalny `templates.json`, jeśli jest.
- jsDelivr trzyma `@main` do 12 godzin, ale workflowy repozytorium czyszczą jego cache po każdej przebudowie feedu.

W `mcp/apache.conf` popraw obie ścieżki `/var/www/dockyard/mcp` i dołącz plik w wirtualnym hoście:

```apache
Include /var/www/dockyard/mcp/apache.conf
```

`AllowOverride None` w tym fragmencie jest celowe: reguły są w pliku vhosta, a `.htaccess` zostaje na hosting, na którym nie da się edytować vhosta. Na takim hostingu adresem bywa `https://TWOJA-DOMENA/mcp/` ze slashem na końcu. Do agentów podajesz ten z nich, który na POST zwraca 200.

Sprawdzenie:

```bash
curl -s -D- -o /dev/null -X POST https://TWOJA-DOMENA/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"ping\"}"
```

Oczekiwany status to 200 i ciało `{"jsonrpc":"2.0","id":1,"result":{}}`.

Lokalnie, z katalogu repozytorium, logika narzędzi bez Apache:

```bash
php mcp/index.php --self-test
```
