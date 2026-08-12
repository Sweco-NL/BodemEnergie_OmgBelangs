# -*- coding: utf-8 -*-
"""
Script voor uitdraaien GIS plots Provincie Utrecht voor uitdraaien omgevingsbelangen vooronderzoek/quikscan. 
Eerste proof of conceptversie t.b.v. herfstkick-off.
Author: BABELING
Versie: A.0.2.
Key features:
- RD-punt + buffer
- Meerdere ArcGIS FeatureServer-services automatisch ophalen
- Per service een aparte plot met dezelfde opbouw
- Ondergrondkaart via OpenBasisKaart

To do:
- helperfunctie voor service-config voor duidelijker services toevoegen
- Layers met verschillende features omzetten in sublayers met duidelijke labels uit ArcGIS resp.
- Omliggende systemen LGR toevoegen a.d.h.v. WKO-tool.
"""

import sys
from pathlib import Path
import json

import geopandas as gpd
import pandas as pd
import matplotlib as mpl
from matplotlib.colors import to_hex
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import requests
import urllib3
from shapely.geometry import Point, shape

# --------------------------------------------------
# VHGM_FLOPY REPO
# --------------------------------------------------
VHGM_FLOPY_REPO = Path(r"C:\Users\NLB467\GitHub\BodemEnergie_vhgm_flopy")
if str(VHGM_FLOPY_REPO) not in sys.path:
    sys.path.insert(0, str(VHGM_FLOPY_REPO))

from vhgm_flopy.plots import (
    get_map as vhgm_get_map,
    scale_bar,
    title_inside,
)

# --------------------------------------------------
# OPENBASISKAART
# --------------------------------------------------
try:
    from achtergrondkaart import OpenBasisKaart
except ImportError:
    OpenBasisKaart = None

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ----------------------------
# Instellingen
# ----------------------------
rd_x = 141589
rd_y = 457767
radius_m = 1000

point = Point(rd_x, rd_y)
buffer_geom = point.buffer(radius_m)

gdf_point = gpd.GeoDataFrame(geometry=[point], crs="EPSG:28992")
gdf_buffer = gpd.GeoDataFrame(geometry=[buffer_geom], crs="EPSG:28992")

rings = [list(map(list, buffer_geom.exterior.coords))]
geometry_json = json.dumps({
    "rings": rings,
    "spatialReference": {"wkid": 28992}
})

# --------------------------------------------------
# SERVICE-CONFIGURATIE
# --------------------------------------------------
services = [
    {
        "name": "Grondwaterbelangen",
        "service_url": "https://agrest.geodata-utrecht.nl/arcgis/rest/services/w01_2_grondwater/FeatureServer",
        "layers_to_query": {
            745: "Strategische_grondwatervoorraad",
            391: "Grondwaterbeschermingszones"
        },
        "legend_labels": {
            "Strategische_grondwatervoorraad": "Strategische grondwatervoorraad",
            "Grondwaterbeschermingszones": "Grondwaterbeschermingszones"
        },
        "label_fields": {
            "Strategische_grondwatervoorraad": "WINNING",
            "Grondwaterbeschermingszones": "TYPE"
        },
        "split_features": True,
        "cmap_name": "tab20"
    },
    {
        "name": "Natuurbelangen",
        "service_url": "https://agrest.geodata-utrecht.nl/arcgis/rest/services/n01_2_2_natuur_beleid/FeatureServer",
        "layers_to_query": {
            833: "Natuurnetwerk_Nederland",
            744: "Natura2000_gebieden"
        },
        "legend_labels": {
            "Natuurnetwerk_Nederland": "Natuurnetwerk Nederland",
            "Natura2000_gebieden": "Natura 2000-gebieden"
        },
        "label_fields": {
            "Natuurnetwerk_Nederland": "OMSCHRIJVING",
            "Natura2000_gebieden": "NAAM_N2K"
        },
        "split_features": True,
        "cmap_name": "tab20"
    },
    {
         "name": "Aardkundige waarden",
         "service_url": "https://agrest.geodata-utrecht.nl/arcgis/rest/services/m01_2_bodem/FeatureServer",
         "layers_to_query": {
             951: "Aardkundige_waarden"
        },
        "legend_labels": {
            "Aardkundige_waarden": "Aardkundige Waarden"
        },
        "label_fields": {
            "Aardkundige_waarden": "TOELICHT"
        },
        "split_features": True,
        "cmap_name": "tab20"
    },
    {
         "name": "Bodemkwaliteit",
         "service_url": "https://agrest.geodata-utrecht.nl/arcgis/rest/services/m01_2_bodem/FeatureServer",
         "layers_to_query": {
             159: "Vereenvoudige_bodemkaart",
             598: "Loodverwachtingskaart"
        },
        "legend_labels": {
            "Vereenvoudige_bodemkaart": "Vereenvoudige bodemkaart",
            "Loodverwachtingskaart": "Loodverwachtingskaart"
        },
        "label_fields": {
            "Vereenvoudige_bodemkaart": "BODEM_NAAM",
            "Loodverwachtingskaart": "OMSCHRIJVING"
        },
        "split_features": True,
        "cmap_name": "tab20"
    }
]

