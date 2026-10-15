# sfx-olly

A Python CLI and library for Splunk Observability Cloud: discover metrics, query
their values with SignalFlow, inspect detectors/incidents, and receive alert webhooks.

Requires Python 3.10+ and an API-scoped token for querying your organization.
Metric queries run once and exit; the webhook receiver stays running to accept notifications.
Raw traces and logs are not currently supported.

## Installation

From the project checkout:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Without the installed command, use `python -m sfx_olly` instead of `sfx-olly`.

## Configuration

```bash
cp .env.example .env
```

Edit your local `.env` to set `SFX_TOKEN` and the correct `SFX_REALM`.
Run commands from that directory; real environment variables override `.env`.
Keep credentials out of source control and support messages.

See the [configuration reference](https://github.com/asksmruti/sfx-olly/blob/main/docs/reference.md#configuration)
for timeouts, retries, corporate CA certificates, logging, and webhook settings.

## Common Commands

All example metric names, projects, and environments below are fictional. Replace
them with values discovered in your organization; these examples are not seeded data.

```bash
# Discover metric names and their dimensions.
sfx-olly metrics search 'example.*' --limit 20
sfx-olly metrics inspect example.project.size

# Read a project's values, without combining different series.
sfx-olly query example.project.size \
  --filter environment=env-test --filter project.name=project-demo \
  --range 1h --resolution 1m --unit kib

# Print the generated SignalFlow without calling the API.
sfx-olly query example.project.size --filter environment=env-test --dry-run

# Run SignalFlow copied from a chart file.
sfx-olly signalflow --file chart.flow --range 1h --resolution 1m

# Inspect active incidents or detector configurations.
sfx-olly incidents list
sfx-olly detectors list --limit 20

# Get command help or machine-readable results.
sfx-olly query --help
sfx-olly -o json metrics inspect example.project.size
```

`--unit kib` assumes the source values are bytes; it only formats table output.
Add `--latest` to display the latest non-null returned point per series in the window.
This can be an older sample, not proof of current availability.

## Understand Query Options

| Option | Question it answers |
| --- | --- |
| `--filter KEY=VALUE` | Which dimension-labelled series should be included? |
| `--range 1h` | How far back from now should the query look? |
| `--resolution 1m` | How large should each requested time bucket be? |
| `--rollup max` | How should one series' samples be combined within a bucket? |
| `--agg sum` | How should different series be combined at each timestamp? |
| `--by project.name` | Should that aggregation run separately for each project? |
| `--transform mean --over 1h` | Should each resulting series have a moving time calculation? |

Start without aggregation and add it only when the result has the meaning you want.
For example, summing duplicate reports of a shared project size would double-count it.

The [Command Guide](https://github.com/asksmruti/sfx-olly/blob/main/docs/command-guide.md)
contains worked numeric examples, every option, a step-by-step project query,
recipes, and dashboard comparison checks.

## Webhook Receiver

Set `WEBHOOK_SHARED_SECRET` in your local `.env` to a locally generated secret,
and keep `WEBHOOK_REQUIRE_SIGNATURE=true`. Use that same secret in Splunk's webhook
integration. Then start the receiver:

```bash
sfx-olly webhook serve
```

In another terminal, send a signed synthetic alert:

```bash
sfx-olly webhook send-test
```

The displayed Critical CPU alert is sample data, not an incident from your detector.
`serve` listens for notifications; it does not create or trigger Splunk alerts.

Splunk needs a reachable HTTPS endpoint ending in `/webhooks/splunk`, not your
laptop's localhost. Configure that integration as your detector's alert recipient.
The [webhook setup and end-to-end tests](https://github.com/asksmruti/sfx-olly/blob/main/docs/reference.md#webhook-receiver)
cover secrets, ngrok, local/tunnel/Splunk tests, payload storage, and 404/401 troubleshooting.

## Library Usage

```python
from sfx_olly import SplunkOllyClient
from sfx_olly.metrics import MetricQuery
from sfx_olly.utils import time_range

start, stop = time_range("1h")
spec = MetricQuery("example.project.size", filters={"environment": ["env-test"]})
with SplunkOllyClient() as client:
    points = client.signalflow.query(spec, start, stop)
```

See the [library reference](https://github.com/asksmruti/sfx-olly/blob/main/docs/reference.md#library-usage)
for metadata APIs, custom settings, error handling, and webhook handlers.

## Documentation

- [Command Guide](https://github.com/asksmruti/sfx-olly/blob/main/docs/command-guide.md): concepts, numerical examples, options, and recipes.
- [User Reference](https://github.com/asksmruti/sfx-olly/blob/main/docs/reference.md): full configuration, cURL examples, webhooks, library APIs, security, and troubleshooting.
- [Architecture](https://github.com/asksmruti/sfx-olly/blob/main/docs/architecture.md): module map, call flows, and adding other signals.

The CLI also includes offline help: `sfx-olly help` and `sfx-olly help query`.
Contributor and release procedures are separate in [docs/publishing.md](https://github.com/asksmruti/sfx-olly/blob/main/docs/publishing.md).

## License

[MIT](https://github.com/asksmruti/sfx-olly/blob/main/LICENSE).
