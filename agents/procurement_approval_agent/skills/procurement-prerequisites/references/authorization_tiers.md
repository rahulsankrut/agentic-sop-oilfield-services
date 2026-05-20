# Authorization tiers

| Tier | Approval threshold (USD) | Typical owner |
|---|---|---|
| `junior` | $200K | OCC planner |
| `standard` | $500K | Senior OCC planner |
| `senior` | $1.5M | Operations Manager |
| `director` | $5M | Operations Director |
| `strict` | $200K | Customer-mandated tier (e.g., North Atlantic Resources, Deepwater Ventures) |

Anything above $5M requires VP-level approval and is out of scope of the
automated procurement gate (the agent surfaces a finding and returns
`approved=false`).
