"""Default congestion zones — known traffic hotspots to avoid in routing."""

DEFAULT_CONGESTION_ZONES: list[dict] = [
    # ── NYC zones ──
    {
        "zone_id": "nyc_times_square",
        "city": "nyc",
        "name": "Times Square Area",
        "severity": "severe",
        "center": [-73.9855, 40.7580],
        "polygon": [
            [-73.9880, 40.7560], [-73.9830, 40.7560],
            [-73.9830, 40.7600], [-73.9880, 40.7600],
            [-73.9880, 40.7560],
        ],
    },
    {
        "zone_id": "nyc_herald_square",
        "city": "nyc",
        "name": "Herald Square / Penn Station",
        "severity": "moderate",
        "center": [-73.9876, 40.7484],
        "polygon": [
            [-73.9900, 40.7465], [-73.9850, 40.7465],
            [-73.9850, 40.7505], [-73.9900, 40.7505],
            [-73.9900, 40.7465],
        ],
    },
    {
        "zone_id": "nyc_lincoln_tunnel",
        "city": "nyc",
        "name": "Lincoln Tunnel Approach",
        "severity": "severe",
        "center": [-74.0020, 40.7600],
        "polygon": [
            [-74.0050, 40.7580], [-73.9990, 40.7580],
            [-73.9990, 40.7620], [-74.0050, 40.7620],
            [-74.0050, 40.7580],
        ],
    },
    {
        "zone_id": "nyc_holland_tunnel",
        "city": "nyc",
        "name": "Holland Tunnel Approach",
        "severity": "moderate",
        "center": [-74.0090, 40.7260],
        "polygon": [
            [-74.0120, 40.7240], [-74.0060, 40.7240],
            [-74.0060, 40.7280], [-74.0120, 40.7280],
            [-74.0120, 40.7240],
        ],
    },
    # ── Chandigarh zones ──
    {
        "zone_id": "chd_sector17",
        "city": "chandigarh",
        "name": "Sector 17 Market Area",
        "severity": "severe",
        "center": [76.7788, 30.7412],
        "polygon": [
            [76.7760, 30.7395], [76.7815, 30.7395],
            [76.7815, 30.7430], [76.7760, 30.7430],
            [76.7760, 30.7395],
        ],
    },
    {
        "zone_id": "chd_tribune_chowk",
        "city": "chandigarh",
        "name": "Tribune Chowk",
        "severity": "moderate",
        "center": [76.7675, 30.7270],
        "polygon": [
            [76.7650, 30.7250], [76.7700, 30.7250],
            [76.7700, 30.7290], [76.7650, 30.7290],
            [76.7650, 30.7250],
        ],
    },
    {
        "zone_id": "chd_isbt",
        "city": "chandigarh",
        "name": "ISBT / Sector 43 Junction",
        "severity": "severe",
        "center": [76.7511, 30.7226],
        "polygon": [
            [76.7485, 30.7205], [76.7535, 30.7205],
            [76.7535, 30.7245], [76.7485, 30.7245],
            [76.7485, 30.7205],
        ],
    },
    {
        "zone_id": "chd_elante",
        "city": "chandigarh",
        "name": "Elante Mall / Industrial Area",
        "severity": "moderate",
        "center": [76.8016, 30.7061],
        "polygon": [
            [76.7990, 30.7040], [76.8040, 30.7040],
            [76.8040, 30.7080], [76.7990, 30.7080],
            [76.7990, 30.7040],
        ],
    },
]
