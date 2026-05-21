# ============================================================
# NAXA Phase 2 — engine/events_db.py
#
# The Historical Events Database — v0.3.0 (n=14)
# ============================================================
#
# WHAT CHANGED IN v0.3.0:
#   Expanded from n=4 to n=14 events.
#   Added Red Sea cluster (3 events), Panama historical droughts
#   (2011, 2015), port disruptions (LA 2021, ILWU 2022),
#   Black Sea grain corridor, and Cape rerouting surge.
#   Date range expanded from 2016-2023 to 2011-2024.
#
# IMPORTANT — EVENT TYPE HETEROGENEITY:
#   Original 4 events were all canal_capacity_restriction.
#   New events include route_security_disruption and
#   port_capacity_disruption types. The scorer currently
#   treats all events equally. Directional signals remain
#   valid across types. Magnitude comparisons should note
#   the type difference when presenting to analysts.
#
# EVENTS NEEDING VERIFICATION (data_quality = ESTIMATED):
#   panama_drought_2011, panama_drought_2015,
#   panama_expansion_delays_2014
#   These are directionally valid. Verify magnitudes before
#   customer-facing reporting.
#
# SOURCES KEY:
#   [ACP]     Panama Canal Authority official statistics
#   [DREWRY]  Drewry World Container Index reports
#   [LLOYDS]  Lloyd's List shipping intelligence
#   [IMF]     IMF Primary Commodity Prices
#   [USDA]    US Department of Agriculture
#   [FBX]     Freightos Baltic Index
#   [BIMCO]   Baltic and International Maritime Council
# ============================================================

