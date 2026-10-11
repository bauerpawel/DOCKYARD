# Dockyard — serwer MCP z katalogiem aplikacji

Katalog Dockyard opisuje gotowe aplikacje Dockera (te same, które Portainer bierze z `templates.json`). Po dodaniu serwera MCP agent potrafi znaleźć aplikację i wdrożyć ją u użytkownika: w lokalnym Dockerze albo w jego Portainerze.

Instrukcja dla użytkowników, czyli jak dodać serwer do Claude, Codex, Grok i innych agentów, leży w katalogu `guide/`: [polski](guide/pl.md), [English](guide/en.md), [Deutsch](guide/de.md), [Français](guide/fr.md).

Serwer pokazuje tę instrukcję w przeglądarce pod swoim adresem, z prawdziwym adresem w miejscu `YOUR-DOMAIN` i w języku przeglądarki. Parametr `?lang=pl` (albo `en`, `de`, `fr`) wybiera język ręcznie. Klienci MCP dostają na `GET` kod 405, tak jak wcześniej.

---

## Wdrożenie katalogu na Apache

Ta część jest dla osoby, która publikuje serwer.

PHP 8.1 lub nowszy, Apache 2.4 z modułami `rewrite` i `alias`, w `php.ini` włączone `allow_url_fopen` (feed i publiczne pliki Compose są dociągane z sieci).

Na dysku serwera:

```text
/var/www/dockyard/mcp/              ten katalog
/var/www/dockyard/repository.json   adres repozytorium zgodny z feedem
/var/www/dockyard/stacks/           opcjonalnie, lokalne Compose z tego repo
/var/www/dockyard/templates.json    opcjonalnie, zapas gdy CDN nie odpowiada
```

Wgrywaj cały katalog `mcp/`, łącznie z `vendor/` i `guide/`. Parser YAML Symfony jest już dołączony;
Composer nie jest potrzebny na serwerze. Aktualizacja zależności u programisty:
`composer update --working-dir=mcp --no-dev`, potem commit `composer.lock` i `vendor/` razem.

Lokalny plik stosu jest używany tylko dla repozytorium z `repository.json` (lub nadpisania
`DOCKYARD_REPO_URL`) i jego opublikowanego main/HEAD. Inne repozytoria oraz inne gałęzie są pobierane
z deklarowanego źródła. Przy kopii tylko `mcp/` bez lokalnych stosów pliki schodzą z GitHuba.

Plan sprawdza YAML Compose, w tym kotwice i skrócone mapy. `privileged`, socket Docker/Podman,
przestrzenie hosta, urządzenia i capabilities wymagają osobnej zgody przez `allow_privileged`.
Pliki `include`/`extends` i dynamiczne źródła wolumenów są oznaczane do dodatkowej oceny.
Niepoprawny YAML lub brak parsera blokuje plan także po zgodzie.

### Feed

Feed przychodzi z oficjalnego CDN, `https://cdn.jsdelivr.net/gh/bauerpawel/DOCKYARD@main/templates.json`. Na serwerze wystarczy więc sam katalog `mcp/`, bez kopii `templates.json`.

- Pobrany feed leży w `mcp/cache/` przez 15 minut. Katalog `mcp/cache/` musi być zapisywalny dla serwera WWW, inaczej feed schodzi z CDN przy każdym żądaniu.
- Gdy CDN nie odpowiada albo zwraca coś innego niż feed, serwer używa ostatniej pobranej kopii i próbuje ponownie po 15 minutach. Bez takiej kopii bierze lokalny `templates.json`, jeśli jest: obok `index.php` albo katalog wyżej.
- jsDelivr trzyma `@main` do 12 godzin, ale workflowy repozytorium czyszczą jego cache po każdej przebudowie feedu.

Inny adres feedu ustawia zmienna `DOCKYARD_TEMPLATES_URL` w `apache.conf` albo w `.htaccess`. Adres musi być `https` na `cdn.jsdelivr.net` albo `raw.githubusercontent.com`:

```apache
SetEnv DOCKYARD_TEMPLATES_URL https://cdn.jsdelivr.net/gh/OWNER/REPO@main/templates.json
```

Zmienna `DOCKYARD_TEMPLATES` ze ścieżką do pliku wyłącza CDN. Serwer czyta wtedy tylko pliki lokalne, zaczynając od wskazanego.

### Apache

W `mcp/apache.conf` popraw obie ścieżki `/var/www/dockyard/mcp` i dołącz plik w wirtualnym hoście:

```apache
Include /var/www/dockyard/mcp/apache.conf
```

`AllowOverride None` w tym fragmencie jest celowe: reguły są w pliku vhosta, a `.htaccess` zostaje na hosting, na którym nie da się edytować vhosta. Oba pliki mają `RewriteOptions AllowNoSlash`, więc adres działa ze slashem na końcu i bez niego.

Sprawdzenie:

```bash
curl -s -D- -o /dev/null -X POST https://TWOJA-DOMENA/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"ping\"}"
```

Oczekiwany status to 200 i ciało `{"jsonrpc":"2.0","id":1,"result":{}}`. Gdy POST kończy się przekierowaniem, klient MCP gubi treść żądania; popraw wtedy konfigurację Apache.

Lokalnie, z katalogu repozytorium, logika narzędzi bez Apache:

```bash
php mcp/index.php --self-test
```
