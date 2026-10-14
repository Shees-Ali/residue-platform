"""Known districts (centroids) and the synthetic village list used by the seed."""

DISTRICTS: dict[str, tuple[float, float]] = {
    "Lahore": (31.52, 74.36),
    "Sheikhupura": (31.71, 73.98),
    "Kasur": (31.12, 74.45),
    "Faisalabad": (31.42, 73.08),
    "Okara": (30.81, 73.45),
}

# Synthetic village names per district (no real farmer data). Offsets are degrees from the
# district centroid, so the seed gives each village stable coordinates.
VILLAGES: dict[str, dict[str, tuple[float, float]]] = {
    "Lahore": {
        "Raiwind": (-0.12, 0.02), "Barki": (-0.05, 0.14), "Jallo": (0.06, 0.08),
        "Manga": (-0.20, -0.06), "Niaz Baig": (-0.09, -0.10), "Chunian Road": (-0.28, -0.02),
    },
    "Sheikhupura": {
        "Farooqabad": (0.05, -0.12), "Sharaqpur": (0.00, 0.10), "Muridke": (0.18, 0.12),
        "Safdarabad": (-0.14, -0.24), "Ferozewala": (0.10, 0.20), "Narang": (0.20, 0.04),
    },
    "Kasur": {
        "Pattoki": (-0.08, -0.30), "Chunian": (-0.20, -0.05), "Khudian": (0.02, 0.06),
        "Kot Radha Kishan": (-0.14, -0.12), "Raja Jang": (-0.04, -0.18),
        "Mustafabad": (-0.10, 0.10),
    },
    "Faisalabad": {
        "Jaranwala": (0.12, 0.08), "Samundri": (-0.10, -0.12), "Tandlianwala": (-0.22, -0.02),
        "Chak Jhumra": (0.06, -0.10), "Sidhar": (-0.04, 0.12), "Khurrianwala": (0.14, -0.04),
    },
    "Okara": {
        "Renala Khurd": (0.10, -0.10), "Depalpur": (0.08, 0.14), "Haveli Lakha": (-0.06, -0.18),
        "Basirpur": (-0.12, 0.04), "Mandi Ahmadabad": (0.02, 0.20),
        "Hujra Shah Muqeem": (0.14, -0.02),
    },
}
