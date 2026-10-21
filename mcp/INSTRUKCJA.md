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
/var/www/dockyard/stacks.lock.json  opcjonalnie, zapas pinów stosów gdy CDN nie odpowiada
/var/www/dockyard/templates.json    opcjonalnie, zapas gdy CDN nie odpowiada
```

Wgrywaj cały katalog `mcp/`, łącznie z `vendor/` i `guide/`. Parser YAML Symfony jest już dołączony;
Composer nie jest potrzebny na serwerze. Aktualizacja zależności u programisty:
`composer update --working-dir=mcp --no-dev`, potem commit `composer.lock` i `vendor/` razem.

Lokalny plik stosu jest używany tylko dla repozytorium z `repository.json` (lub nadpisania
`DOCKYARD_REPO_URL`) i jego opublikowanego main/HEAD. Przy kopii tylko `mcp/` bez lokalnych stosów
pliki schodzą z GitHuba.

Pliki stosów z cudzych repozytoriów są przypięte w `stacks.lock.json`: commit i SHA-256 przejrzanej
wersji. Serwer pobiera je tylko z tego commitu i odrzuca treść o innym skrócie, więc zmiana w cudzym
repozytorium nie trafi do planu, dopóki opiekun katalogu jej nie przejrzy i nie przypnie
(`python -m gallery pin-stacks --update`). Stos bez pinu blokuje plan. Piny przychodzą z tego samego
źródła co feed (CDN, a przy awarii plik obok `templates.json`).

Plan sprawdza YAML Compose, w tym kotwice i skrócone mapy, według listy dozwolonych kluczy i ścieżek.
Bez zgody przechodzą: wolumeny nazwane i anonimowe, ścieżki względne w katalogu projektu, katalogi danych
(`/portainer`, `/srv`, `/mnt`, `/media`, `/data`, `/volume1`, `/opt/mediadepot`) i `/etc/localtime`
oraz `/etc/timezone` tylko do odczytu. Wszystko inne wymaga osobnej zgody przez `allow_privileged`:
`privileged`, socket silnika kontenerów, przestrzenie hosta, urządzenia, capabilities, inne ścieżki
hosta, `build`, zasoby `external`, `include`/`extends` oraz klucze, których serwer nie zna.
Niepoprawny YAML lub brak parsera blokuje plan także po zgodzie.

Docker Compose podstawia zmienne najpierw ze środowiska procesu, a dopiero potem z `.env`. Stos, który
podstawia `PORTAINER_URL`, `PORTAINER_API_KEY` albo `PORTAINER_ENDPOINT_ID`, jest zablokowany także po
zgodzie. Inne zmienne, których plan nie ustawia, wymagają zgody, chyba że agent poda je w `env` albo
`local_secrets`.

### Feed

Feed przychodzi z oficjalnego CDN, `https://cdn.jsdelivr.net/gh/bauerpawel/DOCKYARD@main/templates.json`. Na serwerze wystarczy więc sam katalog `mcp/`, bez kopii `templates.json`.

- Pobrany feed leży w `mcp/cache/` przez 15 minut. Katalog `mcp/cache/` musi być zapisywalny dla serwera WWW, inaczej feed schodzi z CDN przy każdym żądaniu.
- Gdy CDN nie odpowiada albo zwraca coś innego niż feed, serwer używa ostatniej pobranej kopii i próbuje ponownie po 15 minutach. Bez takiej kopii bierze lokalny `templates.json`, jeśli jest: obok `index.php` albo katalog wyżej.
- jsDelivr trzyma `@main` do 12 godzin, ale workflowy repozytorium czyszczą jego cache po każdej przebudowie feedu.
- `stacks.lock.json` schodzi z tego samego katalogu na CDN co feed i ma ten sam cache oraz zapas.

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