EVENTS = {

    # =========================================================
    # ORIGINAL 4 EVENTS — unchanged from v0.2.0
    # =========================================================

    "panama_drought_2023": {
        "meta": {
            "name":         "Panama Canal Drought 2023",
            "type":         "canal_capacity_restriction",
            "subtype":      "drought_water_level",
            "location":     "Panama Canal, Gatun Lake",
            "trigger_date": "2023-08-01",
            "peak_date":    "2023-11-15",
            "end_date":     "2024-02-01",
            "severity": {
                "score":                 0.85,
                "transit_reduction_pct": 50,
                "duration_weeks":        26,
                "cause": "El Niño-driven drought, record low Gatun Lake levels"
            },
            "sources": [
                "ACP Notice to Shipping N-A-148-2023",
                "ACP Monthly Traffic Statistics Aug-Dec 2023",
                "https://www.pancanal.com/en/statistics"
            ]
        },
        "signal_chain": {
            "container_freight_asia_usec": {
                "asset":        "Drewry WCI Asia-USEC Route",
                "layer":        2,
                "asset_class":  "freight_rate",
                "direction":    "UP",
                "move_14d":     18.0,
                "move_30d":     28.4,
                "move_60d":     31.2,
                "data_quality": "PRIMARY",
                "source":       "[DREWRY]",
                "notes": "Asia-US East Coast route most directly impacted."
            },
            "shipping_equities_container": {
                "asset":        "Container Shipping Stocks (ZIM, MATX composite)",
                "layer":        3,
                "asset_class":  "equity",
                "direction":    "MIXED",
                "move_14d":     4.2,
                "move_30d":     -2.1,
                "move_60d":     -8.4,
                "data_quality": "PRIMARY",
                "source":       "[yfinance]",
                "notes": "Canal signal overwhelmed by post-COVID normalization trend."
            },
            "shipping_equities_tanker": {
                "asset":        "Tanker Stocks (FRO, INSW composite)",
                "layer":        3,
                "asset_class":  "equity",
                "direction":    "UP",
                "move_14d":     6.8,
                "move_30d":     11.2,
                "move_60d":     8.9,
                "data_quality": "PRIMARY",
                "source":       "[yfinance]",
                "notes": "LNG rerouting via Cape Horn increases ton-mile demand."
            },
            "grain_prices_corn": {
                "asset":        "Global Corn Price (IMF series)",
                "layer":        4,
                "asset_class":  "commodity_agricultural",
                "direction":    "DOWN",
                "move_14d":     -1.2,
                "move_30d":     -4.8,
                "move_60d":     -7.1,
                "data_quality": "PRIMARY",
                "source":       "[IMF] [USDA]",
                "notes": "Brazil 2023 record harvest overwhelmed canal signal."
            }
        }
    },

    "suez_blockage_2021": {
        "meta": {
            "name":         "Suez Canal Ever Given Blockage 2021",
            "type":         "canal_capacity_restriction",
            "subtype":      "vessel_grounding_full_blockage",
            "location":     "Suez Canal, Egypt",
            "trigger_date": "2021-03-23",
            "peak_date":    "2021-03-23",
            "end_date":     "2021-03-29",
            "severity": {
                "score":                 0.95,
                "transit_reduction_pct": 100,
                "duration_weeks":        0.86,
                "cause": "Container vessel Ever Given ran aground in high winds"
            },
            "sources": [
                "Suez Canal Authority incident report March 2021",
                "Drewry WCI reports March-April 2021",
                "Lloyd's List coverage March 2021"
            ]
        },
        "signal_chain": {
            "container_freight_asia_usec": {
                "asset":        "Drewry WCI Asia-USEC Route",
                "layer":        2,
                "asset_class":  "freight_rate",
                "direction":    "UP",
                "move_14d":     24.6,
                "move_30d":     31.4,
                "move_60d":     38.2,
                "data_quality": "PRIMARY",
                "source":       "[DREWRY]",
                "notes": "2021 rates already elevated from COVID demand surge."
            },
            "shipping_equities_container": {
                "asset":        "Container Shipping Stocks",
                "layer":        3,
                "asset_class":  "equity",
                "direction":    "UP",
                "move_14d":     8.4,
                "move_30d":     14.7,
                "move_60d":     21.3,
                "data_quality": "PRIMARY",
                "source":       "[yfinance]",
                "notes": "Clean equity signal — no normalization headwind in 2021."
            },
            "shipping_equities_tanker": {
                "asset":        "Tanker Stocks",
                "layer":        3,
                "asset_class":  "equity",
                "direction":    "UP",
                "move_14d":     5.2,
                "move_30d":     9.1,
                "move_60d":     12.4,
                "data_quality": "PRIMARY",
                "source":       "[yfinance]",
                "notes": "Smaller move than containers — crude tankers use Cape routinely."
            },
            "grain_prices_corn": {
                "asset":        "Global Corn Price",
                "layer":        4,
                "asset_class":  "commodity_agricultural",
                "direction":    "UP",
                "move_14d":     2.8,
                "move_30d":     5.1,
                "move_60d":     3.4,
                "data_quality": "PRIMARY",
                "source":       "[IMF] [USDA]",
                "notes": "Suez carries more grain than Panama — Black Sea exports."
            }
        }
    },

    "panama_drought_2019": {
        "meta": {
            "name":         "Panama Canal Drought 2019",
            "type":         "canal_capacity_restriction",
            "subtype":      "drought_water_level",
            "location":     "Panama Canal, Gatun Lake",
            "trigger_date": "2019-07-15",
            "peak_date":    "2019-09-01",
            "end_date":     "2019-11-30",
            "severity": {
                "score":                 0.45,
                "transit_reduction_pct": 20,
                "duration_weeks":        20,
                "cause": "Dry season extended by regional weather pattern"
            },
            "sources": [
                "ACP Annual Report 2019",
                "ACP Notice to Shipping series July-November 2019"
            ]
        },
        "signal_chain": {
            "container_freight_asia_usec": {
                "asset":        "Drewry WCI Asia-USEC Route",
                "layer":        2,
                "asset_class":  "freight_rate",
                "direction":    "UP",
                "move_14d":     11.2,
                "move_30d":     18.7,
                "move_60d":     16.4,
                "data_quality": "PRIMARY",
                "source":       "[DREWRY]",
                "notes": "Smaller move than 2023 — validates severity correlation."
            },
            "shipping_equities_container": {
                "asset":        "Container Shipping Stocks",
                "layer":        3,
                "asset_class":  "equity",
                "direction":    "MIXED",
                "move_14d":     2.1,
                "move_30d":     3.4,
                "move_60d":     -1.8,
                "data_quality": "PARTIAL",
                "source":       "[yfinance]",
                "notes": "High confounder: US-China trade war tariffs active 2019."
            },
            "shipping_equities_tanker": {
                "asset":        "Tanker Stocks",
                "layer":        3,
                "asset_class":  "equity",
                "direction":    "UP",
                "move_14d":     3.8,
                "move_30d":     6.2,
                "move_60d":     4.1,
                "data_quality": "PRIMARY",
                "source":       "[yfinance]",
                "notes": "Cleaner than containers — less trade war exposure."
            },
            "grain_prices_corn": {
                "asset":        "Global Corn Price",
                "layer":        4,
                "asset_class":  "commodity_agricultural",
                "direction":    "FLAT",
                "move_14d":     0.4,
                "move_30d":     1.2,
                "move_60d":     0.8,
                "data_quality": "PRIMARY",
                "source":       "[IMF]",
                "notes": "Minimal grain response — consistent with lower severity."
            }
        }
    },

    "panama_expansion_2016": {
        "meta": {
            "name":         "Panama Canal New Locks Expansion 2016",
            "type":         "canal_capacity_restriction",
            "subtype":      "construction_capacity_uncertainty",
            "location":     "Panama Canal",
            "trigger_date": "2016-04-01",
            "peak_date":    "2016-04-15",
            "end_date":     "2016-06-26",
            "severity": {
                "score":                 0.35,
                "transit_reduction_pct": 10,
                "duration_weeks":        12,
                "cause": "Construction delays and new lock reliability concerns"
            },
            "sources": [
                "ACP press release April 2016",
                "Journal of Commerce: Canal Expansion Coverage 2016"
            ]
        },
        "signal_chain": {
            "container_freight_asia_usec": {
                "asset":        "Drewry WCI Asia-USEC Route",
                "layer":        2,
                "asset_class":  "freight_rate",
                "direction":    "UP",
                "move_14d":     8.4,
                "move_30d":     14.2,
                "move_60d":     11.8,
                "data_quality": "PRIMARY",
                "source":       "[DREWRY]",
                "notes": "Smallest freight move — validates severity scaling."
            },
            "shipping_equities_container": {
                "asset":        "Container Shipping Stocks",
                "layer":        3,
                "asset_class":  "equity",
                "direction":    "UP",
                "move_14d":     5.1,
                "move_30d":     7.8,
                "move_60d":     12.4,
                "data_quality": "PARTIAL",
                "source":       "[yfinance]",
                "notes": "Confounder: Hanjin Shipping bankruptcy August 2016."
            },
            "shipping_equities_tanker": {
                "asset":        "Tanker Stocks",
                "layer":        3,
                "asset_class":  "equity",
                "direction":    "UP",
                "move_14d":     4.2,
                "move_30d":     6.8,
                "move_60d":     9.1,
                "data_quality": "PRIMARY",
                "source":       "[yfinance]",
                "notes": "Clean signal — not affected by Hanjin bankruptcy."
            },
            "grain_prices_corn": {
                "asset":        "Global Corn Price",
                "layer":        4,
                "asset_class":  "commodity_agricultural",
                "direction":    "FLAT",
                "move_14d":     -0.8,
                "move_30d":     1.4,
                "move_60d":     2.1,
                "data_quality": "PRIMARY",
                "source":       "[IMF]",
                "notes": "No meaningful grain signal for this event type."
            }
        }
    },

    # =========================================================
    # NEW EVENTS — added in v0.3.0
    # Red Sea / route security cluster
    # =========================================================

    "red_sea_houthi_2024": {
        "meta": {
            "name":         "Red Sea Houthi Shipping Crisis 2023-2024",
            "type":         "route_security_disruption",
            "subtype":      "armed_threat_commercial_vessels",
            "location":     "Red Sea / Bab-el-Mandeb Strait",
            "trigger_date": "2023-12-19",
            "peak_date":    "2024-01-15",
            "end_date":     None,
            "severity": {
                "score":                 0.80,
                "transit_reduction_pct": 75,
                "duration_weeks":        52,
                "cause": "Houthi attacks on commercial vessels. MSC and Maersk "
                         "suspended Red Sea transits Dec 19 2023."
            },
            "sources": [
                "Maersk advisory Dec 19 2023",
                "MSC statement Dec 19 2023",
                "UNCTAD Rapid Assessment: Red Sea crisis Jan 2024",
                "Drewry WCI reports Dec 2023 - Jan 2024"
            ]
        },
        "signal_chain": {
            "container_freight_asia_usec": {
                "asset":        "Drewry WCI Asia-USEC Route",
                "layer":        2,
                "asset_class":  "freight_rate",
                "direction":    "UP",
                "move_14d":     38.5,
                "move_30d":     62.4,
                "move_60d":     48.2,
                "data_quality": "PRIMARY",
                "source":       "[DREWRY] [FBX]",
                "notes": "LARGEST MOVES IN DATABASE. Asia-Europe saw +100-170%. "
                         "USEC impact driven by capacity diversion from rerouted vessels."
            },
            "shipping_equities_container": {
                "asset":        "Container Shipping Stocks (ZIM, MATX, DAC)",
                "layer":        3,
                "asset_class":  "equity",
                "direction":    "UP",
                "move_14d":     18.4,
                "move_30d":     31.2,
                "move_60d":     22.8,
                "data_quality": "PRIMARY",
                "source":       "[yfinance]",
                "notes": "Cleaner equity signal than Panama 2023. Rate spike overcame "
                         "normalization headwind. ZIM +40%+ from Dec 19 lows."
            },
            "shipping_equities_tanker": {
                "asset":        "Tanker Stocks (FRO, INSW)",
                "layer":        3,
                "asset_class":  "equity",
                "direction":    "UP",
                "move_14d":     12.6,
                "move_30d":     19.4,
                "move_60d":     16.8,
                "data_quality": "PRIMARY",
                "source":       "[yfinance]",
                "notes": "Cape rerouting adds 8-10 days per voyage. Structural ton-mile increase."
            },
            "grain_prices_corn": {
                "asset":        "Global Grain Prices",
                "layer":        4,
                "asset_class":  "commodity_agricultural",
                "direction":    "UP",
                "move_14d":     2.1,
                "move_30d":     4.8,
                "move_60d":     3.2,
                "data_quality": "PARTIAL",
                "source":       "[IMF] [USDA]",
                "notes": "Modest grain upward pressure. Confounder: Ukraine/Russia ongoing."
            }
        }
    },

    "suez_rerouting_sustained_2024": {
        "meta": {
            "name":         "Sustained Red Sea Avoidance / Cape Rerouting 2024",
            "type":         "route_security_disruption",
            "subtype":      "sustained_rerouting_normalization",
            "location":     "Red Sea / Cape of Good Hope",
            "trigger_date": "2024-01-10",
            "peak_date":    "2024-02-01",
            "end_date":     None,
            "severity": {
                "score":                 0.72,
                "transit_reduction_pct": 65,
                "duration_weeks":        48,
                "cause": "Maersk confirmed permanent Cape routing Jan 10 2024. "
                         "New operational standard for all major carriers."
            },
            "sources": [
                "Maersk operational update Jan 10 2024",
                "Hapag-Lloyd carrier advisory Jan 2024",
                "BIMCO situation report Q1 2024"
            ]
        },
        "signal_chain": {
            "container_freight_asia_usec": {
                "asset":        "Drewry WCI Asia-USEC (sustained elevation)",
                "layer":        2,
                "asset_class":  "freight_rate",
                "direction":    "UP",
                "move_14d":     22.1,
                "move_30d":     35.8,
                "move_60d":     41.2,
                "data_quality": "PRIMARY",
                "source":       "[DREWRY] [FBX]",
                "notes": "Rates compounded over time. Structural capacity removed from Red Sea lane."
            },
            "shipping_equities_container": {
                "asset":        "Container Shipping Stocks",
                "layer":        3,
                "asset_class":  "equity",
                "direction":    "UP",
                "move_14d":     8.4,
                "move_30d":     14.6,
                "move_60d":     19.2,
                "data_quality": "PRIMARY",
                "source":       "[yfinance]",
                "notes": "Sustained earnings uplift priced in from Jan 10 base."
            },
            "shipping_equities_tanker": {
                "asset":        "Tanker Stocks",
                "layer":        3,
                "asset_class":  "equity",
                "direction":    "UP",
                "move_14d":     6.2,
                "move_30d":     11.4,
                "move_60d":     14.8,
                "data_quality": "PRIMARY",
                "source":       "[yfinance]",
                "notes": "Cape routing = structural ton-mile increase."
            },
            "grain_prices_corn": {
                "asset":        "Global Grain Prices",
                "layer":        4,
                "asset_class":  "commodity_agricultural",
                "direction":    "UP",
                "move_14d":     1.8,
                "move_30d":     3.4,
                "move_60d":     4.1,
                "data_quality": "PARTIAL",
                "source":       "[IMF]",
                "notes": "Modest sustained grain uplift."
            }
        }
    },

    "suez_war_risk_insurance_2024": {
        "meta": {
            "name":         "Red Sea War Risk Insurance Spike Jan 2024",
            "type":         "route_security_disruption",
            "subtype":      "war_risk_insurance_elevation",
            "location":     "Red Sea, Gulf of Aden",
            "trigger_date": "2024-01-15",
            "peak_date":    "2024-01-20",
            "end_date":     None,
            "severity": {
                "score":                 0.70,
                "transit_reduction_pct": 60,
                "duration_weeks":        40,
                "cause": "LMA war risk zone designation + spike in vessel targeting incidents."
            },
            "sources": [
                "Lloyd's Market Association joint war committee notice Jan 2024",
                "BIMCO war risk insurance market report Q1 2024"
            ]
        },
        "signal_chain": {
            "container_freight_asia_usec": {
                "asset":        "Drewry WCI Asia-USEC Route",
                "layer":        2,
                "asset_class":  "freight_rate",
                "direction":    "UP",
                "move_14d":     15.2,
                "move_30d":     24.8,
                "move_60d":     28.4,
                "data_quality": "PARTIAL",
                "source":       "[DREWRY]",
                "notes": "Confounder: Overlaps with red_sea_houthi_2024 and suez_rerouting_2024. "
                         "Use as corroborating data."
            },
            "shipping_equities_container": {
                "asset":        "Container Shipping Stocks",
                "layer":        3,
                "asset_class":  "equity",
                "direction":    "UP",
                "move_14d":     6.8,
                "move_30d":     12.4,
                "move_60d":     10.2,
                "data_quality": "PARTIAL",
                "source":       "[yfinance]",
                "notes": "Corroborating data. Overlapping with other Red Sea events."
            },
            "shipping_equities_tanker": {
                "asset":        "Tanker Stocks",
                "layer":        3,
                "asset_class":  "equity",
                "direction":    "UP",
                "move_14d":     5.4,
                "move_30d":     9.8,
                "move_60d":     11.2,
                "data_quality": "PARTIAL",
                "source":       "[yfinance]",
                "notes": "Corroborating signal."
            },
            "grain_prices_corn": {
                "asset":        "Global Grain Prices",
                "layer":        4,
                "asset_class":  "commodity_agricultural",
                "direction":    "UP",
                "move_14d":     1.4,
                "move_30d":     2.8,
                "move_60d":     2.1,
                "data_quality": "PARTIAL",
                "source":       "[IMF]",
                "notes": "Modest signal. Multiple confounders active."
            }
        }
    },

    # =========================================================
    # Panama historical drought cluster
    # =========================================================

    "panama_drought_2015": {
        "meta": {
            "name":         "Panama Canal Drought 2015",
            "type":         "canal_capacity_restriction",
            "subtype":      "drought_water_level",
            "location":     "Panama Canal, Gatun Lake",
            "trigger_date": "2015-07-10",
            "peak_date":    "2015-09-15",
            "end_date":     "2015-12-01",
            "severity": {
                "score":                 0.40,
                "transit_reduction_pct": 18,
                "duration_weeks":        21,
                "cause": "El Niño weather pattern, reduced rainfall in watershed"
            },
            "sources": [
                "ACP Annual Report 2015",
                "ACP Notice to Shipping July-November 2015",
                "Journal of Commerce: Panama Canal 2015 drought coverage"
            ]
        },
        "signal_chain": {
            "container_freight_asia_usec": {
                "asset":        "Container Freight Rates Asia-USEC",
                "layer":        2,
                "asset_class":  "freight_rate",
                "direction":    "UP",
                "move_14d":     9.8,
                "move_30d":     16.2,
                "move_60d":     13.4,
                "data_quality": "ESTIMATED",
                "source":       "[DREWRY] estimated from historical reports",
                "notes": "VERIFY: Pull actual Drewry WCI Q3 2015. "
                         "Estimated from 2019 event (sev 0.45) scaled for severity 0.40."
            },
            "shipping_equities_container": {
                "asset":        "Container Shipping Stocks",
                "layer":        3,
                "asset_class":  "equity",
                "direction":    "MIXED",
                "move_14d":     1.8,
                "move_30d":     2.9,
                "move_60d":     -3.2,
                "data_quality": "ESTIMATED",
                "source":       "yfinance estimated",
                "notes": "VERIFY: ZIM not yet public 2015. Pull Maersk/Evergreen actual data."
            },
            "shipping_equities_tanker": {
                "asset":        "Tanker Stocks",
                "layer":        3,
                "asset_class":  "equity",
                "direction":    "UP",
                "move_14d":     3.2,
                "move_30d":     5.4,
                "move_60d":     3.8,
                "data_quality": "ESTIMATED",
                "source":       "yfinance estimated (FRO, INSW historical)",
                "notes": "VERIFY: Pull FRO/INSW actual Jul-Dec 2015."
            },
            "grain_prices_corn": {
                "asset":        "Global Corn Price",
                "layer":        4,
                "asset_class":  "commodity_agricultural",
                "direction":    "FLAT",
                "move_14d":     0.2,
                "move_30d":     0.8,
                "move_60d":     1.1,
                "data_quality": "PRIMARY",
                "source":       "[FRED] PMAIZMTUSD",
                "notes": "IMF data available. Corn in multi-year decline in 2015."
            }
        }
    },

    "panama_drought_2011": {
        "meta": {
            "name":         "Panama Canal Drought 2011",
            "type":         "canal_capacity_restriction",
            "subtype":      "drought_water_level",
            "location":     "Panama Canal, Gatun Lake",
            "trigger_date": "2011-08-01",
            "peak_date":    "2011-09-15",
            "end_date":     "2011-11-30",
            "severity": {
                "score":                 0.32,
                "transit_reduction_pct": 12,
                "duration_weeks":        16,
                "cause": "Seasonal drought, La Niña transition"
            },
            "sources": [
                "ACP Annual Report 2011 (estimated)",
                "Drewry supply-demand review Q3-Q4 2011"
            ]
        },
        "signal_chain": {
            "container_freight_asia_usec": {
                "asset":        "Container Freight Rates Asia-USEC",
                "layer":        2,
                "asset_class":  "freight_rate",
                "direction":    "UP",
                "move_14d":     6.2,
                "move_30d":     11.4,
                "move_60d":     8.8,
                "data_quality": "ESTIMATED",
                "source":       "[DREWRY] estimated",
                "notes": "VERIFY: Least documented event in database. "
                         "Direction UP is confident. Magnitude is estimated."
            },
            "shipping_equities_container": {
                "asset":        "Container Shipping Stocks",
                "layer":        3,
                "asset_class":  "equity",
                "direction":    "MIXED",
                "move_14d":     1.2,
                "move_30d":     2.1,
                "move_60d":     -1.8,
                "data_quality": "ESTIMATED",
                "source":       "estimated",
                "notes": "VERIFY. Confounder: European debt crisis H2 2011."
            },
            "shipping_equities_tanker": {
                "asset":        "Tanker Stocks",
                "layer":        3,
                "asset_class":  "equity",
                "direction":    "UP",
                "move_14d":     2.4,
                "move_30d":     4.1,
                "move_60d":     2.8,
                "data_quality": "ESTIMATED",
                "source":       "estimated",
                "notes": "VERIFY. Confounder: European debt crisis H2 2011."
            },
            "grain_prices_corn": {
                "asset":        "Global Corn Price",
                "layer":        4,
                "asset_class":  "commodity_agricultural",
                "direction":    "FLAT",
                "move_14d":     -0.4,
                "move_30d":     0.6,
                "move_60d":     0.9,
                "data_quality": "PRIMARY",
                "source":       "[FRED] PMAIZMTUSD",
                "notes": "IMF data available. Canal event had minimal grain impact."
            }
        }
    },

    "panama_expansion_delays_2014": {
        "meta": {
            "name":         "Panama Canal Expansion Pre-Opening Delays 2014",
            "type":         "canal_capacity_restriction",
            "subtype":      "construction_labor_dispute",
            "location":     "Panama Canal",
            "trigger_date": "2014-01-20",
            "peak_date":    "2014-03-01",
            "end_date":     "2014-07-31",
            "severity": {
                "score":                 0.25,
                "transit_reduction_pct": 5,
                "duration_weeks":        28,
                "cause": "GUPC/Sacyr contractor dispute. Uncertainty about expansion timeline."
            },
            "sources": [
                "ACP press releases Jan-Mar 2014",
                "Reuters: Panama Canal contractor dispute 2014"
            ]
        },
        "signal_chain": {
            "container_freight_asia_usec": {
                "asset":        "Container Freight Rates Asia-USEC",
                "layer":        2,
                "asset_class":  "freight_rate",
                "direction":    "UP",
                "move_14d":     4.8,
                "move_30d":     8.4,
                "move_60d":     6.2,
                "data_quality": "ESTIMATED",
                "source":       "[DREWRY] estimated",
                "notes": "VERIFY: Pull actual Drewry data Q1 2014. "
                         "Lowest severity in DB (0.25). Pure uncertainty signal."
            },
            "shipping_equities_container": {
                "asset":        "Container Shipping Stocks",
                "layer":        3,
                "asset_class":  "equity",
                "direction":    "FLAT",
                "move_14d":     1.4,
                "move_30d":     2.8,
                "move_60d":     1.2,
                "data_quality": "ESTIMATED",
                "source":       "estimated",
                "notes": "VERIFY: Minimal signal expected."
            },
            "shipping_equities_tanker": {
                "asset":        "Tanker Stocks",
                "layer":        3,
                "asset_class":  "equity",
                "direction":    "FLAT",
                "move_14d":     0.8,
                "move_30d":     1.6,
                "move_60d":     0.4,
                "data_quality": "ESTIMATED",
                "source":       "estimated",
                "notes": "Minimal tanker signal for this event type."
            },
            "grain_prices_corn": {
                "asset":        "Global Corn Price",
                "layer":        4,
                "asset_class":  "commodity_agricultural",
                "direction":    "FLAT",
                "move_14d":     -0.6,
                "move_30d":     0.4,
                "move_60d":     1.8,
                "data_quality": "PRIMARY",
                "source":       "[FRED] PMAIZMTUSD",
                "notes": "IMF data available."
            }
        }
    },

    # =========================================================
    # Port disruption cluster
    # =========================================================

    "covid_port_congestion_la_2021": {
        "meta": {
            "name":         "LA/Long Beach Port Congestion Peak 2021",
            "type":         "port_capacity_disruption",
            "subtype":      "port_congestion_peak",
            "location":     "Port of Los Angeles / Long Beach, California",
            "trigger_date": "2021-09-01",
            "peak_date":    "2021-10-15",
            "end_date":     "2022-04-01",
            "severity": {
                "score":                 0.60,
                "transit_reduction_pct": 45,
                "duration_weeks":        30,
                "cause": "COVID demand surge + labor shortages + 73 ships at anchor."
            },
            "sources": [
                "Marine Exchange of Southern California vessel tracking Sep-Oct 2021",
                "Port of LA/LB monthly statistics 2021",
                "Drewry WCI reports Q3-Q4 2021"
            ]
        },
        "signal_chain": {
            "container_freight_asia_usec": {
                "asset":        "Drewry WCI Asia-USEC Route",
                "layer":        2,
                "asset_class":  "freight_rate",
                "direction":    "UP",
                "move_14d":     22.4,
                "move_30d":     31.8,
                "move_60d":     28.6,
                "data_quality": "PRIMARY",
                "source":       "[DREWRY] [FBX]",
                "notes": "Rates already elevated. Measures marginal congestion-driven increase."
            },
            "shipping_equities_container": {
                "asset":        "Container Shipping Stocks",
                "layer":        3,
                "asset_class":  "equity",
                "direction":    "UP",
                "move_14d":     12.8,
                "move_30d":     18.4,
                "move_60d":     14.2,
                "data_quality": "PRIMARY",
                "source":       "[yfinance]",
                "notes": "Strong equity signal. Rate spike translated directly to earnings."
            },
            "shipping_equities_tanker": {
                "asset":        "Tanker Stocks",
                "layer":        3,
                "asset_class":  "equity",
                "direction":    "FLAT",
                "move_14d":     0.8,
                "move_30d":     1.4,
                "move_60d":     2.2,
                "data_quality": "PRIMARY",
                "source":       "[yfinance]",
                "notes": "Calibration: flat tanker signal for port-specific events."
            },
            "grain_prices_corn": {
                "asset":        "Global Corn Price",
                "layer":        4,
                "asset_class":  "commodity_agricultural",
                "direction":    "UP",
                "move_14d":     3.2,
                "move_30d":     6.8,
                "move_60d":     8.4,
                "data_quality": "PARTIAL",
                "source":       "[IMF] [FRED]",
                "notes": "Confounder: Global grain supply concerns separate from port congestion."
            }
        }
    },

    "la_west_coast_labor_dispute_2022": {
        "meta": {
            "name":         "US West Coast ILWU/PMA Labor Dispute 2022",
            "type":         "port_capacity_disruption",
            "subtype":      "labor_action_slowdown",
            "location":     "US West Coast Ports (LA/LB, Seattle, Oakland)",
            "trigger_date": "2022-07-01",
            "peak_date":    "2022-10-15",
            "end_date":     "2023-06-14",
            "severity": {
                "score":                 0.45,
                "transit_reduction_pct": 25,
                "duration_weeks":        50,
                "cause": "ILWU/PMA contract negotiations. Work-to-rule slowdowns "
                         "reduced throughput ~20-30%."
            },
            "sources": [
                "ILWU/PMA joint statements 2022-2023",
                "PMSA operational reports",
                "Drewry supply chain advisory 2022"
            ]
        },
        "signal_chain": {
            "container_freight_asia_usec": {
                "asset":        "Container Freight Rates Asia-USEC",
                "layer":        2,
                "asset_class":  "freight_rate",
                "direction":    "DOWN",
                "move_14d":     -8.4,
                "move_30d":     -14.2,
                "move_60d":     -22.8,
                "data_quality": "PRIMARY",
                "source":       "[DREWRY] [FBX]",
                "notes": "IMPORTANT CALIBRATION: Rates FELL despite disruption. "
                         "Post-COVID normalization dominated. Disruptions don't always "
                         "mean UP rates — macro context matters."
            },
            "shipping_equities_container": {
                "asset":        "Container Shipping Stocks",
                "layer":        3,
                "asset_class":  "equity",
                "direction":    "DOWN",
                "move_14d":     -6.8,
                "move_30d":     -12.4,
                "move_60d":     -18.2,
                "data_quality": "PRIMARY",
                "source":       "[yfinance]",
                "notes": "Equities fell — consistent with rate normalization."
            },
            "shipping_equities_tanker": {
                "asset":        "Tanker Stocks",
                "layer":        3,
                "asset_class":  "equity",
                "direction":    "UP",
                "move_14d":     4.2,
                "move_30d":     8.8,
                "move_60d":     11.4,
                "data_quality": "PRIMARY",
                "source":       "[yfinance]",
                "notes": "Tankers decoupled from container weakness. "
                         "Confounder: Russian oil sanctions creating separate tanker demand."
            },
            "grain_prices_corn": {
                "asset":        "Global Corn Price",
                "layer":        4,
                "asset_class":  "commodity_agricultural",
                "direction":    "DOWN",
                "move_14d":     -2.4,
                "move_30d":     -6.8,
                "move_60d":     -9.2,
                "data_quality": "PRIMARY",
                "source":       "[IMF] [FRED]",
                "notes": "Grain falling H2 2022 as supply fears eased."
            }
        }
    },

    # =========================================================
    # Grain / conflict cluster
    # =========================================================

    "black_sea_grain_corridor_2022": {
        "meta": {
            "name":         "Black Sea Grain Corridor Disruption 2022",
            "type":         "route_security_disruption",
            "subtype":      "conflict_zone_shipping_halt",
            "location":     "Black Sea / Bosphorus",
            "trigger_date": "2022-02-24",
            "peak_date":    "2022-03-15",
            "end_date":     "2022-07-22",
            "severity": {
                "score":                 0.75,
                "transit_reduction_pct": 90,
                "duration_weeks":        21,
                "cause": "Russian invasion of Ukraine. Black Sea mining. "
                         "Insurance unwillingness to cover Black Sea transits."
            },
            "sources": [
                "IMO situation reports Feb-Jul 2022",
                "USDA grain export disruption reports 2022",
                "Drewry WCI reports Q1-Q2 2022",
                "UN Black Sea Grain Initiative documentation"
            ]
        },
        "signal_chain": {
            "container_freight_asia_usec": {
                "asset":        "Container Freight Rates (indirect impact)",
                "layer":        2,
                "asset_class":  "freight_rate",
                "direction":    "UP",
                "move_14d":     14.2,
                "move_30d":     18.8,
                "move_60d":     12.4,
                "data_quality": "PARTIAL",
                "source":       "[DREWRY]",
                "notes": "Confounder: Rates already elevated from COVID era. "
                         "Black Sea impact indirect on container freight."
            },
            "shipping_equities_container": {
                "asset":        "Container Shipping Stocks",
                "layer":        3,
                "asset_class":  "equity",
                "direction":    "UP",
                "move_14d":     8.4,
                "move_30d":     6.2,
                "move_60d":     -4.8,
                "data_quality": "PARTIAL",
                "source":       "[yfinance]",
                "notes": "Confounder: Broad market selloff on invasion news."
            },
            "shipping_equities_tanker": {
                "asset":        "Tanker Stocks",
                "layer":        3,
                "asset_class":  "equity",
                "direction":    "UP",
                "move_14d":     14.8,
                "move_30d":     22.4,
                "move_60d":     18.6,
                "data_quality": "PRIMARY",
                "source":       "[yfinance]",
                "notes": "STRONG SIGNAL: Russian oil sanctions + rerouting = major tanker uplift."
            },
            "grain_prices_corn": {
                "asset":        "Global Grain Prices — PRIMARY SIGNAL",
                "layer":        4,
                "asset_class":  "commodity_agricultural",
                "direction":    "UP",
                "move_14d":     24.8,
                "move_30d":     38.4,
                "move_60d":     28.2,
                "data_quality": "PRIMARY",
                "source":       "[IMF] [FRED] [USDA]",
                "notes": "LARGEST GRAIN MOVES IN DATABASE. Wheat +50% in first weeks. "
                         "Calibrates upper bound of grain response. "
                         "Do not assume these magnitudes for canal events."
            }
        }
    },

    # =========================================================
    # Cape rerouting — inverse / corroborating signal
    # =========================================================

    "cape_of_good_hope_traffic_surge_2024": {
        "meta": {
            "name":         "Cape of Good Hope Traffic Surge 2024",
            "type":         "route_capacity_surge",
            "subtype":      "alternative_route_congestion",
            "location":     "Cape of Good Hope, South Africa",
            "trigger_date": "2024-02-01",
            "peak_date":    "2024-03-15",
            "end_date":     None,
            "severity": {
                "score":                 0.60,
                "transit_increase_pct":  200,
                "duration_weeks":        40,
                "cause": "Red Sea avoidance drove all major carriers to Cape routing."
            },
            "sources": [
                "South African Port Operations vessel statistics 2024",
                "UNCTAD shipping capacity analysis Feb 2024",
                "Drewry global fleet capacity report Q1 2024"
            ]
        },
        "signal_chain": {
            "container_freight_asia_usec": {
                "asset":        "Container Freight Rates (Cape Premium)",
                "layer":        2,
                "asset_class":  "freight_rate",
                "direction":    "UP",
                "move_14d":     12.4,
                "move_30d":     18.8,
                "move_60d":     22.4,
                "data_quality": "PRIMARY",
                "source":       "[DREWRY] [FBX]",
                "notes": "Capacity reduction from longer voyages. Fewer roundtrips per quarter."
            },
            "shipping_equities_container": {
                "asset":        "Container Shipping Stocks",
                "layer":        3,
                "asset_class":  "equity",
                "direction":    "UP",
                "move_14d":     5.8,
                "move_30d":     9.4,
                "move_60d":     7.2,
                "data_quality": "PARTIAL",
                "source":       "[yfinance]",
                "notes": "Confounder: Hard to separate from continued Red Sea rally."
            },
            "shipping_equities_tanker": {
                "asset":        "Tanker Stocks",
                "layer":        3,
                "asset_class":  "equity",
                "direction":    "UP",
                "move_14d":     4.2,
                "move_30d":     8.6,
                "move_60d":     9.8,
                "data_quality": "PARTIAL",
                "source":       "[yfinance]",
                "notes": "Cape routing = more fuel consumption = tanker revenue upside."
            },
            "grain_prices_corn": {
                "asset":        "Global Grain Prices",
                "layer":        4,
                "asset_class":  "commodity_agricultural",
                "direction":    "FLAT",
                "move_14d":     0.4,
                "move_30d":     1.2,
                "move_60d":     2.1,
                "data_quality": "PARTIAL",
                "source":       "[IMF]",
                "notes": "Minimal grain-specific impact from Cape surge alone."
            }
        }
    }
}


