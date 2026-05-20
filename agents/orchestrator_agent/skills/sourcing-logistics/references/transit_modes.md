# Transit-mode selection

| Distance (km) | Mode | Effective speed | Base $/km | Notes |
|---|---|---|---|---|
| 0 – 250 | `ground_transit` | ~60 km/h + 4h prep | $200 | Truck + crew |
| 250 – 8000 | `sea_freight` | ~40 km/h + 48h overhead | $80 | Container + 24h handling each end |
| > 8000 | `cargo_charter` | ~750 km/h + 8h ground handling | $50 (×1.0–1.8 by asset class) | Antonov-class for frac spreads |

Asset-class multipliers for cargo charter:
- `downhole_tool` × 1.0 (small footprint)
- `surface_equipment` × 1.4
- `frac_spread` × 1.8 (oversize cargo handling)

Loaded costs add $150/hr per certification labour hour and a flat $5K customs
surcharge when the source and destination are in different countries.
