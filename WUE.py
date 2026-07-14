# -*- coding: utf-8 -*-
"""WUE.py — Water Use Efficiency (WUE) of Thailand from Google Earth Engine.

WUE = annual GPP / annual ET, expressed in grams of carbon per kilogram of water
(g C / kg H2O).

Data sources (MODIS, Collection 061, 500 m, 8-day):
    - ET  : MODIS/061/MOD16A2   band "ET"  (scale 0.1  -> mm / 8-day)
    - GPP : MODIS/061/MOD17A2H  band "Gpp" (scale 0.0001 -> kg C / m2 / 8-day)

Pipeline:
    year 8-day scenes -> mask fill values -> sum over the year -> apply scale
    -> WUE = GPP / ET x 1000 -> clip to Thailand -> getMapId -> WUE.html

Usage:
    python WUE.py

Requires one-time authentication:  earthengine authenticate
Note: GEE tile URLs expire after a few hours/days — re-run this script to refresh.
"""
import datetime
import json
import sys

import ee

PROJECT_ID = "physiographic-regions"
YEAR = 2024                       # full calendar year to aggregate
START_DATE = f"{YEAR}-01-01"
END_DATE = f"{YEAR + 1}-01-01"
OUTPUT_FILE = "WUE.html"

# MODIS valid-range upper bounds (values above these are fill / no-data flags).
ET_VALID_MAX = 32700
GPP_VALID_MAX = 30000
ET_SCALE = 0.1                    # -> mm / 8-day  (= kg H2O / m2)
GPP_SCALE = 0.0001               # -> kg C / m2 / 8-day

# WUE visualisation (g C / kg H2O). RdYlGn: low efficiency red, high green.
WUE_PALETTE = ["#d73027", "#fc8d59", "#fee08b", "#d9ef8b", "#91cf60", "#1a9850"]
WUE_MIN = 0.0
WUE_MAX = 4.0
VIS_PARAMS = {"min": WUE_MIN, "max": WUE_MAX, "palette": WUE_PALETTE}


def build_wue():
    thailand = (
        ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017")
        .filter(ee.Filter.eq("country_na", "Thailand"))
        .geometry()
    )

    def mask_et(img):
        et = img.select("ET")
        return et.updateMask(et.lte(ET_VALID_MAX))

    def mask_gpp(img):
        gpp = img.select("Gpp")
        return gpp.updateMask(gpp.lte(GPP_VALID_MAX))

    et_sum = (
        ee.ImageCollection("MODIS/061/MOD16A2")
        .filterBounds(thailand)
        .filterDate(START_DATE, END_DATE)
        .map(mask_et)
        .sum()
        .multiply(ET_SCALE)          # mm / year (= kg H2O / m2 / year)
    )
    gpp_sum = (
        ee.ImageCollection("MODIS/061/MOD17A2H")
        .filterBounds(thailand)
        .filterDate(START_DATE, END_DATE)
        .map(mask_gpp)
        .sum()
        .multiply(GPP_SCALE)         # kg C / m2 / year
    )

    # WUE = GPP / ET; x1000 converts kg C/kg H2O -> g C/kg H2O.
    wue = (
        gpp_sum.divide(et_sum)
        .multiply(1000)
        .updateMask(et_sum.gt(0))
        .clip(thailand)
        .rename("WUE")
    )
    return wue, thailand


