<?php
declare(strict_types=1);

// Odświeża stronę, feed i pliki MCP z publicznego main.
// Cron co 15 minut: php /opt/dockyard/refresh.php
// Trzymaj kopię tego pliku poza document rootem (nie w mcp/ ani html/).
// Archiwum schodzi tylko wtedy, gdy zmieni się commit na main.
// Commit bez kompletu plików jest pomijany do następnego: nic nie zostaje podmienione.
// apache.conf i mcp/cache/ nie są ruszane.

const REFRESH_REPO = 'bauerpawel/DOCKYARD';
const REFRESH_DEST = '/var/www/dockyard';
const REFRESH_MCP_FILES = ['index.php', '.htaccess', 'AGENT.md', 'INSTRUKCJA.md'];

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
    foreach (['docs', 'stacks'] as $dir) {
        if (!is_dir($root . '/' . $dir)) {
            $missing[] = $dir . '/';
        }
    }
    $files = array_merge(['templates.json'], array_map(static fn (string $name): string => 'mcp/' . $name, REFRESH_MCP_FILES));
    foreach ($files as $file) {
        if (!is_file($root . '/' . $file)) {
            $missing[] = $file;
        }
    }
    return $missing;
}

function refresh_install(string $root, string $dest): void
{
    refresh_swap_dir($root . '/docs', $dest . '/html');
    refresh_replace_file($root . '/templates.json', $dest . '/templates.json');
    refresh_swap_dir($root . '/stacks', $dest . '/stacks');
    foreach (REFRESH_MCP_FILES as $name) {
        refresh_replace_file($root . '/mcp/' . $name, $dest . '/mcp/' . $name);
    }
}

/** Kopia obok celu i rename(): czytający widzi starą albo nową wersję, nigdy połowę pliku. */
function refresh_replace_file(string $source, string $target): void
{
    $temp = dirname($target) . '/.' . basename($target) . '.tmp';
    if (!copy($source, $temp) || !rename($temp, $target)) {
        @unlink($temp);
        throw new RuntimeException("Nie można zapisać $target");
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

function refresh_swap_dir(string $fresh, string $live): void
{
    if (!is_dir($fresh)) {
        throw new RuntimeException("Brak katalogu $fresh");
    }
    $stage = $live . '.new';
    $backup = $live . '.old';
    refresh_rm_tree($stage);
    if (!rename($fresh, $stage)) {
        throw new RuntimeException("Nie można przygotować $live");
    }
    if (is_dir($backup)) {
        refresh_rm_tree($backup);
    }
    if (is_dir($live) && !rename($live, $backup)) {
        throw new RuntimeException("Nie można odsunąć $live");
    }
    if (!rename($stage, $live)) {
        if (is_dir($backup)) {
            rename($backup, $live);
        }
        throw new RuntimeException("Nie można podmienić $live");
    }
    refresh_rm_tree($backup);
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
