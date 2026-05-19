# Enterprise systems — query overview

In TASK-03 (this task) the skill's tools query in-memory synthetic data from
`data/`. In TASK-04 these tools are replaced by MCP-server calls; the skill
surface stays the same.

| Tool | Backing data (TASK-03) | Backing system (TASK-04) |
|---|---|---|
| `query_maximo_availability` | `data/maximo_inventory.json` | Maximo MCP |
| `query_sap_workforce` | `data/sap_workforce.json` | SAP MCP |
| `query_fdp_customer_config` | `data/fdp_configurations.json` | FDP MCP |
| `query_intouch_specs` | `data/intouch_index.json` | InTouch retrieval (Knowledge Catalog + Smart Storage) |

All queries are by **canonical_id** (Knowledge Catalog's identifier), never
by SAP material number, Maximo equipment id, or FDP config id. The
asset-equivalence skill resolves the input identifier upstream.
