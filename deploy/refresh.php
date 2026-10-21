<?php
declare(strict_types=1);

// Odświeża stronę, feed i pliki MCP z publicznego main.
// Cron co 15 minut: php /opt/dockyard/refresh.php
// Trzymaj kopię tego pliku poza document rootem (nie w mcp/ ani html/).
// Archiwum schodzi tylko wtedy, gdy zmieni się commit na main i GitHub Actions zgłosi, że jego testy przeszły.
// Dopóki testy trwają, commit czeka do następnego uruchomienia.
// Commit z nieudanymi testami albo bez kompletu plików jest pomijany do następnego: nic nie zostaje podmienione.
// apache.conf i mcp/cache/ nie są ruszane.

const REFRESH_REPO = 'bauerpawel/DOCKYARD';
const REFRESH_DEST = '/var/www/dockyard';
const REFRESH_MCP_FILES = ['index.php', '.htaccess', 'AGENT.md', 'INSTRUKCJA.md', 'composer.json', 'composer.lock'];
// Job test z .github/workflows/checks.yml; macierz wersji Pythona daje nazwy "test (3.10)", "test (3.14)".
const REFRESH_TEST_CHECK = 'test (';

/**
 * @param null|callable(string, string): array{0: int, 1: string, 2: list<string>} $get
 */
function refresh_main(string $dest, ?callable $get = null): int
{
    $get ??= 'refresh_http_get';
    $repo = REFRESH_REPO;
    $stateFile = $dest . '/.refresh-sha';
    $api = "https://api.github.com/repos/$repo/commits/main";

    if (!is_dir($dest) && !mkdir($dest, 0755, true)) {
        fwrite(STDERR, "Nie można utworzyć $dest\n");
        return 1;
    }
    if (!is_dir($dest . '/mcp') && !mkdir($dest . '/mcp', 0755, true)) {
        fwrite(STDERR, "Nie można utworzyć katalogu mcp\n");
        return 1;
    }

    $lock = fopen($dest . '/.refresh.lock', 'c');
    if ($lock === false || !flock($lock, LOCK_EX | LOCK_NB)) {
        return 0;
    }

    $saved = is_file($stateFile) ? trim((string) file_get_contents($stateFile)) : '';
    $headers = "User-Agent: dockyard-refresh\r\nAccept: application/vnd.github.sha\r\n";
    if (preg_match('/^[0-9a-f]{40}$/', $saved)) {
        $headers .= 'If-None-Match: "' . $saved . "\"\r\n";
    }

    [$status, $body, $headerLines] = $get($api, $headers);
    if ($status === 304) {
        return 0;
    }
    if ($status !== 200) {
        fwrite(STDERR, "GitHub odpowiedział HTTP $status\n");
        return 1;
    }

    $sha = trim($body);
    if (!preg_match('/^[0-9a-f]{40}$/', $sha)) {
        fwrite(STDERR, "Odpowiedź nie zawiera identyfikatora commita\n");
        return 1;
    }
    if ($sha === $saved) {
        return 0;
    }

    $tested = refresh_tests_passed($sha, $get);
    if ($tested === null) {
        return 0;
    }
    if ($tested === false) {
        file_put_contents($stateFile, $sha . "\n");
        fwrite(STDERR, "Testy commita $sha nie przeszły. Nic nie podmieniono, czekam na następny commit.\n");
        return 1;
    }

    $zip = $dest . '/.refresh-src.zip';
    $unpack = $dest . '/.refresh-src';
    [$zipStatus, $zipBody] = $get(
        "https://codeload.github.com/$repo/zip/$sha",
        "User-Agent: dockyard-refresh\r\n"
    );
    if ($zipStatus !== 200 || $zipBody === '') {
        fwrite(STDERR, "Archiwum commita $sha nie zostało pobrane (HTTP $zipStatus)\n");
        return 1;
    }
    if (file_put_contents($zip, $zipBody) === false) {
        fwrite(STDERR, "Nie można zapisać archiwum\n");
        return 1;
    }

    try {
        $root = refresh_unpack($zip, $unpack);
        $missing = refresh_missing($root);
        if ($missing !== []) {
            // Ten commit już się nie zmieni. Zapamiętany nie będzie pobierany co 15 minut.
            file_put_contents($stateFile, $sha . "\n");
            fwrite(STDERR, "Commit $sha nie ma: " . implode(', ', $missing) . ". Nic nie podmieniono, czekam na następny commit.\n");
            return 1;
        }
        refresh_install($root, $dest);
    } catch (RuntimeException $e) {
        fwrite(STDERR, $e->getMessage() . "\n");
        return 1;
    } finally {
        refresh_rm_tree($unpack);
        if (is_file($zip)) {
            unlink($zip);
        }
    }

    file_put_contents($stateFile, $sha . "\n");
    $modified = refresh_header_value($headerLines, 'Last-Modified');
    echo 'wgrano ' . $sha . ($modified !== '' ? " (zmiana w repo: $modified)" : '') . "\n";
    return 0;
}

