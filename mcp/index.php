<?php
declare(strict_types=1);

/**
 * Dockyard MCP — katalog aplikacji i plan wdrożenia.
 * Agent wykonuje plan u siebie (Docker albo Portainer w LAN).
 * Ten proces nie łączy się z infrastrukturą użytkownika.
 */

const DOCKYARD_MCP_VERSION = '1.0.0';
const DOCKYARD_PROTOCOLS = ['2025-06-18', '2025-03-26'];
const DOCKYARD_PORTAINER_PREFIX = '/portainer/Files/AppData';
const DOCKYARD_STACK_MAX_BYTES = 524288;
const DOCKYARD_CACHE_TTL = 21600;
const DOCKYARD_FEED_MAX_BYTES = 5242880;
const DOCKYARD_FEED_TTL = 900;

function dockyard_main(): void
{
    if (PHP_SAPI === 'cli') {
        $args = $GLOBALS['argv'] ?? [];
        if (in_array('--self-test', $args, true)) {
            exit(dockyard_self_test());
        }
        fwrite(STDOUT, "Dockyard MCP przyjmuje POST JSON-RPC pod adresem katalogu, bez nazwy pliku .php.\n");
        exit(0);
    }
    dockyard_http();
}

function dockyard_http(): void
{
    ini_set('display_errors', '0');
    header('X-Content-Type-Options: nosniff');
    header('Access-Control-Allow-Origin: *');
    header('Access-Control-Allow-Methods: POST, OPTIONS');
    header('Access-Control-Allow-Headers: Content-Type, Accept, MCP-Protocol-Version, Mcp-Protocol-Version, Mcp-Session-Id, Mcp-Method');
    header('Access-Control-Expose-Headers: MCP-Protocol-Version');

    $method = strtoupper($_SERVER['REQUEST_METHOD'] ?? 'GET');
    if ($method === 'OPTIONS') {
        http_response_code(204);
        return;
    }
    if ($method !== 'POST') {
        dockyard_send(405, [
            'jsonrpc' => '2.0',
            'id' => null,
            'error' => [
                'code' => -32600,
                'message' => 'Ten adres przyjmuje wyłącznie POST z JSON-RPC (MCP Streamable HTTP).',
            ],
        ]);
        return;
    }

    $accept = $_SERVER['HTTP_ACCEPT'] ?? '';
    if ($accept !== '' && !str_contains($accept, 'application/json') && !str_contains($accept, 'text/event-stream') && !str_contains($accept, '*/*')) {
        dockyard_send(406, [
            'jsonrpc' => '2.0',
            'id' => null,
            'error' => ['code' => -32600, 'message' => 'Accept musi zawierać application/json albo text/event-stream.'],
        ]);
        return;
    }

    $raw = file_get_contents('php://input');
    if ($raw === false || trim($raw) === '') {
        dockyard_send(400, [
            'jsonrpc' => '2.0',
            'id' => null,
            'error' => ['code' => -32700, 'message' => 'Brak treści JSON.'],
        ]);
        return;
    }
    try {
        $message = json_decode($raw, true, 32, JSON_THROW_ON_ERROR);
    } catch (JsonException) {
        dockyard_send(400, [
            'jsonrpc' => '2.0',
            'id' => null,
            'error' => ['code' => -32700, 'message' => 'Niepoprawny JSON.'],
        ]);
        return;
    }
    if (!is_array($message) || array_is_list($message)) {
        dockyard_send(400, [
            'jsonrpc' => '2.0',
            'id' => null,
            'error' => ['code' => -32600, 'message' => 'Oczekiwany jest jeden obiekt JSON-RPC.'],
        ]);
        return;
    }

    $response = dockyard_dispatch($message);
    if ($response === null) {
        http_response_code(202);
        return;
    }
    dockyard_send(200, $response);
}

function dockyard_send(int $status, array $body): void
{
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($body, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
}

function dockyard_dispatch(array $message): ?array
{
    $method = (string) ($message['method'] ?? '');
    $hasId = array_key_exists('id', $message);
    $id = $message['id'] ?? null;
    $params = $message['params'] ?? [];
    if (!is_array($params)) {
        $params = [];
    }

    // Powiadomienie (bez id) i odpowiedź klienta (bez method) nie dostają odpowiedzi JSON-RPC.
    if (!$hasId || !array_key_exists('method', $message)) {
        return null;
    }
    if (($message['jsonrpc'] ?? '') !== '2.0') {
        return dockyard_rpc_error($id, -32600, 'jsonrpc musi być równe 2.0.');
    }

    try {
        $result = match ($method) {
            'initialize' => dockyard_initialize($params),
            'ping' => new stdClass(),
            'tools/list' => ['tools' => dockyard_tools()],
            'tools/call' => dockyard_call_tool($params),
            default => null,
        };
    } catch (InvalidArgumentException $e) {
        return dockyard_rpc_error($id, -32602, $e->getMessage());
    } catch (Throwable $e) {
        return dockyard_rpc_error($id, -32603, 'Błąd serwera.');
    }

    if ($result === null) {
        return dockyard_rpc_error($id, -32601, 'Nieznana metoda.');
    }
    return ['jsonrpc' => '2.0', 'id' => $id, 'result' => $result];
}

function dockyard_rpc_error(mixed $id, int $code, string $message): array
{
    return ['jsonrpc' => '2.0', 'id' => $id, 'error' => ['code' => $code, 'message' => $message]];
}

function dockyard_initialize(array $params): array
{
    // Nieznana wersja dostaje najnowszą obsługiwaną (pierwszą na liście), jak zaleca specyfikacja MCP.
    $requested = (string) ($params['protocolVersion'] ?? '');
    $version = in_array($requested, DOCKYARD_PROTOCOLS, true) ? $requested : DOCKYARD_PROTOCOLS[0];
    $instructions = dockyard_agent_instructions();
    return [
        'protocolVersion' => $version,
        'capabilities' => ['tools' => ['listChanged' => false]],
        'serverInfo' => ['name' => 'dockyard', 'version' => DOCKYARD_MCP_VERSION],
        'instructions' => $instructions,
    ];
}

function dockyard_agent_instructions(): string
{
    $path = __DIR__ . DIRECTORY_SEPARATOR . 'AGENT.md';
    $text = is_file($path) ? file_get_contents($path) : false;
    if (!is_string($text) || trim($text) === '') {
        return 'Katalog Dockyard. Wdrożenie wykonuje agent na maszynie użytkownika, w Dockerze albo w jego Portainerze.';
    }
    return trim($text);
}

/** @return list<array<string, mixed>> */
function dockyard_tools(): array
{
    return [
        [
            'name' => 'list_apps',
            'description' => 'Szuka aplikacji w katalogu Dockyard. Zwraca krótkie karty (slug, tytuł, kategoria, rodzaj, obraz). Pełny opis i plan wdrożenia biorą się z get_app i prepare_deploy.',
            'inputSchema' => [
                'type' => 'object',
                'properties' => [
                    'query' => ['type' => 'string', 'description' => 'Słowa z nazwy, opisu, obrazu albo kategorii. Wszystkie muszą pasować.'],
                    'category' => ['type' => 'string', 'description' => 'Dokładna kategoria, bez rozróżniania wielkości liter.'],
                    'kind' => ['type' => 'string', 'enum' => ['container', 'compose', 'swarm', 'edge'], 'description' => 'Rodzaj wpisu.'],
                    'limit' => ['type' => 'integer', 'minimum' => 1, 'maximum' => 50, 'description' => 'Domyślnie 20, maksimum 50.'],
                    'offset' => ['type' => 'integer', 'minimum' => 0],
                ],
                'additionalProperties' => false,
            ],
        ],
        [
            'name' => 'get_app',
            'description' => 'Jedna aplikacja po slug z list_apps: opis, obraz albo repozytorium stosu, porty, wolumeny, zmienne (sekrety oznaczone), ostrzeżenia. Nic nie uruchamia.',
            'inputSchema' => [
                'type' => 'object',
                'properties' => [
                    'slug' => ['type' => 'string', 'description' => 'Pole slug z list_apps.'],
                ],
                'required' => ['slug'],
                'additionalProperties' => false,
            ],
        ],
        [
            'name' => 'prepare_deploy',
            'description' => 'Składa plan wdrożenia dla Dockera i dla Portainera. Nie łączy się z żadnym z nich. Uruchom plan na maszynie użytkownika tylko gdy ready jest true i użytkownik wybrał cel. Klucza Portainera i haseł aplikacji tu nie przysyłaj: sekrety wymień lokalnie w miejsce CHANGEME, a ich nazwy podaj w local_secrets. confirm=true dopiero po wyraźnej zgodzie użytkownika.',
            'inputSchema' => [
                'type' => 'object',
                'properties' => [
                    'slug' => ['type' => 'string'],
                    'name' => ['type' => 'string', 'description' => 'Nazwa projektu i stosu. Domyślnie slug.'],
                    'env' => [
                        'type' => 'object',
                        'additionalProperties' => ['type' => 'string'],
                        'description' => 'Nadpisania zmiennych, które nie są sekretami.',
                    ],
                    'local_secrets' => [
                        'type' => 'array',
                        'items' => ['type' => 'string'],
                        'description' => 'Nazwy sekretów, które agent uzupełni lokalnie. W planie stoją jako CHANGEME.',
                    ],
                    'data_dir' => ['type' => 'string', 'description' => 'Katalog projektu na maszynie użytkownika. Domyślnie ./dockyard/<nazwa>.'],
                    'confirm' => ['type' => 'boolean', 'description' => 'true tylko po wyraźnej zgodzie na wdrożenie.'],
                    'allow_privileged' => ['type' => 'boolean'],
                    'allow_default_secrets' => ['type' => 'boolean'],
                ],
                'required' => ['slug'],
                'additionalProperties' => false,
            ],
        ],
    ];
}

function dockyard_call_tool(array $params): array
{
    $name = (string) ($params['name'] ?? '');
    $args = $params['arguments'] ?? [];
    if (is_string($args)) {
        $decoded = json_decode($args, true);
        $args = is_array($decoded) ? $decoded : [];
    }
    if (!is_array($args)) {
        $args = [];
    }

    $payload = match ($name) {
        'list_apps' => dockyard_list_apps($args),
        'get_app' => dockyard_get_app($args),
        'prepare_deploy' => dockyard_prepare_deploy($args),
        default => null,
    };
    if ($payload === null) {
        return dockyard_tool_text('Nieznane narzędzie: ' . $name, true);
    }
    if (isset($payload['error']) && is_string($payload['error'])) {
        return dockyard_tool_text($payload['error'], true);
    }
    $json = json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT | JSON_THROW_ON_ERROR);
    return dockyard_tool_text($json, false);
}

