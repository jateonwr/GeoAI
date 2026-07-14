# -*- coding: utf-8 -*-
"""Generate sentinel2.html — Sentinel-2 cloud-free median composite of Thailand (2026)
overlaid on Google Maps Satellite, computed with Google Earth Engine.

Usage:
    python generate_sentinel2.py

Requires one-time authentication:  earthengine authenticate
Note: GEE tile URLs expire after a few hours/days — re-run this script to refresh.
"""
import datetime
import json
import sys

import ee

PROJECT_ID = "physiographic-regions"
START_DATE = "2026-01-01"
END_DATE = "2027-01-01"
CS_BAND = "cs_cdf"      # Cloud Score+ band
CS_THRESHOLD = 0.6      # keep pixels with cloud score >= 0.6 (higher = stricter)
OUTPUT_FILE = "sentinel2.html"

VIS_PARAMS = {"bands": ["B4", "B3", "B2"], "min": 0, "max": 3000, "gamma": 1.1}


def build_composite():
    thailand = (
        ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017")
        .filter(ee.Filter.eq("country_na", "Thailand"))
        .geometry()
    )

    s2 = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(thailand)
        .filterDate(START_DATE, END_DATE)
    )
    cloud_score = ee.ImageCollection("GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED")

    def mask_clouds(img):
        return img.updateMask(img.select(CS_BAND).gte(CS_THRESHOLD))

    composite = (
        s2.linkCollection(cloud_score, [CS_BAND])
        .map(mask_clouds)
        .median()
        .clip(thailand)
    )
    return composite, thailand, s2


def main():
    ee.Initialize(project=PROJECT_ID)

    composite, thailand, s2 = build_composite()

    image_count = s2.size().getInfo()
    print(f"Sentinel-2 scenes in composite: {image_count}")
    if image_count == 0:
        sys.exit("No Sentinel-2 scenes found for the given period — aborting.")

    tile_url = composite.getMapId(VIS_PARAMS)["tile_fetcher"].url_format
    print(f"EE tile URL: {tile_url}")

    # Simplified outline (~1 km tolerance) small enough to embed inline in the HTML.
    boundary_geojson = json.dumps(thailand.simplify(1000).getInfo())

    generated = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    html = (
        HTML_TEMPLATE
        .replace("__TILE_URL__", tile_url)
        .replace("__BOUNDARY__", boundary_geojson)
        .replace("__IMAGE_COUNT__", f"{image_count:,}")
        .replace("__GENERATED__", generated)
        .replace("__PERIOD__", f"{START_DATE} → {END_DATE}")
    )
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {OUTPUT_FILE}")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sentinel-2 Thailand 2026 — Cloud-free Median</title>

    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>

    <style>
        :root {
            --primary: #3b82f6;
            --primary-glow: rgba(59, 130, 246, 0.35);
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
        input[type="range"] {
            width: 100%;
            accent-color: var(--primary);
            cursor: pointer;
        }

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
            background: rgba(59, 130, 246, 0.15);
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
        .btn:hover { background: rgba(59, 130, 246, 0.35); box-shadow: 0 0 16px var(--primary-glow); }

        .meta {
            margin-top: 14px;
            padding-top: 12px;
            border-top: 1px solid var(--border-color);
            font-size: 0.72rem;
            color: var(--text-muted);
            line-height: 1.6;
        }
        .meta i { width: 14px; text-align: center; margin-right: 4px; }

        .leaflet-control-attribution { background: rgba(15, 23, 42, 0.7) !important; color: var(--text-muted) !important; }
        .leaflet-control-attribution a { color: var(--primary) !important; }
    </style>
</head>
<body>
    <div id="map"></div>

    <div id="control-panel" class="glass-panel">
        <h1><i class="fa-solid fa-satellite"></i> Sentinel-2 Thailand 2026</h1>
        <div class="subtitle">Cloud-free median composite (Cloud Score+) · Google Earth Engine</div>

        <div class="row">
            <label><input type="checkbox" id="toggle-s2" checked> Sentinel-2 Median</label>
        </div>
        <div class="row slider-row">
            <div class="slider-head"><span>Opacity</span><span id="opacity-value">100%</span></div>
            <input type="range" id="opacity-slider" min="0" max="100" value="100">
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

        <div class="meta">
            <div><i class="fa-regular fa-calendar"></i> ช่วงข้อมูล: __PERIOD__</div>
            <div><i class="fa-solid fa-images"></i> จำนวนภาพ: __IMAGE_COUNT__ scenes</div>
            <div><i class="fa-solid fa-clock-rotate-left"></i> สร้างเมื่อ: __GENERATED__</div>
            <div><i class="fa-solid fa-triangle-exclamation"></i> Tile URL ของ GEE มีอายุจำกัด — รัน generate_sentinel2.py ใหม่หากภาพไม่แสดง</div>
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

        var s2Layer = L.tileLayer('__TILE_URL__', {
            maxZoom: 20,
            attribution: 'Sentinel-2 &copy; ESA/Copernicus · Google Earth Engine'
        }).addTo(map);

        var boundary = L.geoJSON(__BOUNDARY__, {
            style: { color: '#3b82f6', weight: 2, fill: false, dashArray: '6 4' }
        }).addTo(map);

        // --- Controls ---
        document.getElementById('toggle-s2').addEventListener('change', function () {
            this.checked ? map.addLayer(s2Layer) : map.removeLayer(s2Layer);
        });
        document.getElementById('toggle-boundary').addEventListener('change', function () {
            this.checked ? map.addLayer(boundary) : map.removeLayer(boundary);
        });
        document.getElementById('opacity-slider').addEventListener('input', function () {
            s2Layer.setOpacity(this.value / 100);
            document.getElementById('opacity-value').textContent = this.value + '%';
        });
        document.getElementById('basemap-select').addEventListener('change', function () {
            map.removeLayer(googleSatellite);
            map.removeLayer(googleHybrid);
            (this.value === 'hybrid' ? googleHybrid : googleSatellite).addTo(map);
            if (map.hasLayer(s2Layer)) { s2Layer.bringToFront(); }
        });
        document.getElementById('zoom-thailand').addEventListener('click', function () {
            map.fitBounds(THAILAND_BOUNDS);
        });
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
