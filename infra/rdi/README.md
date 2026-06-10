# RDI configuration

Redis Data Integration pipeline for the demo. Streams Postgres rows into
the canonical Redis keys consumed by the rest of the stack.

## Layout

```
infra/rdi/
├── Dockerfile          # demo processor image (python 3.12)
├── processor.py        # CDC processor: LISTEN/NOTIFY → Redis writes
├── triggers.sql        # idempotent CDC triggers, installed on startup
├── requirements.txt
└── config/
    ├── config.yaml     # sources/targets, RDI schema
    └── jobs/           # one YAML per source table
        ├── customers.yaml
        ├── accounts.yaml
        ├── cards.yaml
        ├── devices.yaml
        ├── merchants.yaml
        ├── merchant_categories.yaml
        └── transactions.yaml
```

## Key mapping

| Postgres table         | Redis key(s)                                                            | Type(s)                |
|------------------------|-------------------------------------------------------------------------|------------------------|
| `customers`            | `customer:{customer_id}`                                                | JSON                   |
| `accounts`             | `account:{account_id}`                                                  | JSON                   |
| `cards`                | `card:{card_id}`                                                        | JSON                   |
| `devices`              | `device:{device_id}`                                                    | JSON                   |
| `merchants`            | `merchant:{merchant_id}` (includes `reputation_score`)                  | JSON                   |
| `merchant_categories`  | `mcc:{code}`                                                            | JSON                   |
| `transactions`         | `tx:{transaction_id}` + `XADD stream:transactions` + `LPUSH card:{card_id}:tx:recent` (capped at 100) | JSON + Stream + List   |

## How it works

The container reads RDI-shaped YAML (see `config/config.yaml` and
`config/jobs/*.yaml`) and applies `redis.write` outputs to the Redis
Cloud database identified by `REDIS_URL`.

CDC is implemented via Postgres `LISTEN/NOTIFY` row triggers
(`triggers.sql`), giving sub-100ms event latency on a local stack. The
processor maintains an `rdi:status` JSON document (heartbeat plus
`last_event_at`) — the backend exposes this at `GET /rdi/status` and
`make rdi-status` prints the current lag.

In production the same `config/` directory can be pointed at the
managed RDI Helm chart (`redis/rdi-processor`, `redis/rdi-collector-*`,
etc. — see [Install on Kubernetes](https://redis.io/docs/latest/integrate/redis-data-integration/installation/install-k8s/)).