function dockyard_tool_text(string $text, bool $isError): array
{
    return [
        'content' => [['type' => 'text', 'text' => $text]],
        'isError' => $isError,
    ];
}

/** @return array<string, mixed> */
function dockyard_list_apps(array $args): array
{
    $catalog = dockyard_catalog();
    $query = trim((string) ($args['query'] ?? ''));
    $category = trim((string) ($args['category'] ?? ''));
    $kind = trim((string) ($args['kind'] ?? ''));
    $limit = is_numeric($args['limit'] ?? null) ? (int) $args['limit'] : 20;
    $offset = is_numeric($args['offset'] ?? null) ? (int) $args['offset'] : 0;
    if ($limit < 1) {
        $limit = 1;
    }
    if ($limit > 50) {
        $limit = 50;
    }
    if ($offset < 0) {
        $offset = 0;
    }

    $terms = $query === '' ? [] : (preg_split('/\s+/', dockyard_lower($query)) ?: []);
    $matched = [];
    foreach ($catalog as $app) {
        if ($category !== '' && dockyard_lower((string) ($app['category'] ?? '')) !== dockyard_lower($category)) {
            continue;
        }
        if ($kind !== '' && ($app['kind'] ?? '') !== $kind) {
            continue;
        }
        if ($terms !== []) {
            $hay = dockyard_lower(implode("\n", [
                (string) ($app['slug'] ?? ''),
                (string) ($app['title'] ?? ''),
                (string) ($app['description'] ?? ''),
                (string) ($app['image'] ?? ''),
                (string) ($app['category'] ?? ''),
            ]));
            $ok = true;
            foreach ($terms as $term) {
                if ($term !== '' && !str_contains($hay, $term)) {
                    $ok = false;
                    break;
                }
            }
            if (!$ok) {
                continue;
            }
        }
        $matched[] = [
            'slug' => $app['slug'],
            'title' => $app['title'],
            'category' => $app['category'],
            'kind' => $app['kind'],
            'image' => $app['image'],
            'description' => dockyard_cut((string) ($app['description'] ?? ''), 160),
        ];
    }
    if ($query !== '') {
        usort($matched, static function (array $a, array $b) use ($query): int {
            return dockyard_search_rank($a, $query) <=> dockyard_search_rank($b, $query);
        });
    }

    return [
        'total' => count($matched),
        'offset' => $offset,
        'limit' => $limit,
        'apps' => array_slice($matched, $offset, $limit),
    ];
}

/** @return array<string, mixed> */
function dockyard_get_app(array $args): array
{
    $slug = trim((string) ($args['slug'] ?? ''));
    if ($slug === '') {
        return ['error' => 'Podaj slug.'];
    }
    $app = dockyard_find($slug);
    if ($app === null) {
        return ['error' => 'Brak aplikacji o slug „' . $slug . '”.'];
    }
    $template = $app['template'];
    $env = [];
    foreach ($template['env'] ?? [] as $item) {
        if (!is_array($item) || empty($item['name'])) {
            continue;
        }
        $name = (string) $item['name'];
        $env[] = [
            'name' => $name,
            'label' => isset($item['label']) ? (string) $item['label'] : null,
            'description' => isset($item['description']) ? dockyard_cut(strip_tags((string) $item['description']), 400) : null,
            'default' => dockyard_env_default($item),
            'secret' => dockyard_is_secret($name),
        ];
    }
    $warnings = dockyard_template_warnings($template);
    return [
        'slug' => $app['slug'],
        'title' => $app['title'],
        'description' => dockyard_cut(trim(strip_tags((string) ($app['description'] ?? ''))), 2000),
        'category' => $app['category'],
        'kind' => $app['kind'],
        'logo' => $template['logo'] ?? null,
        'image' => $app['image'],
        'privileged' => !empty($template['privileged']),
        'network' => $template['network'] ?? null,
        'command' => $template['command'] ?? null,
        'ports' => array_values($template['ports'] ?? []),
        'volumes' => array_values($template['volumes'] ?? []),
        'env' => $env,
        'repository' => $template['repository'] ?? null,
        'warnings' => $warnings,
    ];
}