/**
 * Wynik jobów test commita w GitHub Actions: true, gdy wszystkie przeszły; false, gdy któryś nie przeszedł;
 * null, gdy jeszcze trwają, nie wystartowały albo GitHub nie odpowiada.
 *
 * @param callable(string, string): array{0: int, 1: string, 2: list<string>} $get
 */
function refresh_tests_passed(string $sha, callable $get): ?bool
{
    [$status, $body] = $get(
        'https://api.github.com/repos/' . REFRESH_REPO . "/commits/$sha/check-runs?per_page=100",
        "User-Agent: dockyard-refresh\r\nAccept: application/vnd.github+json\r\n"
    );
    $decoded = $status === 200 ? json_decode($body, true) : null;
    $runs = is_array($decoded) && is_array($decoded['check_runs'] ?? null) ? $decoded['check_runs'] : [];
    $pending = false;
    $found = false;
    foreach ($runs as $run) {
        if (!is_array($run) || ($run['app']['slug'] ?? '') !== 'github-actions'
            || !str_starts_with((string) ($run['name'] ?? ''), REFRESH_TEST_CHECK)) {
            continue;
        }
        $found = true;
        if (($run['status'] ?? '') !== 'completed') {
            $pending = true;
        } elseif (($run['conclusion'] ?? '') !== 'success') {
            return false;
        }
    }
    return $found && !$pending ? true : null;
}

/** Rozpakowuje archiwum commita i zwraca jego jedyny katalog główny. */
function refresh_unpack(string $zip, string $unpack): string
{
    $archive = new ZipArchive();
    if ($archive->open($zip) !== true) {
        throw new RuntimeException('Nie można otworzyć archiwum');
    }
    refresh_rm_tree($unpack);
    mkdir($unpack, 0755, true);
    $extracted = $archive->extractTo($unpack);
    $archive->close();
    if ($extracted !== true) {
        throw new RuntimeException('Archiwum nie rozpakowało się w całości');
    }
    $top = glob($unpack . '/*', GLOB_ONLYDIR) ?: [];
    if (count($top) !== 1) {
        throw new RuntimeException('Nieoczekiwany układ archiwum');
    }
    return $top[0];
}

/** @return list<string> Pliki i katalogi potrzebne do podmiany, których brakuje w archiwum. */
function refresh_missing(string $root): array
{
    $missing = [];
    foreach (['docs', 'stacks', 'mcp/vendor', 'mcp/guide'] as $dir) {
        if (!is_dir($root . '/' . $dir)) {
            $missing[] = $dir . '/';
        }
    }
    $files = array_merge(['docs/index.html', 'templates.json', 'repository.json', 'stacks.lock.json', 'mcp/vendor/autoload.php', 'mcp/vendor/composer/installed.json', 'mcp/vendor/symfony/yaml/Yaml.php', 'mcp/vendor/symfony/yaml/Parser.php', 'mcp/guide/en.md'], array_map(static fn (string $name): string => 'mcp/' . $name, REFRESH_MCP_FILES));
    foreach ($files as $file) {
        if (!is_file($root . '/' . $file)) {
            $missing[] = $file;
        }
    }
    return $missing;
}