# ============================================================
# DATABASE METADATA — v0.3.0
# ============================================================

DB_METADATA = {
    "version":       "0.3.0",
    "last_updated":  "2025-05",
    "n_events":      len(EVENTS),
    "event_type":    "shipping_chokepoint_disruption",
    "date_range":    "2011-2024",
    "coverage_note": "14 events across 4 disruption types: canal_capacity_restriction, "
                     "route_security_disruption, port_capacity_disruption, route_capacity_surge. "
                     "3 events carry ESTIMATED data quality (2011, 2014, 2015) — valid for "
                     "directional scoring, verify magnitudes before customer reporting.",
    "methodology":   "All move percentages measured from event trigger date. "
                     "PRIMARY=direct measurement, PARTIAL=high confounder count, "
                     "ESTIMATED=calculated from secondary sources.",
    "confidence_floor":   0.30,
    "confidence_ceiling": 0.85,
    "events_needing_verification": [
        "panama_drought_2011",
        "panama_drought_2015",
        "panama_expansion_delays_2014"
    ]
}


if __name__ == "__main__":
    print("=" * 55)
    print(f"NAXA Events Database v{DB_METADATA['version']}")
    print(f"{len(EVENTS)} events | {DB_METADATA['date_range']}")
    print(f"Confidence ceiling: {DB_METADATA['confidence_ceiling']}")
    print("=" * 55)

    quality_counts = {}
    for ev in EVENTS.values():
        for step in ev.get("signal_chain", {}).values():
            q = step.get("data_quality", "ESTIMATED")
            quality_counts[q] = quality_counts.get(q, 0) + 1

    print("\nData quality across all signal chain steps:")
    for q, c in sorted(quality_counts.items()):
        print(f"  {q:<12} {c} steps")

    print(f"\nNeeds verification: {DB_METADATA['events_needing_verification']}")
    print()
    for eid, ev in EVENTS.items():
        m = ev["meta"]
        sev = m["severity"]["score"]
        print(f"  [{m['trigger_date']}] sev={sev} | {m['name']}")