/** @return array<string, mixed> */
function dockyard_prepare_deploy(array $args): array
{
    $slug = trim((string) ($args['slug'] ?? ''));
    if ($slug === '') {
        return ['error' => 'Podaj slug.'];
    }
    $app = dockyard_find($slug);
    if ($app === null) {
        return ['error' => 'Brak aplikacji o slug „' . $slug . '”.'];
    }

    $template = $app['template'];
    $project = dockyard_project_name((string) ($args['name'] ?? ''), $app['slug']);
    $userEnv = dockyard_env_map($args['env'] ?? []);
    $localSecrets = [];
    foreach ($args['local_secrets'] ?? [] as $secretName) {
        if (is_string($secretName) && $secretName !== '') {
            $localSecrets[] = $secretName;
        }
    }
    $confirm = dockyard_bool($args['confirm'] ?? false);
    $allowPrivileged = dockyard_bool($args['allow_privileged'] ?? false);
    $allowDefaultSecrets = dockyard_bool($args['allow_default_secrets'] ?? false);
    $dataDir = isset($args['data_dir']) ? trim((string) $args['data_dir']) : '';
    $directory = $dataDir !== '' ? rtrim(str_replace('\\', '/', $dataDir), '/') : './dockyard/' . $project;

    $blockers = [];
    $warnings = dockyard_template_warnings($template);
    if ($dataDir !== '' && (str_contains($dataDir, '..') || str_contains($dataDir, "\n") || str_contains($dataDir, "\0"))) {
        $blockers[] = 'data_dir zawiera niedozwoloną sekwencję.';
    }
    if (!$confirm) {
        $blockers[] = 'Brak zgody. Pokaż plan użytkownikowi i wywołaj prepare_deploy ponownie z confirm=true dopiero po wyraźnym tak.';
    }
    if (!empty($template['privileged']) && !$allowPrivileged) {
        $blockers[] = 'Kontener jest privileged (pełny dostęp do urządzeń hosta). Uruchom go tylko z allow_privileged=true po osobnej zgodzie użytkownika.';
    }
    if ($app['kind'] === 'edge') {
        $blockers[] = 'To jest szablon Edge. Ten serwer składa plan Docker Compose i stos standalone Portainera.';
    }
    if ($app['kind'] === 'unknown') {
        $blockers[] = 'Nieobsługiwany typ szablonu.';
    }
    if ($app['kind'] === 'swarm') {
        $warnings[] = 'Wpis jest stosem Swarm. Plan używa API standalone Portainera. Na środowisku Swarm tego żądania nie wysyłaj.';
    }

    [$envValues, $secretsToSet, $secretBlockers, $secretWarnings] = dockyard_resolve_env(
        is_array($template['env'] ?? null) ? $template['env'] : [],
        $userEnv,
        $localSecrets,
        $allowDefaultSecrets
    );
    $blockers = array_merge($blockers, $secretBlockers);
    $warnings = array_merge($warnings, $secretWarnings);

    $dockerCompose = null;
    $portainerCompose = null;
    $loadError = null;
    if ($app['kind'] === 'container') {
        if (empty($template['image'])) {
            $blockers[] = 'Szablon kontenera nie ma obrazu.';
        } else {
            $dockerCompose = dockyard_container_compose($template, $project, true, $envValues);
            $portainerCompose = dockyard_container_compose($template, $project, false, $envValues);
        }
    } elseif (in_array($app['kind'], ['compose', 'swarm'], true)) {
        try {
            $original = dockyard_load_stack($template);
            $portainerCompose = $original;
            $dockerCompose = str_replace(DOCKYARD_PORTAINER_PREFIX, './data', $original);
        } catch (RuntimeException $e) {
            $loadError = $e->getMessage();
            $blockers[] = $loadError;
        }
    }

    $ports = array_values($template['ports'] ?? []);
    if ($ports === [] && is_string($dockerCompose)) {
        $ports = dockyard_ports_from_text($dockerCompose);
    }
    $randomPorts = [];
    foreach ($ports as $port) {
        if (preg_match('#^\d+(?:/(?:tcp|udp))?$#', (string) $port) === 1) {
            $randomPorts[] = (string) $port;
        }
    }
    foreach ($ports as $port) {
        if (preg_match('#^(\d+):\d+#', (string) $port, $m) === 1 && (int) $m[1] > 0 && (int) $m[1] < 1024) {
            $warnings[] = 'Aplikacja publikuje port poniżej 1024 (' . $port . '). Na Linuksie wiązanie tego portu może wymagać dodatkowych uprawnień.';
            break;
        }
    }
    if ($randomPorts !== []) {
        $warnings[] = 'Port ' . implode(', ', $randomPorts) . ' nie ma numeru portu hosta. Docker wystawi go na losowym porcie hosta: numer pokaże docker.ps albo lista kontenerów w Portainerze.';
    }
    $warnings = array_values(array_unique($warnings));

    $envFile = dockyard_dotenv($envValues);
    $portainerEnv = [];
    foreach ($envValues as $name => $value) {
        $portainerEnv[] = ['name' => $name, 'value' => $value];
    }

    $ready = $blockers === [] && is_string($dockerCompose) && is_string($portainerCompose);
    return [
        'slug' => $app['slug'],
        'title' => $app['title'],
        'kind' => $app['kind'],
        'project' => $project,
        'ready' => $ready,
        'blockers' => $blockers,
        'warnings' => $warnings,
        'secrets_to_set' => $secretsToSet,
        'published_ports' => $ports,
        'suggested_url' => dockyard_suggested_url($ports),
        'agent_next_step' => $ready
            ? 'Plan jest gotowy. Wykonaj wyłącznie cel wybrany przez użytkownika, na jego maszynie. CHANGEME podmień lokalnie. Adresu i klucza Portainera nie wysyłaj do tego serwera.'
            : 'Nic nie uruchamiaj. Usuń powody z blockers i wywołaj prepare_deploy ponownie.',
        'docker' => is_string($dockerCompose) ? [
            'directory' => $directory,
            'compose_filename' => 'docker-compose.yml',
            'env_filename' => '.env',
            'compose' => $dockerCompose,
            'env_file' => $envFile,
            'check' => ['docker', 'info'],
            'up' => ['docker', 'compose', '-f', 'docker-compose.yml', '-p', $project, 'up', '-d'],
            'ps' => ['docker', 'compose', '-f', 'docker-compose.yml', '-p', $project, 'ps'],
        ] : null,
        'portainer' => is_string($portainerCompose) ? [
            'inputs' => ['PORTAINER_URL', 'PORTAINER_API_KEY', 'PORTAINER_ENDPOINT_ID'],
            'method' => 'POST',
            'url' => '{PORTAINER_URL}/api/stacks/create/standalone/string?endpointId={PORTAINER_ENDPOINT_ID}',
            'headers' => [
                'X-API-Key' => '{PORTAINER_API_KEY}',
                'Content-Type' => 'application/json',
            ],
            'body' => [
                'name' => $project,
                'stackFileContent' => $portainerCompose,
                'env' => $portainerEnv,
                'fromAppTemplate' => false,
            ],
        ] : null,
    ];
}

/**
 * @param list<array<string, mixed>> $specs
 * @param array<string, string> $userEnv
 * @param list<string> $localSecrets
 * @return array{0: array<string, string>, 1: list<string>, 2: list<string>, 3: list<string>}
 */
function dockyard_resolve_env(array $specs, array $userEnv, array $localSecrets, bool $allowDefaultSecrets): array
{
    $values = [];
    $secretsToSet = [];
    $blockers = [];
    $warnings = [];
    foreach ($specs as $spec) {
        if (!is_array($spec) || empty($spec['name'])) {
            continue;
        }
        $name = (string) $spec['name'];
        if (!preg_match('/^[A-Za-z_][A-Za-z0-9_]*$/', $name)) {
            continue;
        }
        $default = dockyard_env_default($spec);
        $userSet = array_key_exists($name, $userEnv);
        $effective = $userSet ? $userEnv[$name] : $default;
        $isSecret = dockyard_is_secret($name);
        $markedLocal = in_array($name, $localSecrets, true);
        if ($markedLocal && (!$userSet || $effective === $default)) {
            $effective = 'CHANGEME';
            $secretsToSet[] = $name;
        } elseif ($isSecret && $default !== '' && $effective === $default && !$allowDefaultSecrets) {
            $blockers[] = 'Zmienna ' . $name . ' ma wartość domyślną z szablonu. Ustal własną wartość (hasło, klucz), podaj nazwę w local_secrets i wstaw ją lokalnie w miejsce CHANGEME.';
        } elseif ($isSecret && $default === '' && !$userSet) {
            $warnings[] = 'Zmienna ' . $name . ' wygląda na sekret i nie ma wartości. Uzupełnij ją lokalnie, jeśli aplikacja jej wymaga.';
        }
        $values[$name] = $effective;
    }
    foreach ($userEnv as $name => $value) {
        if (!isset($values[$name]) && preg_match('/^[A-Za-z_][A-Za-z0-9_]*$/', $name)) {
            $values[$name] = $value;
        }
    }
    return [$values, $secretsToSet, $blockers, $warnings];
}