/** Stage and validate every artifact, then roll back the whole set if any publication fails. */
function refresh_install(string $root, string $dest, ?callable $move = null): void
{
    if (is_link($dest . '/mcp')) {
        throw new RuntimeException('Katalog mcp nie może być dowiązaniem podczas aktualizacji.');
    }
    refresh_validate_release($root);
    $move ??= 'rename';
    $entries = ['html' => 'docs', 'templates.json' => 'templates.json', 'repository.json' => 'repository.json', 'stacks.lock.json' => 'stacks.lock.json', 'stacks' => 'stacks'];
    foreach (REFRESH_MCP_FILES as $name) {
        $entries['mcp/' . $name] = 'mcp/' . $name;
    }
    $entries['mcp/vendor'] = 'mcp/vendor';
    $entries['mcp/guide'] = 'mcp/guide';
    $stage = $dest . '/.refresh-stage-' . bin2hex(random_bytes(6));
    if (!mkdir($stage . '/fresh/mcp', 0755, true) || !mkdir($stage . '/backup/mcp', 0755, true)) {
        throw new RuntimeException('Nie można przygotować wydania.');
    }
    $moved = [];
    $installed = [];
    $preserve = false;
    try {
        foreach ($entries as $target => $source) {
            $live = $dest . '/' . $target;
            if (is_link($live) || (file_exists($live) && is_dir($live) !== is_dir($root . '/' . $source))) {
                throw new RuntimeException('Nieoczekiwany typ pliku docelowego: ' . $live);
            }
            refresh_copy_entry($root . '/' . $source, $stage . '/fresh/' . $target);
        }
        foreach ($entries as $target => $source) {
            $live = $dest . '/' . $target;
            if (file_exists($live)) {
                if (!$move($live, $stage . '/backup/' . $target)) {
                    throw new RuntimeException('Nie można odsunąć ' . $live);
                }
                $moved[] = $target;
            }
            if (!$move($stage . '/fresh/' . $target, $live)) {
                throw new RuntimeException('Nie można opublikować ' . $live);
            }
            $installed[] = $target;
        }
    } catch (RuntimeException $error) {
        try {
            foreach (array_reverse($installed) as $target) {
                $live = $dest . '/' . $target;
                if (is_dir($live) && !is_link($live)) {
                    refresh_rm_tree($live);
                } elseif (!unlink($live)) {
                    throw new RuntimeException('Nie można usunąć nowego pliku ' . $live);
                }
            }
            foreach (array_reverse($moved) as $target) {
                if (!$move($stage . '/backup/' . $target, $dest . '/' . $target)) {
                    throw new RuntimeException('Nie można przywrócić ' . $target);
                }
            }
        } catch (RuntimeException $rollbackError) {
            $preserve = true;
            throw new RuntimeException($error->getMessage() . '; rollback: ' . $rollbackError->getMessage() . '; kopie zachowano w ' . $stage, 0, $error);
        }
        throw new RuntimeException($error->getMessage() . '; przywrócono poprzednie wydanie.', 0, $error);
    } finally {
        if (!$preserve) {
            refresh_rm_tree($stage);
        }
    }
}

function refresh_validate_release(string $root): void
{
    $missing = refresh_missing($root);
    if ($missing !== []) {
        throw new RuntimeException('Niekompletne wydanie: ' . implode(', ', $missing));
    }
    try {
        $feed = json_decode((string) file_get_contents($root . '/templates.json'), true, 512, JSON_THROW_ON_ERROR);
        $config = json_decode((string) file_get_contents($root . '/repository.json'), true, 32, JSON_THROW_ON_ERROR);
        if (!is_array($feed) || ($feed['version'] ?? '') !== '3' || !is_array($feed['templates'] ?? null)
            || !array_is_list($feed['templates'])) {
            throw new RuntimeException('Niepoprawny feed Portainer v3.');
        }
        if (!is_array($config) || !is_string($config['url'] ?? null)
            || filter_var($config['url'], FILTER_VALIDATE_URL) === false
            || !in_array(parse_url($config['url'], PHP_URL_SCHEME), ['http', 'https'], true)
            || parse_url($config['url'], PHP_URL_USER) !== null || parse_url($config['url'], PHP_URL_PASS) !== null
            || stripos($config['url'], '/OWNER/REPO') !== false) {
            throw new RuntimeException('Niepoprawna tożsamość repozytorium.');
        }
        $pins = json_decode((string) file_get_contents($root . '/stacks.lock.json'), true, 32, JSON_THROW_ON_ERROR);
        if (!is_array($pins) || !is_array($pins['repositories'] ?? null)) {
            throw new RuntimeException('Niepoprawne piny stosów w stacks.lock.json.');
        }
        json_decode((string) file_get_contents($root . '/mcp/composer.json'), true, 32, JSON_THROW_ON_ERROR);
        $lock = json_decode((string) file_get_contents($root . '/mcp/composer.lock'), true, 64, JSON_THROW_ON_ERROR);
        $installed = json_decode((string) file_get_contents($root . '/mcp/vendor/composer/installed.json'), true, 64, JSON_THROW_ON_ERROR);
        if (!is_array($lock['packages'] ?? null) || !is_array($installed['packages'] ?? null)) {
            throw new RuntimeException('Niepoprawne metadane zależności PHP.');
        }
        $versions = [];
        foreach ($installed['packages'] as $package) {
            $versions[$package['name']] = $package['version'];
        }
        foreach ($lock['packages'] as $package) {
            if (($versions[$package['name']] ?? '') !== $package['version']) {
                throw new RuntimeException('vendor nie odpowiada composer.lock: ' . $package['name']);
            }
        }
        if (trim((string) file_get_contents($root . '/docs/index.html')) === '') {
            throw new RuntimeException('Pusta strona wydania.');
        }
        $phpFiles = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($root . '/mcp', FilesystemIterator::SKIP_DOTS));
        foreach ($phpFiles as $file) {
            if ($file->isLink()) {
                throw new RuntimeException('Wydanie zawiera dowiązanie: ' . $file->getPathname());
            }
            if ($file->isFile() && $file->getExtension() === 'php') {
                token_get_all((string) file_get_contents($file->getPathname()), TOKEN_PARSE);
            }
        }
    } catch (JsonException | ParseError $error) {
        throw new RuntimeException('Niepoprawna zawartość wydania: ' . $error->getMessage(), 0, $error);
    }
}