def main():
    ee.Initialize(project=PROJECT_ID)

    wue, thailand = build_wue()

    stats = wue.reduceRegion(
        reducer=ee.Reducer.mean().combine(ee.Reducer.minMax(), sharedInputs=True),
        geometry=thailand,
        scale=1000,
        maxPixels=int(1e13),
        bestEffort=True,
    ).getInfo()
    mean_wue = stats.get("WUE_mean")
    min_wue = stats.get("WUE_min")
    max_wue = stats.get("WUE_max")
    if mean_wue is None:
        sys.exit("WUE reduceRegion returned no data — aborting.")
    print(f"WUE over Thailand ({YEAR})  mean={mean_wue:.3f}  "
          f"min={min_wue:.3f}  max={max_wue:.3f}  g C/kg H2O")

    tile_url = wue.getMapId(VIS_PARAMS)["tile_fetcher"].url_format
    print(f"EE tile URL: {tile_url}")

    # Simplified outline (~1 km tolerance) small enough to embed inline in the HTML.
    boundary_geojson = json.dumps(thailand.simplify(1000).getInfo())

    generated = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    legend_stops = ", ".join(WUE_PALETTE)
    html = (
        HTML_TEMPLATE
        .replace("__TILE_URL__", tile_url)
        .replace("__BOUNDARY__", boundary_geojson)
        .replace("__LEGEND_STOPS__", legend_stops)
        .replace("__WUE_MIN__", f"{WUE_MIN:.0f}")
        .replace("__WUE_MAX__", f"{WUE_MAX:.0f}")
        .replace("__MEAN_WUE__", f"{mean_wue:.2f}")
        .replace("__YEAR__", str(YEAR))
        .replace("__GENERATED__", generated)
    )
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {OUTPUT_FILE}")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WUE Thailand __YEAR__ — Water Use Efficiency (MODIS)</title>

    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>

    <style>
        :root {
            --primary: #1a9850;
            --primary-glow: rgba(26, 152, 80, 0.35);
            --bg-dark: #0f172a;
            --panel-bg: rgba(15, 23, 42, 0.78);
            --border-color: rgba(255, 255, 255, 0.08);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Outfit', 'Inter', sans-serif;
            background-color: var(--bg-dark);
            color: var(--text-main);
            height: 100vh;
            overflow: hidden;
        }
        #map { width: 100%; height: 100%; position: absolute; top: 0; left: 0; z-index: 1; }

        .glass-panel {
            background: var(--panel-bg);
            backdrop-filter: blur(16px) saturate(120%);
            -webkit-backdrop-filter: blur(16px) saturate(120%);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
        }
        #control-panel {
            position: absolute;
            top: 16px;
            left: 16px;
            z-index: 1000;
            width: 320px;
            max-width: calc(100vw - 32px);
            padding: 18px 20px;
        }
        #control-panel h1 {
            font-size: 1.05rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        #control-panel h1 i { color: var(--primary); }
        .subtitle { font-size: 0.78rem; color: var(--text-muted); margin: 4px 0 14px; }

        .row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
            margin-bottom: 12px;
            font-size: 0.85rem;
        }
        .row label { display: flex; align-items: center; gap: 8px; cursor: pointer; }
        .row input[type="checkbox"] { accent-color: var(--primary); width: 15px; height: 15px; cursor: pointer; }

        .slider-row { flex-direction: column; align-items: stretch; }
        .slider-row .slider-head { display: flex; justify-content: space-between; font-size: 0.8rem; color: var(--text-muted); margin-bottom: 6px; }
        input[type="range"] { width: 100%; accent-color: var(--primary); cursor: pointer; }

        select {
            background: rgba(255,255,255,0.06);
            color: var(--text-main);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 5px 8px;
            font-family: inherit;
            font-size: 0.8rem;
            cursor: pointer;
        }
        select option { background: var(--bg-dark); }

        .btn {
            width: 100%;
            padding: 8px 12px;
            border: 1px solid var(--border-color);
            border-radius: 10px;
            background: rgba(26, 152, 80, 0.15);
            color: var(--text-main);
            font-family: inherit;
            font-size: 0.85rem;
            cursor: pointer;
            transition: var(--transition);
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }
        .btn:hover { background: rgba(26, 152, 80, 0.35); box-shadow: 0 0 16px var(--primary-glow); }

        .legend { margin-top: 16px; }
        .legend .legend-title { font-size: 0.8rem; margin-bottom: 8px; }
        .legend .bar {
            height: 14px;
            border-radius: 7px;
            background: linear-gradient(to right, __LEGEND_STOPS__);
            border: 1px solid var(--border-color);
        }
        .legend .scale { display: flex; justify-content: space-between; font-size: 0.72rem; color: var(--text-muted); margin-top: 5px; }
        .legend .unit { font-size: 0.7rem; color: var(--text-muted); text-align: center; margin-top: 3px; }

        .meta {
            margin-top: 14px;
            padding-top: 12px;
            border-top: 1px solid var(--border-color);
            font-size: 0.72rem;
            color: var(--text-muted);
            line-height: 1.6;
        }
        .meta i { width: 14px; text-align: center; margin-right: 4px; }
        .meta .big { font-size: 0.95rem; color: var(--text-main); font-weight: 600; }

        .leaflet-control-attribution { background: rgba(15, 23, 42, 0.7) !important; color: var(--text-muted) !important; }
        .leaflet-control-attribution a { color: var(--primary) !important; }
    </style>