# --------------------------------------------------
# QUERY-FUNCTIE
# --------------------------------------------------
def query_layer(service_url, layer_id, layer_name):
    query_url = f"{service_url}/{layer_id}/query"

    params = {
        "f": "json",
        "geometry": geometry_json,
        "geometryType": "esriGeometryPolygon",
        "inSR": 28992,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": 28992
    }

    resp = requests.get(query_url, params=params, verify=False, timeout=60)
    resp.raise_for_status()
    result = resp.json()

    if "error" in result:
        raise RuntimeError(
            f"ArcGIS error for layer {layer_id} ({layer_name}): {result['error']}"
        )

    features = result.get("features", [])
    print(f"Layer {layer_id} ({layer_name}): {len(features)} features")

    if not features:
        return gpd.GeoDataFrame(columns=["geometry"], geometry="geometry", crs="EPSG:28992")

    records = []
    geoms = []

    for f in features:
        records.append(f.get("attributes", {}))
        geom = f.get("geometry", {})

        if "rings" in geom:
            geoms.append(shape({
                "type": "Polygon",
                "coordinates": geom["rings"]
            }))
        elif "paths" in geom:
            geoms.append(shape({
                "type": "MultiLineString",
                "coordinates": geom["paths"]
            }))
        elif "x" in geom and "y" in geom:
            geoms.append(shape({
                "type": "Point",
                "coordinates": (geom["x"], geom["y"])
            }))
        else:
            geoms.append(None)

    return gpd.GeoDataFrame(records, geometry=geoms, crs="EPSG:28992")

# --------------------------------------------------
# PLOT-FUNCTIE
# --------------------------------------------------
def generate_colors(n, cmap_name="tab20"):
    cmap = plt.get_cmap(cmap_name)
    if n <= 1:
        return [to_hex(cmap(0.0))]
    return [to_hex(cmap(i / max(n - 1, 1))) for i in range(n)]

def get_label_from_field(row, field_name):
    if not field_name:
        return None
    if field_name not in row:
        return None

    value = row[field_name]
    if pd.isna(value):
        return None

    text = str(value).strip()
    if not text:
        return None

    return text


def plot_features_separately(ax, gdf, prefix, label_field=None, alpha=0.45, edgecolor="black", cmap_name="tab20"):
    legend_patches = []

    if gdf.empty:
        return legend_patches

    colors = generate_colors(len(gdf), cmap_name=cmap_name)

    for i, (_, row) in enumerate(gdf.iterrows()):
        feature_gdf = gpd.GeoDataFrame([row], geometry="geometry", crs=gdf.crs)
        color = colors[i]

        feature_gdf.plot(
            ax=ax,
            facecolor=color,
            edgecolor=edgecolor,
            linewidth=1,
            alpha=alpha
        )

        feature_label = get_label_from_field(row, label_field)
        if not feature_label:
            feature_label = f"{prefix} {i + 1}"

        legend_patches.append(
            Patch(
                facecolor=color,
                edgecolor=edgecolor,
                alpha=alpha,
                label=feature_label
            )
        )

    return legend_patches

def get_layer_display_name(service_url, layer_id, fallback_name):
    url = f"{service_url}/{layer_id}?f=json"
    resp = requests.get(url, verify=False, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data.get("name", fallback_name)

def plot_service(service_cfg, extent):
    fig, ax = vhgm_get_map(extent)

    if OpenBasisKaart is not None:
        try:
            OpenBasisKaart(ax, extent)
        except Exception as e:
            print(f"OpenBasisKaart kon niet worden toegevoegd voor {service_cfg['name']}.")
            print(e)

    legend_elements = []

    results = {}
    for layer_id, layer_key in service_cfg["layers_to_query"].items():
        display_name = get_layer_display_name(service_cfg["service_url"], layer_id, layer_key)
        results[layer_key] = query_layer(service_cfg["service_url"], layer_id, display_name)

    for layer_key, gdf in results.items():
        if gdf.empty:
            continue

        label = service_cfg.get("legend_labels", {}).get(layer_key, layer_key)
        
        if service_cfg.get("split_features", False):
            label_field = service_cfg.get("label_fields", {}).get(layer_key)

            legend_elements += plot_features_separately(
                ax=ax,
                gdf=gdf,
                prefix=label,
                label_field=label_field,
                alpha=0.45,
                edgecolor="black",
                cmap_name=service_cfg.get("cmap_name", "tab20")
    )
        else:
            colors = service_cfg["colors"].get(layer_key, "black")

            gdf.plot(
                ax=ax,
                facecolor=colors,
                edgecolor=colors,
                linewidth=1,
                alpha=0.3
            )
            legend_elements.append(
                Patch(
                    facecolor=colors,
                    edgecolor=colors,
                    alpha=0.3,
                    label=label
                )   
            )

    gdf_buffer.boundary.plot(
        ax=ax, color="red", linestyle="--", linewidth=2
    )
    gdf_point.plot(
        ax=ax, color="red", marker="x", markersize=80
    )

    legend_elements += [
        Line2D([0], [0], color="red", linestyle="--", linewidth=2, label=f"{radius_m} m zoekstraal"),
        Line2D([0], [0], marker="x", color="red", linestyle="None", markersize=8, label="Onderzoekslocatie"),
    ]

    title_inside(service_cfg["name"], ax)
    scale_bar(ax)
    ax.set_aspect("equal", adjustable="box")
    ax.legend(handles=legend_elements, loc="upper right", title="Legenda")
    return fig, ax


# --------------------------------------------------
# EXTENT BEPALEN
# --------------------------------------------------
xmin, ymin, xmax, ymax = gdf_buffer.total_bounds
margin = 200
extent = [xmin - margin, xmax + margin, ymin - margin, ymax + margin]

# --------------------------------------------------
# ALLE SERVICES PLOTEN
# --------------------------------------------------
for service_cfg in services:
    plot_service(service_cfg, extent)

plt.show()