function dockyard_env_default(array $env): string
{
    if (array_key_exists('default', $env) && $env['default'] !== null) {
        return (string) $env['default'];
    }
    foreach ($env['select'] ?? [] as $option) {
        if (is_array($option) && !empty($option['default'])) {
            return (string) ($option['value'] ?? '');
        }
    }
    return '';
}

function dockyard_is_secret(string $name): bool
{
    $tokens = preg_split('/[^a-z0-9]+/', strtolower($name), -1, PREG_SPLIT_NO_EMPTY) ?: [];
    // Klucz publiczny i ścieżka do pliku z sekretem nie są sekretem.
    if ($tokens === [] || in_array('public', $tokens, true) || in_array(end($tokens), ['file', 'dir'], true)) {
        return false;
    }
    if (preg_match('/password|passwd|secret|token|api_?key/i', $name) === 1) {
        return true;
    }
    foreach ($tokens as $token) {
        if (in_array($token, ['pass', 'pwd', 'key', 'salt'], true) || preg_match('/(pass|key)$/', $token) === 1) {
            return true;
        }
    }
    return false;
}

/** @param array<string, mixed> $template */
function dockyard_template_warnings(array $template): array
{
    $warnings = [];
    if (!empty($template['privileged'])) {
        $warnings[] = 'Szablon uruchamia kontener jako privileged: dostaje dostęp do urządzeń i uprawnień hosta, szerszy niż sama aplikacja zwykle potrzebuje.';
    }
    $network = (string) ($template['network'] ?? '');
    if ($network === 'host') {
        $warnings[] = 'Kontener używa sieci hosta i widzi porty maszyny bezpośrednio.';
    }
    return $warnings;
}

/**
 * @param array<string, mixed> $template
 * @param array<string, string> $envValues
 */
function dockyard_container_compose(array $template, string $project, bool $dockerPaths, array $envValues): string
{
    $image = (string) $template['image'];
    $lines = [
        '# Dockyard: ' . (string) ($template['title'] ?? $project),
        'services:',
        '  ' . $project . ':',
        '    image: ' . dockyard_yaml_string($image),
        '    restart: ' . dockyard_restart((string) ($template['restart_policy'] ?? 'unless-stopped')),
    ];
    $ports = $template['ports'] ?? [];
    if (is_array($ports) && $ports !== []) {
        $lines[] = '    ports:';
        foreach ($ports as $port) {
            $lines[] = '      - ' . dockyard_yaml_string((string) $port);
        }
    }
    if ($envValues !== []) {
        $lines[] = '    environment:';
        foreach (array_keys($envValues) as $name) {
            $lines[] = '      ' . $name . ': ${' . $name . '}';
        }
    }
    $volumes = $template['volumes'] ?? [];
    $named = [];
    if (is_array($volumes) && $volumes !== []) {
        $lines[] = '    volumes:';
        foreach ($volumes as $volume) {
            if (!is_array($volume) || empty($volume['container'])) {
                continue;
            }
            [$left, $isNamed] = dockyard_volume_source($volume, $dockerPaths);
            $suffix = !empty($volume['readonly']) ? ':ro' : '';
            $lines[] = '      - ' . dockyard_yaml_string($left . ':' . (string) $volume['container'] . $suffix);
            if ($isNamed) {
                $named[$left] = true;
            }
        }
    }
    $network = trim((string) ($template['network'] ?? ''));
    if ($network === 'host' || $network === 'bridge' || $network === 'none' || str_starts_with($network, 'container:')) {
        $lines[] = '    network_mode: ' . dockyard_yaml_string($network);
    } elseif ($network !== '') {
        $lines[] = '    networks:';
        $lines[] = '      - ' . dockyard_yaml_string($network);
    }
    if (!empty($template['privileged'])) {
        $lines[] = '    privileged: true';
    }
    if (!empty($template['command'])) {
        $lines[] = '    command: ' . dockyard_yaml_string((string) $template['command']);
    }
    if (!empty($template['hostname'])) {
        $lines[] = '    hostname: ' . dockyard_yaml_string((string) $template['hostname']);
    }
    if (!empty($template['interactive'])) {
        $lines[] = '    stdin_open: true';
        $lines[] = '    tty: true';
    }
    if ($network !== '' && $network !== 'host' && $network !== 'bridge' && $network !== 'none' && !str_starts_with($network, 'container:')) {
        $lines[] = 'networks:';
        $lines[] = '  ' . $network . ':';
        $lines[] = '    external: true';
    }
    if ($named !== []) {
        $lines[] = 'volumes:';
        foreach (array_keys($named) as $name) {
            $lines[] = '  ' . $name . ':';
        }
    }
    return implode("\n", $lines) . "\n";
}

/** @param array<string, mixed> $volume @return array{0: string, 1: bool} */
function dockyard_volume_source(array $volume, bool $dockerPaths): array
{
    $bind = trim((string) ($volume['bind'] ?? ''));
    if ($bind === '') {
        $name = 'data' . preg_replace('/[^a-z0-9]+/', '_', strtolower((string) $volume['container']));
        $name = trim((string) $name, '_');
        return [$name === '' ? 'data' : $name, true];
    }
    if ($dockerPaths && str_starts_with($bind, DOCKYARD_PORTAINER_PREFIX)) {
        $bind = './data' . substr($bind, strlen(DOCKYARD_PORTAINER_PREFIX));
    }
    return [$bind, false];
}

function dockyard_restart(string $policy): string
{
    return in_array($policy, ['always', 'unless-stopped', 'on-failure', 'no'], true) ? $policy : 'unless-stopped';
}

/** @param array<string, string> $env */
function dockyard_dotenv(array $env): string
{
    $lines = [];
    foreach ($env as $name => $value) {
        $lines[] = $name . '=' . dockyard_dotenv_value($value);
    }
    return $lines === [] ? '' : implode("\n", $lines) . "\n";
}

function dockyard_dotenv_value(string $value): string
{
    if ($value === '' || preg_match('/\s|#|"|\'|\\\\/', $value) === 1) {
        return '"' . str_replace(["\\", '"', "\n", "\r"], ['\\\\', '\\"', '\\n', ''], $value) . '"';
    }
    return $value;
}

function dockyard_yaml_string(string $value): string
{
    if ($value === '') {
        return '""';
    }
    if (preg_match('/^(true|false|null|yes|no|on|off)$/i', $value) === 1
        || preg_match('/[:#{}\[\],&*!|>%@`"\'\n\r\t]|^\s|\s$|^[-?]|^\d/', $value) === 1) {
        return '"' . str_replace(["\\", '"', "\n", "\r", "\t"], ['\\\\', '\\"', '\\n', '\\r', '\\t'], $value) . '"';
    }
    return $value;
}

/** @param array<string, mixed> $template */
function dockyard_load_stack(array $template): string
{
    $repo = $template['repository'] ?? null;
    if (!is_array($repo) || empty($repo['url']) || empty($repo['stackfile'])) {
        throw new RuntimeException('Szablon stosu nie ma repository.url i repository.stackfile.');
    }
    $stackfile = (string) $repo['stackfile'];
    $local = dockyard_read_local_stack($stackfile);
    if ($local !== null) {
        return $local;
    }
    $url = dockyard_stack_url((string) $repo['url'], $stackfile);
    if ($url === null) {
        throw new RuntimeException('Adres repozytorium stosu jest spoza GitHuba albo ścieżka pliku jest niedozwolona.');
    }
    return dockyard_cached_get($url);
}