</head>
<body>
    <div id="map"></div>

    <div id="control-panel" class="glass-panel">
        <h1><i class="fa-solid fa-leaf"></i> WUE Thailand __YEAR__</h1>
        <div class="subtitle">Water Use Efficiency = GPP / ET · MODIS MOD17A2H &amp; MOD16A2 · Google Earth Engine</div>

        <div class="row">
            <label><input type="checkbox" id="toggle-wue" checked> WUE Layer</label>
        </div>
        <div class="row slider-row">
            <div class="slider-head"><span>Opacity</span><span id="opacity-value">85%</span></div>
            <input type="range" id="opacity-slider" min="0" max="100" value="85">
        </div>
        <div class="row">
            <label><input type="checkbox" id="toggle-boundary" checked> ขอบเขตประเทศไทย</label>
        </div>
        <div class="row">
            <span>Basemap</span>
            <select id="basemap-select">
                <option value="satellite" selected>Google Satellite</option>
                <option value="hybrid">Google Hybrid</option>
            </select>
        </div>
        <button class="btn" id="zoom-thailand"><i class="fa-solid fa-location-crosshairs"></i> Zoom to Thailand</button>

        <div class="legend">
            <div class="legend-title">Water Use Efficiency</div>
            <div class="bar"></div>
            <div class="scale"><span>__WUE_MIN__</span><span>__WUE_MAX__</span></div>
            <div class="unit">g C / kg H<sub>2</sub>O</div>
        </div>

        <div class="meta">
            <div><span class="big">ค่าเฉลี่ยทั้งประเทศ: __MEAN_WUE__ g C/kg H<sub>2</sub>O</span></div>
            <div><i class="fa-regular fa-calendar"></i> ปีข้อมูล: __YEAR__ (MODIS 8-day, 500 m)</div>
            <div><i class="fa-solid fa-clock-rotate-left"></i> สร้างเมื่อ: __GENERATED__</div>
            <div><i class="fa-solid fa-triangle-exclamation"></i> Tile URL ของ GEE มีอายุจำกัด — รัน WUE.py ใหม่หากภาพไม่แสดง</div>
        </div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
    <script>
        var THAILAND_BOUNDS = L.latLngBounds([5.6, 97.3], [20.5, 105.7]);

        var map = L.map('map', { zoomControl: false }).fitBounds(THAILAND_BOUNDS);
        L.control.zoom({ position: 'bottomright' }).addTo(map);

        var googleSatellite = L.tileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', {
            maxZoom: 20, attribution: '&copy; Google'
        });
        var googleHybrid = L.tileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', {
            maxZoom: 20, attribution: '&copy; Google'
        });
        googleSatellite.addTo(map);

        var wueLayer = L.tileLayer('__TILE_URL__', {
            maxZoom: 20, opacity: 0.85,
            attribution: 'MODIS MOD16A2/MOD17A2H · Google Earth Engine'
        }).addTo(map);

        document.getElementById('toggle-wue').addEventListener('change', function () {
            this.checked ? map.addLayer(wueLayer) : map.removeLayer(wueLayer);
        });
        document.getElementById('opacity-slider').addEventListener('input', function () {
            wueLayer.setOpacity(this.value / 100);
            document.getElementById('opacity-value').textContent = this.value + '%';
        });
        document.getElementById('basemap-select').addEventListener('change', function () {
            map.removeLayer(googleSatellite);
            map.removeLayer(googleHybrid);
            (this.value === 'hybrid' ? googleHybrid : googleSatellite).addTo(map);
            if (map.hasLayer(wueLayer)) { wueLayer.bringToFront(); }
        });
        document.getElementById('zoom-thailand').addEventListener('click', function () {
            map.fitBounds(THAILAND_BOUNDS);
        });

        var boundary = L.geoJSON(__BOUNDARY__, {
            style: { color: '#1a9850', weight: 2, fill: false }
        }).addTo(map);
        document.getElementById('toggle-boundary').addEventListener('change', function () {
            this.checked ? map.addLayer(boundary) : map.removeLayer(boundary);
        });
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
