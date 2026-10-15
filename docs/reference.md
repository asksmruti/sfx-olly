# User Reference

A modular Python package to:

- **Query** Splunk Observability Cloud (SignalFx) REST APIs: metrics, dimensions, MTS, raw time series, SignalFlow, detectors and incidents.
- **Receive** detector alert **webhooks**, verify their signature, and **display them formatted** in the terminal (and optionally store them as JSON Lines).
- Use everything from a **CLI** (`sfx-olly`) or as a **library** in your own code.

---

## Contents

1. [Project structure](#project-structure)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [CLI usage](#cli-usage)
5. [Webhook receiver](#webhook-receiver)
6. [Library usage](#library-usage)
7. [Extending](#extending)
8. [Security](#security)
9. [Scaling](#scaling)
10. [Troubleshooting](#troubleshooting)
11. [License](#license)

New to these options? Start with the **[Command Guide](https://github.com/asksmruti/sfx-olly/blob/main/docs/command-guide.md)**.
It explains metrics and dimensions, range versus resolution, rollup versus aggregation
versus time transforms, every query option, and step-by-step project-size examples.

All metric, project, host, topic, and environment values in the examples are fictional.
For example, `example.project.size`, `example.bytes.total`, `project-demo`, and
`env-test` are placeholders, not built-in metrics. Replace them with names discovered
in your own organization. Never substitute real credentials into committed examples.

---

## Project structure

```text
sfx_olly/
├── __init__.py          # exports SplunkOllyClient
├── __main__.py          # python -m sfx_olly
├── config.py            # typed settings from env/.env (ApiSettings, WebhookSettings, LoggingSettings)
├── exceptions.py        # ApiError, AuthenticationError, NotFoundError, RateLimitError, SignalFlowError
├── logging_config.py    # text/JSON logging with secret redaction
├── utils.py             # durations, time ranges, validation helpers
├── help.py              # built-in help topics (sfx-olly help <topic>)
├── api/
│   ├── http.py          # shared HTTP transport: auth, TLS, retries, error mapping
│   ├── base.py          # BaseAPI + pagination
│   ├── alerts.py        # detectors, incidents
│   └── client.py        # SplunkOllyClient facade
├── metrics/
│   ├── __init__.py      # public metric API exports
│   ├── metadata.py      # metric/MTS search and dimension inspection
│   ├── timeseries.py    # /v1/timeserieswindow
│   ├── query_builder.py # MetricQuery -> safe SignalFlow program
│   └── signalflow.py    # one-shot SignalFlow execution (SSE)
├── webhook/
│   ├── models.py        # AlertPayload (pydantic)
│   ├── security.py      # HMAC signature, IP allowlist, replay guard
│   ├── formatter.py     # rich terminal rendering
│   ├── handlers.py      # pluggable sinks: console, JSONL file
│   ├── app.py           # FastAPI app factory
│   ├── server.py        # uvicorn runner
│   └── testing.py       # signed sample alert sender
└── cli/
    ├── main.py          # argument parser + error handling
    ├── output.py        # table / JSON output
    ├── metadata.py      # metrics, dimensions, mts commands
    ├── data.py          # query, timeseries, signalflow commands
    ├── alerts.py        # detectors, incidents commands
    ├── webhook.py       # webhook serve / send-test / render
    └── help_cmd.py      # help command
```

Each layer only depends on the one below it: **CLI → API/Webhook → config/utils**. You can reuse the API or webhook modules without the CLI.

See [Architecture](https://github.com/asksmruti/sfx-olly/blob/main/docs/architecture.md) for every module's responsibility, call flows,
and the plan for adding traces or other signals without mixing their APIs with metrics.
Metric-specific imports now live in `sfx_olly.metrics`; existing `from sfx_olly.api import MetricQuery`
and `client.metadata` / `client.signalflow` / `client.timeseries` still work.
Direct imports such as `sfx_olly.api.query_builder` must change to `sfx_olly.metrics.query_builder`.

There is no watcher, local polling loop, state baseline, or `WATCH_*` configuration.
Each discovery/query command runs once and exits. SSE delivers one query's results;
it is not repeated polling for a metric to appear.

---

## Installation

Requires **Python 3.10+**.

```bash
cd signalfx-playground
python3 -m venv .venv
source .venv/bin/activate
pip install -e .                 # installs the `sfx-olly` command
# or: pip install -r requirements.txt   (then use `python -m sfx_olly`)
```

---

## Configuration

All configuration is external. Values are read from **environment variables**, or from a **`.env`** file in the working directory. Real environment variables take precedence over `.env`.

```bash
cp .env.example .env
# edit .env: set SFX_TOKEN, SFX_REALM (and WEBHOOK_SHARED_SECRET for webhooks)
```

### API settings (`SFX_`)

| Variable | Default | Description |
| --- | --- | --- |
| `SFX_TOKEN` | **required** | API access token (user API token or org token with API scope). Sent as `X-SF-Token`. |
| `SFX_REALM` | `us1` | Your org realm: `us0`, `us1`, `us2`, `eu0`, `eu1`, `eu2`, `jp0`, `au0`... |
| `SFX_TIMEOUT_SECONDS` | `30` | Per-request timeout. |
| `SFX_MAX_RETRIES` | `3` | Retries on 429/500/502/503/504. Honours `Retry-After`. |
| `SFX_BACKOFF_FACTOR` | `0.5` | Exponential backoff factor between retries. |
| `SFX_POOL_MAXSIZE` | `10` | HTTP connection pool size. |
| `SFX_CA_BUNDLE` | – | Path to a custom CA bundle (e.g. corporate TLS proxy). |
| `SFX_API_BASE_URL` | derived from realm | Override API URL (must be `https://`). |
| `SFX_STREAM_BASE_URL` | derived from realm | Override SignalFlow stream URL (must be `https://`). |

### Logging (`LOG_`)

| Variable | Default | Description |
| --- | --- | --- |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `LOG_FORMAT` | `text` | `text` or `json` (for log aggregation) |

### Webhook settings (`WEBHOOK_`)

See [Webhook receiver](#webhook-receiver).

---

## CLI usage

For detailed explanations and worked numeric examples, read the
[beginner-friendly Command Guide](https://github.com/asksmruti/sfx-olly/blob/main/docs/command-guide.md). In particular:

- [Range](https://github.com/asksmruti/sfx-olly/blob/main/docs/command-guide.md#range-how-far-back-to-look): which historical period to query.
- [Resolution](https://github.com/asksmruti/sfx-olly/blob/main/docs/command-guide.md#resolution-the-size-of-a-time-bucket): how finely to divide time.
- [Rollup](https://github.com/asksmruti/sfx-olly/blob/main/docs/command-guide.md#rollup-samples-inside-one-bucket): combine one series' samples inside a bucket.
- [Aggregation](https://github.com/asksmruti/sfx-olly/blob/main/docs/command-guide.md#aggregation-combine-different-series): combine different series at each timestamp.
- [Grouping](https://github.com/asksmruti/sfx-olly/blob/main/docs/command-guide.md#grouping-one-answer-per-project-or-host): calculate separately per project or host.
- [Transform](https://github.com/asksmruti/sfx-olly/blob/main/docs/command-guide.md#transform-calculate-over-time): calculate over a moving time window.
- [Your project-size query](https://github.com/asksmruti/sfx-olly/blob/main/docs/command-guide.md#your-project-size-query-step-by-step): build and understand the command one step at a time.

```bash
sfx-olly --help                # all commands
sfx-olly <command> -h          # options for one command
sfx-olly help                  # list help topics
sfx-olly help webhook          # detailed guide for one topic
```

Global options:

| Option | Description |
| --- | --- |
| `-o table` (default) | Human-readable tables |
| `-o json` | Raw API JSON (pipe to `jq`) |
| `-v`, `--verbose` | Print each API endpoint (with query params), request body (e.g. SignalFlow) and response status/timing to stderr. The token is never printed. Put it before the command: `sfx-olly -v query ...` |
| `--version` | Show version |

### Help module

The built-in help works offline and needs no token:

| Topic | Covers |
| --- | --- |
| `quickstart` | Install, configure, first query |
| `config` | Environment variables |
| `metrics` | Metric / dimension / MTS search |
| `query` | Fetch values of any metric (generic, no SignalFlow needed) |
| `timeseries` | Raw datapoints |
| `signalflow` | SignalFlow programs |
| `alerts` | Detectors and incidents |
| `webhook` | Webhook receiver setup |
| `security` | Security controls |
| `library` | Using the package from Python |

```bash
sfx-olly help signalflow
```

### Metrics, dimensions and MTS metadata

These commands return **metadata** (names, types, dimensions), not values. Search endpoints use `field:value` syntax. A bare term gets a default field added: `metrics` uses `name:`, `dimensions` uses `key:`, and `mts`/`timeseries` use `sf_metric:`.

```bash
sfx-olly metrics search example.bytes.total          # = name:example.bytes.total
sfx-olly metrics search "example.*" --limit 20
sfx-olly mts search "sf_metric:example.bytes.total AND environment:env-prod"
```

### Discover a metric and its dimensions

```bash
sfx-olly metrics search                         # indexed metric names (first 50)
sfx-olly metrics search 'example.*' --limit 100
sfx-olly metrics get example.project.size            # metric metadata, including type
sfx-olly metrics inspect example.project.size        # dimension keys -> observed values
sfx-olly -o json metrics inspect example.project.size
sfx-olly mts search 'sf_metric:example.project.size AND environment:env-test'
```

`inspect` reads at most 1,000 series by default, once. Increase `--limit` up to 10,000.
It labels partial inventories; a value missing from a partial inventory is not proof of absence.
The tree shows 10 values per key; JSON includes all values from the inspected series.
Use `--offset` / `--limit` on searches to view subsequent pages (offset + limit <= 10,000).

Think **metric name -> series -> dimension key/value set -> timestamped values**.
Dimensions are actually a flat map: `environment` and `deployment.environment.name`
are distinct literal keys, not aliases or nested objects. The tree groups observed values
for readability; it does not imply that every combination of values exists.
Use `mts search` to see the dimensions that occur together on each series.

### Missing metrics and alternatives to polling

An API cannot list names that have never been sent: there is no inventory of all possible
future metrics. Compare an expected-name list from your application/collector configuration
against `metrics search` results to identify missing expected names. Search/get are one-shot checks:

```bash
sfx-olly metrics search 'name:expected.metric.name'
sfx-olly mts search 'sf_metric:expected.metric.name'
sfx-olly query expected.metric.name --range 2d --latest
```

These answer different questions: indexed name, indexed series, and values within a time window.
A retained metadata entry does not mean a metric is reporting now. No datapoints can also mean
a wrong filter, time range, realm/org, token visibility, or rollup. It does not establish that
the metric never existed. There is no `metrics search --unavailable` catalog.

For notification without a local watcher, configure a **Splunk-managed detector** on a known
metric/heartbeat and send its alerts to this package's webhook receiver. Use a no-data condition
for a stream that stops reporting, or an appropriate presence/value condition for a known stream
that starts reporting. A zero value may be valid, so do not equate zero with absence.
For arbitrary new metric names, a detector/webhook is not a general metric-catalog change feed;
the producer/collector must emit an explicit registration/event if you need that behavior
without catalog polling. The receiver alone cannot detect new metric names.

### Generic metric query (values for any metric)

`query` turns options into a SignalFlow program, runs it, and prints the results. This is the generic way to get the values of any metric.

```bash
sfx-olly query example.bytes.total
sfx-olly query example.bytes.total --filter environment=env-prod --filter 'topic=*' --agg mean
sfx-olly query example.bytes.total --rollup delta --agg sum --by topic \
    --transform sum --over 1d --range 1d --resolution 1h --latest
sfx-olly query cpu.utilization --filter host=web-01,web-02 --exclude env=dev --agg max --by host --show-program
sfx-olly query cpu.utilization --agg mean --dry-run        # print SignalFlow only
```

| Option | Meaning |
| --- | --- |
| `--filter KEY=V[,V]` | Keep series whose dimension matches. Repeat the option for AND. Commas mean OR. `*` is a wildcard. |
| `--exclude KEY=V[,V]` | Drop series whose dimension matches. |
| `--rollup` | How raw points roll up: `average`, `sum`, `min`, `max`, `count`, `delta`, `rate`, `latest`, `lag` |
| `--agg` / `--by DIM` | Aggregate across series (`mean`, `sum`, `min`, `max`, `count`, `median`, `stddev`, `variance`), optionally grouped by a dimension. |
| `--transform` / `--over` | Aggregate over a time window, e.g. `--transform sum --over 1d`. |
| `--range` / `--resolution` | Look-back window and data granularity. |
| `--latest` | Show only the latest value per series. |
| `--unit` | How values are displayed: `raw` (default), `bytes` (auto B/KiB/MiB/GiB), `kib`, `mib`, `gib`. Tables only; `-o json` stays raw. |
| `--show-program` / `--dry-run` | Print the generated SignalFlow (`--dry-run` doesn't call the API). |

The same thing from Python:

```python
from sfx_olly import SplunkOllyClient
from sfx_olly.api import MetricQuery
from sfx_olly.utils import time_range

spec = MetricQuery(
    metric="example.bytes.total",
    filters={"environment": ["env-prod"]},
    rollup="delta", aggregation="sum", group_by=["topic"],
    transform="sum", window="1d",
)
start, end = time_range("1d")
with SplunkOllyClient() as client:
    for p in client.signalflow.query(spec, start, end, resolution_ms=3_600_000):
        print(p.timestamp_ms, p.properties.get("topic"), p.value)
```

The builder only accepts known functions and validated metric, dimension and window names. Filter values containing quotes, backslashes or control characters are rejected, so user input can't inject SignalFlow code.

### Metric types and other signals

Nothing is hardcoded to example telemetry, project-size, CPU, or a specific environment. The same builder works
with queryable numeric metric series and their actual dimension keys, subject to the input
validation above and API permissions. It does **not** choose the correct metric semantics for you:

| Metric representation | Query guidance |
| --- | --- |
| Gauge (size, temperature, utilization) | Read values; choose average/min/max/latest rollup to match the chart. |
| Counter / cumulative counter | Choose delta or rate when appropriate to the source's counter semantics; match the dashboard. A sum of cumulative readings is usually not a total increase. |
| Histogram / summary exported as numeric bucket, count, sum series | Query the exported numeric series; bucket counts are not automatically percentiles. |
| Native distribution or specialized analytics | Not guaranteed by this simple numeric builder. Use supported custom SignalFlow or add a distribution-specific API after checking the metric format. |
| APM-derived metrics | Work if exposed as ordinary metrics in the metric catalog; use their actual dimension keys. |
| Raw traces, logs, profiles, events | Not metric datapoints. These need their own signal-specific API modules and are not implemented here. |

The `--unit` flag only formats numbers; it does not infer whether a metric is bytes, a count,
or a percentage. Do not use `--unit bytes` unless the source value is measured in bytes.

### More metadata examples

```bash
sfx-olly metrics search "name:cpu.*" --limit 20
sfx-olly metrics search "name:*memory*" --limit 50 --offset 50
sfx-olly metrics get cpu.utilization
sfx-olly dimensions search "key:host" --limit 100
sfx-olly mts search "sf_metric:cpu.utilization AND host:web-01"
sfx-olly -o json metrics search "name:disk.*" | jq '.results[].name'
```

### Raw time series

```bash
sfx-olly timeseries "sf_metric:cpu.utilization" --range 15m --resolution 1m
sfx-olly timeseries "sf_metric:cpu.utilization AND host:web-01" --range 1h --resolution 5m --last 12
```

| Option | Default | Description |
| --- | --- | --- |
| `--range` | `15m` | Look-back window: `30s`, `15m`, `1h`, `7d`, `2w` |
| `--resolution` | `1m` | Rollup resolution |
| `--last` | `5` | Points shown per series (table mode only) |

### SignalFlow

```bash
sfx-olly signalflow "data('cpu.utilization').mean(by=['host']).publish()" --range 30m
sfx-olly signalflow "data('memory.utilization', filter=filter('env','prod')).max().publish()" --range 1h --resolution 5m
sfx-olly signalflow --file program.flow --range 1h
```

### cURL POST: execute the same query

This is the **SignalFlow execute API** used by `sfx-olly query`, not a metric-ingestion API
or the local alert receiver. Export `SFX_TOKEN` and `SFX_REALM` in your shell first;
cURL does not load `.env` automatically. Use an API-scoped token for the same org as the dashboard.
The example assumes a fictional metric with an `environment` dimension:

```bash
export SFX_REALM=us1
STOP_MS="$(($(date +%s) * 1000))"
START_MS="$((STOP_MS - 2 * 24 * 60 * 60 * 1000))"
curl --fail-with-body --no-buffer --request POST \
    "${SFX_STREAM_BASE_URL:-https://stream.${SFX_REALM}.signalfx.com}/v2/signalflow/execute?start=${START_MS}&stop=${STOP_MS}&resolution=60000&immediate=true" \
    --header "X-SF-Token: ${SFX_TOKEN:?Export SFX_TOKEN first}" \
    --header 'Content-Type: text/plain' \
    --header 'Accept: text/event-stream' \
    --data-binary "data('example.project.size', filter=filter('environment', 'env-test')).publish(label='A')"
```

The response is SSE (`event:` / `data:` blocks), not one JSON document. `start` and `stop`
are Unix milliseconds. `immediate=true` returns available historical data without waiting
for future samples. Do not use `-k` or `-L`; optionally supply `--cacert "$SFX_CA_BUNDLE"`
for a corporate CA. See the [SignalFlow API reference](https://dev.splunk.com/observability/reference/api/signalflow/latest).
For the separate inbound webhook POST, see [signed cURL testing](#signed-curl-testing).

### Detectors and incidents

```bash
sfx-olly detectors list --name "CPU" --limit 20
sfx-olly detectors list --tag production
sfx-olly detectors get <detectorId>
sfx-olly incidents list
sfx-olly incidents list --include-resolved --limit 100
sfx-olly incidents get <incidentId>
```

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success |
| `1` | API error (auth, not found, rate limit, server error) |
| `2` | Invalid input or configuration |
| `130` | Interrupted (Ctrl+C) |

---

## Webhook receiver

Splunk Observability can POST a JSON notification to your endpoint whenever a detector triggers or clears. The receiver checks each request, replies `200` straight away, and passes the alert to one or more **handlers**. By default the console handler shows it as a formatted panel.

### 1. Configure

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"   # generate secret
```

In `.env` in the project directory, replace the placeholder with the generated value:

```dotenv
WEBHOOK_SHARED_SECRET=<generated value>
WEBHOOK_REQUIRE_SIGNATURE=true
WEBHOOK_OUTPUT_FILE=./data/alerts.jsonl     # optional: also store alerts
```

Run `sfx-olly webhook serve` from that directory so it can find `.env`. Configure
the same secret in Splunk's webhook integration. Do not share the secret or commit `.env`.

#### Missing shared-secret error

If startup reports:

```text
WEBHOOK_SHARED_SECRET is required when WEBHOOK_REQUIRE_SIGNATURE=true
```

the receiver has no non-empty secret configured. Generate and set it as shown above,
then start the receiver again. Keep signature verification enabled, especially when
exposing the receiver through a public URL.

Environment variables override `.env`. If the error persists after updating `.env`,
an empty exported variable may be overriding it. Remove that shell override and restart:

```bash
unset WEBHOOK_SHARED_SECRET
sfx-olly webhook serve
```

| Variable | Default | Description |
| --- | --- | --- |
| `WEBHOOK_HOST` | `127.0.0.1` | Bind address. Use `0.0.0.0` inside containers. |
| `WEBHOOK_PORT` | `8080` | Listen port. |
| `WEBHOOK_PATH` | `/webhooks/splunk` | Endpoint path. |
| `WEBHOOK_WORKERS` | `1` | Uvicorn worker processes. |
| `WEBHOOK_SHARED_SECRET` | – | Must match the "Shared secret" in the Splunk integration. |
| `WEBHOOK_REQUIRE_SIGNATURE` | `true` | Refuse to start without a secret. Set `false` only for local experiments. |
| `WEBHOOK_MAX_BODY_BYTES` | `262144` | Reject larger bodies with `413`. |
| `WEBHOOK_ALLOWED_CIDRS` | – | Comma-separated source allowlist, e.g. `10.0.0.0/8,203.0.113.0/24`. |
| `WEBHOOK_TRUST_PROXY_HEADERS` | `false` | Use `X-Forwarded-For` (only behind a trusted proxy). |
| `WEBHOOK_FORWARDED_ALLOW_IPS` | `127.0.0.1` | Proxy IPs whose forwarded headers are trusted. |
| `WEBHOOK_DEDUPE_TTL_SECONDS` | `300` | Ignore repeated deliveries of the same event (`0` disables). |
| `WEBHOOK_CONSOLE_OUTPUT` | `true` | Print formatted alerts to stdout. |
| `WEBHOOK_OUTPUT_FILE` | – | Append alerts as JSON Lines (file mode `0600`). |
| `WEBHOOK_SSL_CERTFILE` / `WEBHOOK_SSL_KEYFILE` | – | Serve HTTPS directly instead of via a proxy. |

### 2. Run and test locally

```bash
# terminal 1
sfx-olly webhook serve

# terminal 2 — send a signed sample alert
sfx-olly webhook send-test
sfx-olly webhook send-test --state ok
sfx-olly webhook send-test --file my-payload.json
```

`webhook serve` starts a listener that verifies, displays, and optionally saves incoming
notifications. It does not create detectors or trigger alerts in Splunk.
`webhook send-test` sends a synthetic **Critical: CPU above 90% on web-01** alert
by default. That sample is not a real Splunk incident and need not match any detector
you configured. Its incident ID starts with `TEST`.

The default test URL is localhost, so a successful local test does not verify ngrok
or Splunk delivery. Continue with the [end-to-end webhook test](#end-to-end-webhook-test).

### Signed cURL testing

For the **local receiver API**, start `sfx-olly webhook serve`, then export
`WEBHOOK_SHARED_SECRET` in the calling shell with the same value as the receiver.
Sign the exact body sent; this does not use `SFX_TOKEN`:

```bash
BODY='{"incidentId":"curl-test","status":"anomalous","severity":"Critical","detector":"cURL test","messageTitle":"Test alert"}'
SIGNATURE="$(printf '%s' "$BODY" | python -c 'import base64, hashlib, hmac, os, sys; print(base64.b64encode(hmac.new(os.environ["WEBHOOK_SHARED_SECRET"].encode(), sys.stdin.buffer.read(), hashlib.sha256).digest()).decode())')"
curl --fail-with-body --request POST \
    'http://127.0.0.1:8080/webhooks/splunk' \
    --header 'Content-Type: application/json' \
    --header "X-SFX-Signature: $SIGNATURE" \
    --data-binary "$BODY"
```

Use your configured port/path if different. Local HTTP is for localhost testing only;
the endpoint registered with Splunk must be public HTTPS. `sfx-olly webhook send-test`
is the simpler alternative and reads `.env` automatically.

Terminal 1 shows something like this:

```text
╭─  ANOMALOUS   Critical  Critical Alert: CPU above 90% on web-01 ────────────╮
│ Detector      High CPU on web tier                                          │
│ Rule          CPU above 90%                                                 │
│ Metric        cpu.utilization                                               │
│ Source        web-01                                                        │
│ Time          2026-10-15T09:12:44+00:00                                     │
│ Incident      TEST1A2B3C4D                                                  │
│ Dimensions    env = prod                                                    │
│               host = web-01                                                 │
│ Inputs        A: 97.3  {"host": "web-01"}                                   │
│ Message       cpu.utilization has been above 90% for 5 minutes.             │
│ Runbook       https://wiki.example.com/runbooks/cpu                         │
╰─────────────────────────────────────────────────────────────────────────────╯
```

The panel is red while firing (`anomalous`) and green when cleared (`ok` / `manually resolved`).

Re-render stored alerts later:

```bash
sfx-olly webhook render ./data/alerts.jsonl
sfx-olly webhook render single-alert.json
```

### 3. Connect Splunk Observability

Splunk only delivers to **HTTPS (TLS 1.2+)** URLs reachable from the internet. Typical options:

- A reverse proxy or ingress (nginx, Azure Application Gateway, Kubernetes ingress) that terminates TLS and forwards to the receiver.
- `WEBHOOK_SSL_CERTFILE` / `WEBHOOK_SSL_KEYFILE` to serve TLS directly.
- For quick experiments only: a tunnel such as `ngrok http 8080`.

Splunk cannot reach your laptop's `localhost` directly: that address refers to the
machine making the request, not your laptop. For a local test, start
`sfx-olly webhook serve`, then, in another terminal with ngrok installed and configured:

```bash
ngrok http 8080
```

Use the HTTPS forwarding address ngrok displays, followed by `/webhooks/splunk`,
as the Splunk integration URL, for example `https://<your-ngrok-address>/webhooks/splunk`.
Keep both processes running and your laptop awake; the tunnel URL may change when
restarted. Only use a tunnel if your organization permits it. For production, deploy
the receiver to an always-on server behind HTTPS instead of relying on your laptop.

Then, in Splunk Observability:

1. **Data Management → Add integration → Webhook → New integration**
2. **URL**: `https://<your-host><WEBHOOK_PATH>`
3. **Method**: `POST`
4. **Shared secret**: same value as `WEBHOOK_SHARED_SECRET`
5. Save, then use **Run test** to send a test notification.
6. Open a detector → **Alert recipients → Add recipient → Webhook →** your integration.

Splunk signs every request with `X-SFX-Signature = base64(HMAC-SHA256(secret, body))`. The receiver rejects requests without a valid signature with `401`.

### End-to-end webhook test

Keep `sfx-olly webhook serve` and `ngrok http 8080` running in separate terminals.
If ngrok reports an unauthenticated session, [sign in or create an account](https://dashboard.ngrok.com/signup)
and run the dashboard's `ngrok config add-authtoken` command locally with your credential.
The ngrok authtoken, `WEBHOOK_SHARED_SECRET`, and `SFX_TOKEN` are separate credentials;
do not share them or commit them to source control.

1. **Local receiver:** in a third terminal, run:

    ```bash
    sfx-olly webhook send-test
    ```

    Expect `HTTP 200` with `{"status":"accepted"}` and the synthetic critical alert
    in the receiver terminal. This tests only local delivery.

2. **Public tunnel:** replace `YOUR-NGROK-HOST` with the current HTTPS hostname shown
    by ngrok, keeping the full endpoint path:

    ```bash
    sfx-olly webhook send-test \
      --url "https://YOUR-NGROK-HOST/webhooks/splunk"
    ```

    Expect `HTTP 200` and another synthetic alert. This verifies the tunnel reaches
    the receiver, but still does not test Splunk's integration configuration.

3. **Splunk delivery:** set the integration URL to that same complete HTTPS URL,
    set the same shared secret as the receiver, and send a test notification from Splunk.
    Check the receiver terminal for the notification. Ensure the integration is selected
    as your detector's alert recipient before expecting actual trigger/clear notifications.

If ngrok shows **POST 404**, open its local inspector at `http://127.0.0.1:4040`
and inspect the failed request's path. With the default settings it must be exactly
`/webhooks/splunk`, not `/`. Also check that ngrok forwards to port `8080` and Splunk
uses the current tunnel hostname. Substitute your configured path/port if different.
The receiver has no POST handler at the root URL.

A **401** instead means the route was reached but signature verification failed;
check that Splunk and the receiver use the same shared secret. Keep verification enabled.
Do not use real secrets in screenshots or support messages; rotate any that were exposed.

### HTTP responses

| Status | When |
| --- | --- |
| `200 {"status":"accepted"}` | Alert accepted and dispatched to handlers |
| `200 {"status":"duplicate"}` | Same incident/state/timestamp already seen within the dedupe TTL |
| `401` | Missing or invalid signature |
| `403` | Source IP not in `WEBHOOK_ALLOWED_CIDRS` |
| `413` | Body larger than `WEBHOOK_MAX_BODY_BYTES` |
| `415` | Content-Type is not `application/json` |
| `422` | Body is not a valid alert JSON object |
| `GET /healthz` → `200` | Liveness/readiness probe |

---

## Library usage

### API client

```python
from sfx_olly import SplunkOllyClient
from sfx_olly.exceptions import AuthenticationError, ApiError
from sfx_olly.utils import time_range, parse_duration

with SplunkOllyClient() as client:                       # reads SFX_* settings
    # metadata
    page = client.metadata.search_metrics("name:cpu.*", limit=50)
    for metric in client.metadata.iter_metrics("name:*", max_items=2_000):   # auto-pagination
        print(metric["name"])

    # raw datapoints
    start, end = time_range("1h")
    series = client.timeseries.window("sf_metric:cpu.utilization", start, end, parse_duration("5m"))

    # SignalFlow - collected results
    points = client.signalflow.execute(
        "data('cpu.utilization').mean(by=['host']).publish()", start, end
    )
    for p in points:
        print(p.timestamp_ms, p.properties.get("host"), p.value)

    # SignalFlow - raw streaming messages
    for msg in client.signalflow.stream("data('cpu.utilization').publish()", start, end):
        print(msg.event, msg.payload)

    # alerts
    detectors = client.alerts.list_detectors(name="CPU")
    incidents = client.alerts.list_incidents(include_resolved=False)
```

Explicit settings (for example, several orgs in one process):

```python
from pydantic import SecretStr
from sfx_olly.config import ApiSettings
from sfx_olly import SplunkOllyClient

eu = SplunkOllyClient(ApiSettings(token=SecretStr(eu_token), realm="eu0"))
us = SplunkOllyClient(ApiSettings(token=SecretStr(us_token), realm="us1"))
```

Error handling:

```python
try:
    client.metadata.get_metric("does.not.exist")
except AuthenticationError:
    ...  # 401/403
except ApiError as exc:
    print(exc.status_code, exc)
```

### Webhook components

```python
from sfx_olly.webhook.models import AlertPayload
from sfx_olly.webhook.formatter import render_alert
from sfx_olly.webhook.security import verify_signature
from rich.console import Console

alert = AlertPayload.model_validate_json(raw_body)
Console().print(render_alert(alert))
ok = verify_signature(b"my-secret", raw_body, headers["X-SFX-Signature"])
```

---

## Extending

### Add a webhook handler (Slack, Teams, example telemetry, database...)

Any object with a `handle(alert: AlertPayload) -> None` method works as a handler. Handlers run after the `200` response has been sent, so a slow handler doesn't delay Splunk. If one handler fails, the error is logged and the other handlers still run.

```python
# my_app.py
from sfx_olly.config import get_webhook_settings
from sfx_olly.webhook.app import create_app
from sfx_olly.webhook.handlers import ConsoleHandler, JsonlFileHandler
from sfx_olly.webhook.models import AlertPayload


class TeamsHandler:
    def __init__(self, url: str) -> None:
        self.url = url

    def handle(self, alert: AlertPayload) -> None:
        if alert.is_firing:
            ...  # post to Teams


settings = get_webhook_settings()
app = create_app(settings, handlers=[ConsoleHandler(), TeamsHandler("https://...")])
```

```bash
uvicorn my_app:app --host 127.0.0.1 --port 8080
```

### Add an API endpoint

1. Add metric methods in `sfx_olly/metrics/`; keep shared transport and alert APIs in `sfx_olly/api/`. For traces or another signal, create a separate signal package with its own API class.
2. Use `self._http.get_json(path, params)` or `self._http.request(...)`. Authentication, retries and errors are handled for you.
3. If you created a new class, attach it in `SplunkOllyClient.__init__`.
4. (Optional) Add a CLI command in `sfx_olly/cli/` with a `register(sub)` function, then add the module to `COMMAND_MODULES` in `cli/main.py`.

### Add a help topic

Add an entry to `TOPICS` in `sfx_olly/help.py`. It then shows up in `sfx-olly help` automatically.

---

## Security

| Area | Control |
| --- | --- |
| Secrets | Read only from env or `.env`. Held as `SecretStr` so they are never printed in reprs or config errors. Masked in every log line. |
| Source control | `.env`, keys, certs and alert files are listed in `.gitignore`. Only `.env.example` is committed. |
| Transport | HTTPS only (base URLs are validated). TLS verification is always on, with an optional custom CA bundle. |
| Token leakage | HTTP redirects are disabled, so the `X-SF-Token` header is never sent to another host. |
| Input validation | Realm checked against a pattern (blocks host injection / SSRF via realm). IDs checked against an allowlist pattern. Path segments URL-encoded. Query, program and file sizes bounded. |
| Resilience | Timeouts on every call. Bounded retries with exponential backoff that honour `Retry-After`. |
| Error output | API error bodies are truncated. Config errors never echo input values. |
| Webhook auth | HMAC-SHA256 signature check with constant-time comparison. A secret is mandatory by default. |
| Webhook hardening | Body size limit (streamed). Content-type check. Optional CIDR allowlist. Proxy headers trusted only from configured proxies. Replay de-duplication. |
| Webhook surface | No `/docs` or `/openapi.json`. No `Server` header. `nosniff` and `no-store` headers. Responses never echo the payload. |
| Output safety | Untrusted alert text has control and ANSI characters stripped and is length-limited before display. JSONL files are created with mode `0600`. |
| Defaults | Binds to `127.0.0.1`. Logs a warning when exposed without TLS or without signature checks. |

Production recommendations:

- Keep tokens in a secret manager (for example Azure Key Vault or Kubernetes secrets) and inject them as environment variables. Don't ship `.env` files to production.
- Use a token with the least privilege you need (an API token for reads only), and rotate tokens and the webhook secret regularly.
- Put the receiver behind TLS termination and a WAF or rate limiter.
- Run as a non-root user.

---

## Scaling

- **API client**: one pooled `requests.Session` per client, with pool size set by `SFX_POOL_MAXSIZE`. `iter_metrics` / `iter_mts` page lazily, so large result sets don't need to fit in memory. `signalflow.stream()` processes results as they arrive.
- **Webhook receiver**: stateless and async. Alerts are handed to background tasks so Splunk gets an immediate `200`. Raise `WEBHOOK_WORKERS`, or run several replicas behind a load balancer, and use `/healthz` for probes.
- **Multiple replicas**: de-duplication is per process. For coordinated processing across replicas, add a handler that uses a shared store (Redis `SET NX EX`, or a database unique key on `incidentId|state|timestamp`), or publish to a durable queue and process downstream. A queue alone does not guarantee exactly-once delivery.
- **JSONL output** is meant for single-host use. For multiple replicas, write to a shared sink through a custom handler.

---

## Troubleshooting

### Dashboard has data but the filtered query is empty

For example, this query will be empty if the selected series do not have that literal dimension key:

```bash
sfx-olly query example.project.size --filter deployment.environment.name=env-test --range 2d
```

Suppose your series have `environment=env-test` but no
`deployment.environment.name` dimension. These are different keys, so filtering by
the missing key will not select those series. After inspecting your metric's actual
dimensions, use the matching key:

```bash
sfx-olly query example.project.size --filter environment=env-test --range 2d
# compact display of the latest non-null result within that window per series:
sfx-olly query example.project.size --filter environment=env-test --range 2d --latest
```

These commands are fictional examples, not guaranteed data sources. `--latest` can
return an older sample inside the window; it does not prove current availability.
Compare the dashboard's actual SignalFlow, filters, time window, resolution, rollup,
and realm/org if differences remain. To investigate your metric:

```bash
sfx-olly metrics inspect example.project.size
sfx-olly mts search 'sf_metric:example.project.size AND environment:env-test'
sfx-olly query example.project.size --range 2d --latest
sfx-olly query example.project.size --filter environment=env-test --range 2d --dry-run
sfx-olly -v query example.project.size --filter environment=env-test --range 2d --latest
```

Do not guess aliases between `env`, `environment`, and `deployment.environment.name`.
Sparse metrics may need a wider range; match the dashboard rather than inventing data
with extrapolation. Aborted SignalFlow computations now raise errors instead of appearing empty.

| Symptom | Fix |
| --- | --- |
| `HTTP 400 ... Unsupported query syntax` | Search endpoints need `field:value` syntax. Bare terms are now prefixed automatically. To get metric **values**, use `sfx-olly query <metric>`. |
| `Configuration error ... token: Field required` | Set `SFX_TOKEN` in `.env` or the environment. |
| `HTTP 401/403` | The token is invalid, expired, or an ingest-only token. Use an API-scoped token. |
| `invalid realm` | Use your org realm from **Settings → Organization** (e.g. `eu0`). |
| SSL errors behind a corporate proxy | Set `SFX_CA_BUNDLE` to the proxy CA file. |
| `WEBHOOK_SHARED_SECRET is required` | Set the secret, or set `WEBHOOK_REQUIRE_SIGNATURE=false` for local tests only. |
| Webhook returns `401` | The secret in Splunk and `WEBHOOK_SHARED_SECRET` don't match. |
| Webhook returns `403` | The caller IP isn't in `WEBHOOK_ALLOWED_CIDRS`. Behind a proxy, set `WEBHOOK_TRUST_PROXY_HEADERS=true` and `WEBHOOK_FORWARDED_ALLOW_IPS`. |
| Need request details | Set `LOG_LEVEL=DEBUG`. Tokens stay redacted. |

### Local regression checks

```bash
python -m unittest discover -s tests -v
```

Tests use mocked API responses and do not need a token or access to Splunk.

## License

Released under the [MIT License](https://github.com/asksmruti/sfx-olly/blob/main/LICENSE). Dependency licenses remain their owners'
licenses. Confirm you have permission to publish the code and documentation before
making an organization-developed project public.