function dockyard_read_local_stack(string $stackfile): ?string
{
    $relative = str_replace('\\', '/', $stackfile);
    if ($relative === '' || str_contains($relative, '..') || str_starts_with($relative, '/')) {
        return null;
    }
    $root = dirname(__DIR__);
    $candidate = $root . DIRECTORY_SEPARATOR . str_replace('/', DIRECTORY_SEPARATOR, $relative);
    $realRoot = realpath($root);
    $real = realpath($candidate);
    if ($realRoot === false || $real === false || !is_file($real)) {
        return null;
    }
    $prefix = rtrim($realRoot, DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR;
    if (!str_starts_with($real, $prefix)) {
        return null;
    }
    $body = file_get_contents($real);
    if (!is_string($body) || $body === '' || strlen($body) > DOCKYARD_STACK_MAX_BYTES) {
        return null;
    }
    return $body;
}

function dockyard_stack_url(string $repoUrl, string $stackfile): ?string
{
    $stackfile = str_replace('\\', '/', $stackfile);
    if ($stackfile === '' || str_contains($stackfile, '..') || str_starts_with($stackfile, '/')) {
        return null;
    }
    $parts = parse_url(trim($repoUrl));
    if (!is_array($parts) || ($parts['scheme'] ?? '') !== 'https' || isset($parts['user']) || isset($parts['pass'])) {
        return null;
    }
    $host = strtolower((string) ($parts['host'] ?? ''));
    if ($host !== 'github.com' && $host !== 'www.github.com') {
        return null;
    }
    $path = trim((string) ($parts['path'] ?? ''), '/');
    if (preg_match('#^([^/]+)/([^/]+?)(?:\.git)?(?:/tree/([^/]+))?$#', $path, $m) !== 1) {
        return null;
    }
    $ref = $m[3] ?? 'HEAD';
    if (preg_match('#^[A-Za-z0-9._/-]+$#', $ref) !== 1) {
        return null;
    }
    $encode = static function (string $piece): string {
        return implode('/', array_map('rawurlencode', explode('/', $piece)));
    };
    return 'https://raw.githubusercontent.com/' . rawurlencode($m[1]) . '/' . rawurlencode($m[2]) . '/' . $encode($ref) . '/' . $encode($stackfile);
}

function dockyard_cached_get(string $url): string
{
    $cacheDir = __DIR__ . DIRECTORY_SEPARATOR . 'cache';
    $cacheFile = $cacheDir . DIRECTORY_SEPARATOR . hash('sha256', $url) . '.body';
    if (is_file($cacheFile) && (time() - (int) filemtime($cacheFile)) < DOCKYARD_CACHE_TTL) {
        $cached = file_get_contents($cacheFile);
        if (is_string($cached) && $cached !== '') {
            return $cached;
        }
    }
    $body = dockyard_http_get($url);
    if (is_dir($cacheDir) || @mkdir($cacheDir, 0775, true)) {
        @file_put_contents($cacheFile, $body);
    }
    return $body;
}

function dockyard_http_get(string $url, int $maxBytes = DOCKYARD_STACK_MAX_BYTES): string
{
    $current = $url;
    for ($hop = 0; $hop < 3; $hop++) {
        dockyard_assert_public_url($current);
        $context = stream_context_create([
            'http' => [
                'method' => 'GET',
                'timeout' => 10,
                'follow_location' => 0,
                'ignore_errors' => true,
                'header' => "User-Agent: dockyard-mcp/1.0\r\nAccept: text/plain, text/yaml, */*\r\n",
            ],
            'ssl' => [
                'verify_peer' => true,
                'verify_peer_name' => true,
            ],
        ]);
        $stream = @fopen($current, 'rb', false, $context);
        if ($stream === false) {
            throw new RuntimeException('Nie udało się pobrać pliku stosu.');
        }
        try {
            // Nagłówki z wrapper_data, bo PHP 9 usuwa $http_response_header.
            $meta = stream_get_meta_data($stream);
            $headers = is_array($meta['wrapper_data'] ?? null) ? $meta['wrapper_data'] : [];
            $status = dockyard_http_status($headers);
            if ($status >= 300 && $status < 400) {
                $location = dockyard_header($headers, 'location');
                if ($location === null) {
                    throw new RuntimeException('Przekierowanie pliku stosu bez nagłówka Location.');
                }
                $current = dockyard_resolve_url($current, $location);
                continue;
            }
            if ($status === 200) {
                return dockyard_read_limited($stream, $maxBytes);
            }
        } finally {
            fclose($stream);
        }
        throw new RuntimeException('Nie udało się pobrać pliku stosu (HTTP ' . $status . ').');
    }
    throw new RuntimeException('Za dużo przekierowań przy pobieraniu pliku stosu.');
}

/**
 * Czyta najwyżej $max bajtów, więc za duży plik nie trafia w całości do pamięci.
 *
 * @param resource $stream
 */
function dockyard_read_limited($stream, int $max): string
{
    $body = stream_get_contents($stream, $max + 1);
    if (!is_string($body) || $body === '') {
        throw new RuntimeException('Plik stosu jest pusty albo nie dał się odczytać.');
    }
    if (strlen($body) > $max) {
        throw new RuntimeException('Plik stosu jest za duży.');
    }
    return $body;
}

function dockyard_assert_public_url(string $url): void
{
    $parts = parse_url($url);
    $host = strtolower((string) ($parts['host'] ?? ''));
    $allowed = [
        'raw.githubusercontent.com',
        'objects.githubusercontent.com',
        'codeload.github.com',
        'cdn.jsdelivr.net',
    ];
    if (!is_array($parts)
        || ($parts['scheme'] ?? '') !== 'https'
        || isset($parts['user'])
        || isset($parts['pass'])
        || !in_array($host, $allowed, true)
        || (isset($parts['port']) && (int) $parts['port'] !== 443)) {
        throw new RuntimeException('Niedozwolony adres pliku stosu.');
    }
}

function dockyard_resolve_url(string $base, string $location): string
{
    if (preg_match('#^https://#i', $location) === 1) {
        return $location;
    }
    $parts = parse_url($base);
    $origin = 'https://' . (string) ($parts['host'] ?? '');
    if (str_starts_with($location, '/')) {
        return $origin . $location;
    }
    $dir = preg_replace('#/[^/]*$#', '/', (string) ($parts['path'] ?? '/'));
    return $origin . $dir . $location;
}

/** @param list<string> $headers */
function dockyard_http_status(array $headers): int
{
    foreach ($headers as $header) {
        if (preg_match('#^HTTP/\S+\s+(\d{3})#', $header, $m) === 1) {
            return (int) $m[1];
        }
    }
    return 0;
}

/** @param list<string> $headers */
function dockyard_header(array $headers, string $name): ?string
{
    $prefix = strtolower($name) . ':';
    foreach ($headers as $header) {
        if (str_starts_with(strtolower($header), $prefix)) {
            return trim(substr($header, strlen($prefix)));
        }
    }
    return null;
}

/** @param list<string> $ports */
function dockyard_ports_from_text(string $text): array
{
    $ports = [];
    if (preg_match_all('/["\']?(\d{1,5})(?::(\d{1,5}))?\/(tcp|udp)["\']?/', $text, $hits, PREG_SET_ORDER) > 0) {
        foreach ($hits as $hit) {
            $ports[] = $hit[0];
        }
    }
    if (preg_match_all('/["\'](\d{1,5}:\d{1,5})["\']/', $text, $plain) > 0) {
        foreach ($plain[1] as $pair) {
            $ports[] = $pair . '/tcp';
        }
    }
    return array_values(array_unique($ports));
}

/** @param list<string> $ports */
function dockyard_suggested_url(array $ports): ?string
{
    $hosts = [];
    foreach ($ports as $port) {
        // Port bez numeru hosta ("80/tcp") dostaje losowy port hosta, więc nie ma pod nim adresu.
        if (preg_match('#^(\d+):\d+(?:/(tcp|udp))?$#', $port, $m) !== 1) {
            continue;
        }
        if (($m[2] ?? 'tcp') === 'udp') {
            continue;
        }
        $hosts[] = (int) $m[1];
    }
    if ($hosts === []) {
        return null;
    }
    foreach ([80, 443, 8080, 8443, 3000, 8006, 5678, 9443] as $preferred) {
        if (in_array($preferred, $hosts, true)) {
            $scheme = in_array($preferred, [443, 8443, 9443], true) ? 'https' : 'http';
            return $scheme . '://localhost:' . $preferred;
        }
    }
    return 'http://localhost:' . $hosts[0];
}

function dockyard_project_name(string $requested, string $slug): string
{
    $name = strtolower($requested !== '' ? $requested : $slug);
    $name = preg_replace('/[^a-z0-9_-]+/', '-', $name) ?? '';
    $name = trim($name, '-');
    if ($name === '') {
        $name = 'app';
    }
    return substr($name, 0, 40);
}

/** @return array<string, string> */
function dockyard_env_map(mixed $env): array
{
    if (!is_array($env)) {
        return [];
    }
    $out = [];
    if (array_is_list($env)) {
        foreach ($env as $item) {
            if (is_array($item) && isset($item['name'])) {
                $out[(string) $item['name']] = (string) ($item['value'] ?? '');
            }
        }
        return $out;
    }
    foreach ($env as $key => $value) {
        if (is_string($key) && (is_string($value) || is_int($value) || is_float($value))) {
            $out[$key] = (string) $value;
        }
    }
    return $out;
}

function dockyard_bool(mixed $value): bool
{
    return $value === true || $value === 1 || $value === '1' || $value === 'true';
}

/** @param array<string, mixed> $app */
function dockyard_search_rank(array $app, string $query): int
{
    $q = dockyard_lower(trim($query));
    $slug = dockyard_lower((string) ($app['slug'] ?? ''));
    $title = dockyard_lower((string) ($app['title'] ?? ''));
    if ($slug === $q || $title === $q) {
        return 0;
    }
    if (str_contains($slug, $q) || str_contains($title, $q)) {
        return 1;
    }
    return 2;
}

function dockyard_lower(string $value): string
{
    return function_exists('mb_strtolower') ? mb_strtolower($value, 'UTF-8') : strtolower($value);
}

function dockyard_cut(string $value, int $limit): string
{
    $value = trim(preg_replace('/\s+/', ' ', $value) ?? $value);
    if (function_exists('mb_strlen') && mb_strlen($value, 'UTF-8') > $limit) {
        return mb_substr($value, 0, $limit - 1, 'UTF-8') . '…';
    }
    if (strlen($value) > $limit) {
        return substr($value, 0, $limit - 1) . '…';
    }
    return $value;
}

/** @return list<array<string, mixed>> */
function dockyard_catalog(): array
{
    static $catalog = null;
    if (is_array($catalog)) {
        return $catalog;
    }
    try {
        $decoded = json_decode(dockyard_templates_json(), true, 512, JSON_THROW_ON_ERROR);
    } catch (JsonException) {
        throw new InvalidArgumentException('templates.json nie jest poprawnym JSON.');
    }
    $templates = is_array($decoded) ? ($decoded['templates'] ?? []) : [];
    $catalog = [];
    foreach ($templates as $template) {
        if (!is_array($template)) {
            continue;
        }
        $slug = trim((string) ($template['name'] ?? ''));
        if ($slug === '') {
            $slug = 'id-' . (string) ($template['id'] ?? count($catalog) + 1);
        }
        $catalog[] = [
            'slug' => $slug,
            'title' => (string) ($template['title'] ?? $slug),
            'description' => (string) ($template['description'] ?? ''),
            'category' => (string) (($template['categories'][0] ?? '') ?: ''),
            'kind' => dockyard_kind($template),
            'image' => isset($template['image']) ? (string) $template['image'] : null,
            'template' => $template,
        ];
    }
    return $catalog;
}

/** Treść feedu: z DOCKYARD_TEMPLATES_URL przez cache, a gdy się nie uda, z pliku lokalnego. */
function dockyard_templates_json(): string
{
    $url = getenv('DOCKYARD_TEMPLATES_URL');
    if (is_string($url) && $url !== '') {
        $remote = dockyard_remote_feed($url, dockyard_feed_cache_file($url), DOCKYARD_FEED_TTL, 'dockyard_http_get');
        if ($remote !== null) {
            return $remote;
        }
    }
    $path = dockyard_templates_path();
    if ($path === null) {
        throw new InvalidArgumentException('Brak templates.json. Połóż feed obok index.php albo katalog wyżej, albo ustaw działający DOCKYARD_TEMPLATES_URL.');
    }
    return (string) file_get_contents($path);
}

function dockyard_feed_cache_file(string $url): string
{
    return __DIR__ . DIRECTORY_SEPARATOR . 'cache' . DIRECTORY_SEPARATOR . 'feed-' . hash('sha256', $url) . '.json';
}

/**
 * Świeża kopia z cache, inaczej pobranie, a przy awarii stara kopia. Null, gdy nie ma żadnej.
 *
 * @param callable(string, int): string $fetch
 */
function dockyard_remote_feed(string $url, string $cacheFile, int $ttl, callable $fetch): ?string
{
    $cached = is_file($cacheFile) ? file_get_contents($cacheFile) : false;
    $cached = is_string($cached) && $cached !== '' ? $cached : null;
    if ($cached !== null && time() - (int) filemtime($cacheFile) < $ttl) {
        return $cached;
    }
    try {
        $body = $fetch($url, DOCKYARD_FEED_MAX_BYTES);
        $decoded = json_decode($body, true, 512, JSON_THROW_ON_ERROR);
        if (!is_array($decoded) || !is_array($decoded['templates'] ?? null)) {
            throw new RuntimeException('Feed nie ma listy templates.');
        }
    } catch (RuntimeException | JsonException) {
        if ($cached !== null) {
            // Następna próba za $ttl, żeby każde żądanie nie czekało na niedziałający CDN.
            @touch($cacheFile);
        }
        return $cached;
    }
    dockyard_write_atomic($cacheFile, $body);
    return $body;
}

/** Zapis obok i rename(), żeby równoległe żądanie nie wczytało połowy pliku. */
function dockyard_write_atomic(string $file, string $content): void
{
    $dir = dirname($file);
    if (!is_dir($dir) && !@mkdir($dir, 0775, true)) {
        return;
    }
    $temp = $file . '.' . bin2hex(random_bytes(6)) . '.tmp';
    if (@file_put_contents($temp, $content) === false || !@rename($temp, $file)) {
        @unlink($temp);
    }
}

function dockyard_templates_path(): ?string
{
    $candidates = [];
    $fromEnv = getenv('DOCKYARD_TEMPLATES');
    if (is_string($fromEnv) && $fromEnv !== '') {
        $candidates[] = $fromEnv;
    }
    $candidates[] = __DIR__ . DIRECTORY_SEPARATOR . 'templates.json';
    $candidates[] = dirname(__DIR__) . DIRECTORY_SEPARATOR . 'templates.json';
    foreach ($candidates as $candidate) {
        if (is_file($candidate)) {
            return $candidate;
        }
    }
    return null;
}

/** @param array<string, mixed> $template */
function dockyard_kind(array $template): string
{
    return match ((int) ($template['type'] ?? 0)) {
        1 => 'container',
        2 => 'swarm',
        3 => 'compose',
        4 => 'edge',
        default => 'unknown',
    };
}

/** @return array<string, mixed>|null */
function dockyard_find(string $slug): ?array
{
    $wanted = dockyard_lower($slug);
    $titleHit = null;
    $titleCount = 0;
    foreach (dockyard_catalog() as $app) {
        if (dockyard_lower((string) $app['slug']) === $wanted) {
            return $app;
        }
        if (dockyard_lower((string) $app['title']) === $wanted) {
            $titleHit = $app;
            $titleCount++;
        }
    }
    return $titleCount === 1 ? $titleHit : null;
}

function dockyard_self_test(): int
{
    $failures = 0;
    $check = static function (bool $ok, string $message) use (&$failures): void {
        if ($ok) {
            fwrite(STDOUT, "ok  $message\n");
            return;
        }
        $failures++;
        fwrite(STDERR, "FAIL $message\n");
    };

    $init = dockyard_dispatch([
        'jsonrpc' => '2.0',
        'id' => 1,
        'method' => 'initialize',
        'params' => ['protocolVersion' => '2025-03-26', 'capabilities' => [], 'clientInfo' => ['name' => 'test', 'version' => '0']],
    ]);
    $instructions = (string) ($init['result']['instructions'] ?? '');
    $check(str_contains($instructions, 'PORTAINER_API_KEY'), 'instrukcja agenta wspomina klucz Portainera');
    $check(str_contains($instructions, 'local_secrets'), 'instrukcja agenta wspomina local_secrets');
    $check(str_contains($instructions, 'ready'), 'instrukcja agenta mówi o ready');

    $tools = dockyard_dispatch(['jsonrpc' => '2.0', 'id' => 2, 'method' => 'tools/list']);
    $names = array_column($tools['result']['tools'] ?? [], 'name');
    $check($names === ['list_apps', 'get_app', 'prepare_deploy'], 'lista narzędzi');

    $note = dockyard_dispatch(['jsonrpc' => '2.0', 'method' => 'notifications/initialized']);
    $check($note === null, 'powiadomienie nie dostaje odpowiedzi JSON-RPC');

    $listed = dockyard_list_apps(['query' => 'n8n', 'limit' => 5]);
    $check(($listed['total'] ?? 0) >= 1 && ($listed['apps'][0]['slug'] ?? '') === 'n8n', 'list_apps znajduje n8n');

    $adguard = dockyard_get_app(['slug' => 'adguard']);
    $check(($adguard['image'] ?? '') === 'adguard/adguardhome:latest', 'get_app adguard ma obraz');

    $blocked = dockyard_prepare_deploy(['slug' => 'adguard']);
    $check(($blocked['ready'] ?? true) === false, 'adguard bez confirm nie jest ready');

    $dockerPlan = dockyard_prepare_deploy(['slug' => 'adguard', 'confirm' => true]);
    $check(($dockerPlan['ready'] ?? false) === true, 'adguard z confirm jest ready');
    $check(str_contains((string) $dockerPlan['docker']['compose'], './data/Adguard/Workdir'), 'docker zamienia ścieżkę Portainera');
    $check(!str_contains((string) $dockerPlan['docker']['compose'], DOCKYARD_PORTAINER_PREFIX), 'plan dockera nie zostawia prefiksu Portainera');
    $check(str_contains((string) $dockerPlan['portainer']['body']['stackFileContent'], DOCKYARD_PORTAINER_PREFIX . '/Adguard/Workdir'), 'plan portainera zostawia ścieżkę z feedu');
    $check($dockerPlan['portainer']['headers']['X-API-Key'] === '{PORTAINER_API_KEY}', 'klucz Portainera jest placeholderem');
    $check($dockerPlan['portainer']['body']['fromAppTemplate'] === false, 'fromAppTemplate jest false');
    $check($dockerPlan['docker']['up'][0] === 'docker', 'komenda dockera jest tablicą argumentów');
    $check(($dockerPlan['suggested_url'] ?? '') === 'http://localhost:80', 'adguard proponuje port 80');

    $n8nBlocked = dockyard_prepare_deploy(['slug' => 'n8n', 'confirm' => true]);
    $check(($n8nBlocked['ready'] ?? true) === false, 'n8n z hasłem domyślnym nie jest ready');
    $check(
        array_filter($n8nBlocked['blockers'], static fn ($item) => str_contains((string) $item, 'N8N_BASIC_AUTH_PASSWORD')) !== [],
        'blocker wymienia hasło n8n'
    );

    $n8n = dockyard_prepare_deploy([
        'slug' => 'n8n',
        'confirm' => true,
        'local_secrets' => ['N8N_DB_PASSWORD', 'N8N_BASIC_AUTH_PASSWORD'],
    ]);
    $check(($n8n['ready'] ?? false) === true, 'n8n z local_secrets jest ready');
    $check(str_contains((string) $n8n['docker']['env_file'], 'N8N_BASIC_AUTH_PASSWORD=CHANGEME'), 'env ma CHANGEME');
    $check(str_contains((string) $n8n['docker']['compose'], 'n8nio/n8n'), 'lokalny stackfile n8n wszedł do planu');
    $check(($n8n['suggested_url'] ?? '') === 'http://localhost:5678', 'n8n proponuje port 5678');
    $check(!str_contains(json_encode($n8n['portainer']['headers']), 'ptr_'), 'odpowiedź nie zawiera prawdziwego klucza');

    $windows = dockyard_prepare_deploy(['slug' => 'dockur-windows', 'confirm' => true]);
    $check(($windows['ready'] ?? true) === false, 'privileged bez zgody blokuje plan');
    $windowsOk = dockyard_prepare_deploy([
        'slug' => 'dockur-windows',
        'confirm' => true,
        'allow_privileged' => true,
        'local_secrets' => ['PASSWORD'],
    ]);
    $check(($windowsOk['ready'] ?? false) === true, 'privileged z osobną zgodą przechodzi');

    $check(dockyard_stack_url('https://github.com/bauerpawel/DOCKYARD', 'stacks/n8n/docker-compose.yml') === 'https://raw.githubusercontent.com/bauerpawel/DOCKYARD/HEAD/stacks/n8n/docker-compose.yml', 'url stackfile z GitHuba');
    $check(dockyard_stack_url('https://github.com/a/b', '../etc/passwd') === null, 'ścieżka ze .. odpada');
    $check(dockyard_stack_url('https://evil.example/repo', 'a.yml') === null, 'obcy host odpada');
    $rejected = false;
    try {
        dockyard_assert_public_url('http://127.0.0.1/stack.yml');
    } catch (RuntimeException) {
        $rejected = true;
    }
    $check($rejected, 'adres wewnętrzny odpada');

    foreach (['DB_PASS', 'PASS', 'GOTIFY_DEFAULTUSER_PASS', 'adminpass', 'ADMIN_PWD', 'ENCRYPTION_KEY', 'APP_KEY', 'RUSTFS_ACCESS_KEY', 'FERNETKEY', 'JWT_SECRET', 'N8N_BASIC_AUTH_PASSWORD'] as $name) {
        $check(dockyard_is_secret($name), "$name jest sekretem");
    }
    foreach (['PASSBOLT_PORT', 'PUBLIC_KEY', 'VAPID_PUBLIC_KEY', 'KEYBOARD', 'KEYFILE', 'USER_PASSWORD_FILE', 'N8N_BASIC_AUTH_USER', 'TZ'] as $name) {
        $check(!dockyard_is_secret($name), "$name nie jest sekretem");
    }

    $gotify = dockyard_prepare_deploy(['slug' => 'gotify', 'confirm' => true]);
    $check(($gotify['ready'] ?? true) === false, 'gotify z hasłem admin123 nie jest ready');
    $check(
        array_filter($gotify['blockers'] ?? [], static fn ($item) => str_contains((string) $item, 'GOTIFY_DEFAULTUSER_PASS')) !== [],
        'blocker wymienia hasło gotify'
    );
    $gotifyApp = dockyard_get_app(['slug' => 'gotify']);
    $gotifyPass = array_values(array_filter($gotifyApp['env'] ?? [], static fn ($item) => $item['name'] === 'GOTIFY_DEFAULTUSER_PASS'));
    $check(($gotifyPass[0]['secret'] ?? false) === true, 'get_app oznacza hasło gotify jako sekret');

    $nzbget = dockyard_prepare_deploy(['slug' => 'nzbget', 'confirm' => true, 'local_secrets' => ['NZBGET_PASS']]);
    $check(($nzbget['ready'] ?? false) === true, 'nzbget z local_secrets jest ready');
    $check(str_contains((string) ($nzbget['docker']['env_file'] ?? ''), 'NZBGET_PASS=CHANGEME'), 'hasło nzbget jest CHANGEME');
    $check(!str_contains((string) ($nzbget['docker']['env_file'] ?? ''), 'tegbzn6789'), 'domyślne hasło nzbget nie trafia do planu');

    $n8nUser = dockyard_prepare_deploy([
        'slug' => 'n8n',
        'confirm' => true,
        'local_secrets' => ['N8N_DB_PASSWORD', 'N8N_BASIC_AUTH_PASSWORD', 'N8N_BASIC_AUTH_USER'],
    ]);
    $check(str_contains((string) ($n8nUser['docker']['env_file'] ?? ''), 'N8N_BASIC_AUTH_USER=CHANGEME'), 'local_secrets działa też dla zmiennej spoza reguły');
    $check(in_array('N8N_BASIC_AUTH_USER', $n8nUser['secrets_to_set'] ?? [], true), 'secrets_to_set wymienia zmienną z local_secrets');

    $baserow = dockyard_prepare_deploy(['slug' => 'baserow-container', 'confirm' => true]);
    $check(array_key_exists('suggested_url', $baserow) && $baserow['suggested_url'] === null, 'port bez portu hosta nie daje suggested_url');
    $check(
        array_filter($baserow['warnings'] ?? [], static fn ($item) => str_contains((string) $item, '1024')) === [],
        'port bez portu hosta nie ostrzega o porcie poniżej 1024'
    );
    $check(
        array_filter($baserow['warnings'] ?? [], static fn ($item) => str_contains((string) $item, 'losow')) !== [],
        'ostrzeżenie o losowym porcie hosta'
    );

    $newer = dockyard_dispatch(['jsonrpc' => '2.0', 'id' => 3, 'method' => 'initialize', 'params' => ['protocolVersion' => '2099-01-01']]);
    $check(($newer['result']['protocolVersion'] ?? '') === '2025-06-18', 'nieznana wersja protokołu dostaje najnowszą obsługiwaną');
    $older = dockyard_dispatch(['jsonrpc' => '2.0', 'id' => 4, 'method' => 'initialize', 'params' => ['protocolVersion' => '2025-03-26']]);
    $check(($older['result']['protocolVersion'] ?? '') === '2025-03-26', 'obsługiwana starsza wersja protokołu zostaje');

    $check(dockyard_dispatch(['jsonrpc' => '2.0', 'id' => 5, 'result' => []]) === null, 'odpowiedź klienta nie dostaje odpowiedzi');
    $check(dockyard_dispatch(['jsonrpc' => '2.0', 'id' => 6, 'error' => ['code' => -1, 'message' => 'x']]) === null, 'błąd od klienta nie dostaje odpowiedzi');

    $check((dockyard_list_apps(['limit' => 'abc'])['limit'] ?? 0) === 20, 'limit spoza liczb daje domyślne 20');

    $memory = static function (string $data) {
        $stream = fopen('php://memory', 'w+b');
        fwrite($stream, $data);
        rewind($stream);
        return $stream;
    };
    $check(dockyard_read_limited($memory(str_repeat('a', 10)), 10) === str_repeat('a', 10), 'odczyt do limitu zwraca całość');
    $tooBig = false;
    try {
        dockyard_read_limited($memory(str_repeat('a', 11)), 10);
    } catch (RuntimeException) {
        $tooBig = true;
    }
    $check($tooBig, 'odczyt ponad limit odpada');

    $localFeed = (string) file_get_contents((string) dockyard_templates_path());
    $oldFeed = '{"version":"3","templates":[{"name":"stary"}]}';
    $newFeed = '{"version":"3","templates":[{"name":"nowy"}]}';
    $feedFile = sys_get_temp_dir() . DIRECTORY_SEPARATOR . 'dockyard-feed-' . bin2hex(random_bytes(6)) . '.json';
    $fetches = 0;
    $serve = static function (string $body) use (&$fetches): callable {
        return static function (string $url, int $max) use ($body, &$fetches): string {
            $fetches++;
            return $body;
        };
    };
    $failing = static function (string $url, int $max) use (&$fetches): string {
        $fetches++;
        throw new RuntimeException('CDN nie odpowiada');
    };
    $stale = static function () use ($feedFile, $oldFeed): void {
        file_put_contents($feedFile, $oldFeed);
        touch($feedFile, time() - DOCKYARD_FEED_TTL - 60);
        clearstatcache();
    };

    $realSize = static function (string $url, int $max) use ($memory, $localFeed): string {
        return dockyard_read_limited($memory($localFeed), $max);
    };
    $check(dockyard_remote_feed('https://cdn.example/t.json', $feedFile, DOCKYARD_FEED_TTL, $realSize) === $localFeed, 'feed wielkości templates.json mieści się w limicie');
    @unlink($feedFile);
    $oversized = static function (string $url, int $max) use ($memory): string {
        return dockyard_read_limited($memory('{"templates":[]}' . str_repeat(' ', $max)), $max);
    };
    $check(dockyard_remote_feed('https://cdn.example/t.json', $feedFile, DOCKYARD_FEED_TTL, $oversized) === null, 'za duży feed odpada');

    file_put_contents($feedFile, $oldFeed);
    $fetches = 0;
    $check(dockyard_remote_feed('https://cdn.example/t.json', $feedFile, DOCKYARD_FEED_TTL, $serve($newFeed)) === $oldFeed, 'świeża kopia z cache');
    $check($fetches === 0, 'świeża kopia nie pobiera feedu');

    $stale();
    $check(dockyard_remote_feed('https://cdn.example/t.json', $feedFile, DOCKYARD_FEED_TTL, $serve($newFeed)) === $newFeed, 'przeterminowana kopia jest odświeżana');
    $check(file_get_contents($feedFile) === $newFeed, 'odświeżony feed trafia do cache');

    $stale();
    $fetches = 0;
    $check(dockyard_remote_feed('https://cdn.example/t.json', $feedFile, DOCKYARD_FEED_TTL, $failing) === $oldFeed, 'awaria CDN zwraca starą kopię');
    clearstatcache();
    dockyard_remote_feed('https://cdn.example/t.json', $feedFile, DOCKYARD_FEED_TTL, $failing);
    $check($fetches === 1, 'po awarii CDN kolejne żądanie nie czeka na CDN');

    $stale();
    $check(dockyard_remote_feed('https://cdn.example/t.json', $feedFile, DOCKYARD_FEED_TTL, $serve('<html>błąd</html>')) === $oldFeed, 'niepoprawny feed daje starą kopię');
    $check(file_get_contents($feedFile) === $oldFeed, 'niepoprawny feed nie nadpisuje cache');
    $stale();
    $check(dockyard_remote_feed('https://cdn.example/t.json', $feedFile, DOCKYARD_FEED_TTL, $serve('{"message":"Not Found"}')) === $oldFeed, 'JSON bez listy templates daje starą kopię');

    @unlink($feedFile);
    $check(dockyard_remote_feed('https://cdn.example/t.json', $feedFile, DOCKYARD_FEED_TTL, $failing) === null, 'awaria CDN bez cache daje null');
    @unlink($feedFile);

    $previousUrl = getenv('DOCKYARD_TEMPLATES_URL');
    $testUrl = 'https://cdn.jsdelivr.net/gh/dockyard-self-test/feed-' . bin2hex(random_bytes(6)) . '@main/templates.json';
    $testCache = dockyard_feed_cache_file($testUrl);
    $cacheDirExisted = is_dir(dirname($testCache));
    if (!$cacheDirExisted) {
        mkdir(dirname($testCache), 0775, true);
    }
    file_put_contents($testCache, $newFeed);
    putenv('DOCKYARD_TEMPLATES_URL=' . $testUrl);
    $check(dockyard_templates_json() === $newFeed, 'DOCKYARD_TEMPLATES_URL bierze feed z cache CDN');
    putenv('DOCKYARD_TEMPLATES_URL=http://127.0.0.1/templates.json');
    $check(dockyard_templates_json() === $localFeed, 'niedostępny DOCKYARD_TEMPLATES_URL wraca do pliku lokalnego');
    putenv($previousUrl === false ? 'DOCKYARD_TEMPLATES_URL' : 'DOCKYARD_TEMPLATES_URL=' . $previousUrl);
    @unlink($testCache);
    if (!$cacheDirExisted) {
        @rmdir(dirname($testCache));
    }

    if ($failures === 0) {
        fwrite(STDOUT, "self-test ok\n");
        return 0;
    }
    fwrite(STDERR, "self-test failures: $failures\n");
    return 1;
}

dockyard_main();