function refresh_copy_entry(string $source, string $target): void
{
    if (is_link($source)) {
        throw new RuntimeException('Odmowa kopiowania dowiązania: ' . $source);
    }
    if (is_dir($source)) {
        if (!mkdir($target, 0755, true)) {
            throw new RuntimeException('Nie można przygotować ' . $target);
        }
        foreach (new DirectoryIterator($source) as $file) {
            if (!$file->isDot()) {
                refresh_copy_entry($file->getPathname(), $target . '/' . $file->getFilename());
            }
        }
    } elseif (!copy($source, $target)) {
        throw new RuntimeException('Nie można skopiować ' . $source);
    }
}

/** @return array{0: int, 1: string, 2: list<string>} */
function refresh_http_get(string $url, string $headers): array
{
    $ctx = stream_context_create(['http' => [
        'method' => 'GET',
        'header' => $headers,
        'ignore_errors' => true,
        'timeout' => 60,
        'follow_location' => 1,
        'max_redirects' => 3,
    ]]);
    $stream = @fopen($url, 'rb', false, $ctx);
    if ($stream === false) {
        return [0, '', []];
    }
    // Nagłówki z wrapper_data, bo PHP 9 usuwa $http_response_header.
    $meta = stream_get_meta_data($stream);
    $lines = is_array($meta['wrapper_data'] ?? null) ? $meta['wrapper_data'] : [];
    $body = stream_get_contents($stream);
    fclose($stream);
    $status = 0;
    foreach ($lines as $line) {
        if (preg_match('#^HTTP/\S+\s+(\d{3})#', $line, $m)) {
            $status = (int) $m[1];
        }
    }
    return [$status, is_string($body) ? $body : '', $lines];
}

/** @param list<string> $lines */
function refresh_header_value(array $lines, string $name): string
{
    $prefix = strtolower($name) . ':';
    $value = '';
    foreach ($lines as $line) {
        if (str_starts_with(strtolower($line), $prefix)) {
            $value = trim(substr($line, strlen($prefix)));
        }
    }
    return $value;
}

function refresh_rm_tree(string $dir): void
{
    if (!is_dir($dir)) {
        return;
    }
    $items = new RecursiveIteratorIterator(
        new RecursiveDirectoryIterator($dir, FilesystemIterator::SKIP_DOTS),
        RecursiveIteratorIterator::CHILD_FIRST
    );
    foreach ($items as $item) {
        $item->isDir() ? rmdir($item->getPathname()) : unlink($item->getPathname());
    }
    rmdir($dir);
}

// Uruchomiony wprost (cron), a nie dołączony przez require z testów.
if (PHP_SAPI === 'cli' && realpath((string) ($_SERVER['SCRIPT_FILENAME'] ?? '')) === __FILE__) {
    exit(refresh_main(REFRESH_DEST));
}
