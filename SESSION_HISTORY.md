# Historia sesji roboczych

Plik pozwala odtworzyć, co już zrobiono, i kontynuować pracę.

## 2026-11-02 — przegląd PR #21 (symfony/yaml 7.4.21 → 7.4.22) i audyt zależności

**Zlecenie:** sprawdzić PR, zweryfikować inne biblioteki i CVE, zaktualizować w razie potrzeby.

**PR #21** (Dependabot, `dependabot/composer/mcp/symfony/yaml-7.4.22`) zmienia tylko
`mcp/composer.lock`. `deploy/refresh.php` odrzuca wydanie, w którym `mcp/vendor`
nie zgadza się z lockiem, więc sam PR nie nadaje się do merge'a.

**Zrobione (gałąź `claude/exciting-allen-mr426k`):**
- `composer update symfony/yaml --working-dir=mcp --no-dev` → 7.4.22 (commit `1ed6afa`),
  zaktualizowany `mcp/vendor/`. `composer.lock` jest bajtowo identyczny z lockiem z PR #21.
- Proxy blokuje zipballe GitHuba, więc pakiet zainstalowano ze źródła i ręcznie
  doprowadzono do postaci dist: usunięto pliki `export-ignore` (Tests, phpunit.xml.dist, .git*),
  `installation-source` = `dist`, przywrócono `plugin-api-version` 2.9.0 i tryby plików.
- Zmiany w 7.4.22 to poprawki błędów (Dumper: literal block; Inline: klucze `!php/const|enum`),
  bez advisory bezpieczeństwa.

**Audyt:**
- `composer audit`: brak podatności; pozostałe pakiety (deprecation-contracts 3.7.1,
  polyfill-ctype 1.37.0) aktualne.
- `pip-audit` na `requirements/build.txt` i `dev.txt`: brak podatności.
- `uv pip compile ... --upgrade` (z polityką `--exclude-newer P7D`): brak nowszych wersji.

**Weryfikacja:** `pytest` 506 passed (z testami PHP), `python -m gallery build` i `validate` OK.

**Dalej:** po merge'u tej gałęzi zamknąć PR #21 jako zastąpiony (albo wypchnąć te same
zmiany vendor na gałąź Dependabota i zmergować PR #21).
