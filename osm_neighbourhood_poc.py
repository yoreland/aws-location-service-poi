#!/usr/bin/env python3
"""
OSM Neighbourhood Polygon POC
从 OpenStreetMap 获取带真实边界的 neighbourhood 数据
"""

import json
import sys
import time
from typing import List, Dict, Any
import requests

# Overpass API endpoint
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

def query_osm_neighbourhoods(city_name: str, admin_level: int = 9, limit: int = 20) -> Dict[str, Any]:
    """
    从 OSM 获取指定城市的 neighbourhood 边界数据
    
    Args:
        city_name: 城市名称（如 "Tokyo", "Paris"）
        admin_level: OSM 行政级别（9=区/ward, 10=町/neighbourhood）
        limit: 最多返回多少个区域
    
    Returns:
        包含 neighbourhoods 和 metadata 的字典
    """
    
    # Overpass QL 查询
    # 查询指定城市的行政区划边界
    query = f"""
    [out:json][timeout:60];
    area[name="{city_name}"]->.city;
    (
      relation["boundary"="administrative"]["admin_level"="{admin_level}"](area.city);
    );
    out geom {limit};
    """
    
    print(f"🔍 正在查询 {city_name} 的 neighbourhood 边界数据...")
    print(f"   Admin Level: {admin_level}, Limit: {limit}")
    
    try:
        response = requests.post(
            OVERPASS_URL,
            data={'data': query},
            timeout=90
        )
        response.raise_for_status()
        data = response.json()
        
        print(f"✅ OSM 返回了 {len(data.get('elements', []))} 个区域")
        
        return data
        
    except requests.exceptions.Timeout:
        print("❌ 查询超时，请稍后重试")
        return {"elements": []}
    except Exception as e:
        print(f"❌ 查询失败: {e}")
        return {"elements": []}


def osm_to_geojson(osm_data: Dict[str, Any], city_name: str) -> Dict[str, Any]:
    """
    将 OSM 数据转换为 GeoJSON FeatureCollection
    
    Args:
        osm_data: OSM Overpass API 返回的原始数据
        city_name: 城市名称
    
    Returns:
        GeoJSON FeatureCollection
    """
    
    features = []
    
    for element in osm_data.get('elements', []):
        if element['type'] != 'relation':
            continue
        
        tags = element.get('tags', {})
        name = tags.get('name', tags.get('name:en', 'Unknown'))
        
        # 提取 Polygon 边界
        coordinates = []
        
        # OSM relation 的 members 包含 way
        for member in element.get('members', []):
            if member.get('role') == 'outer' and member.get('type') == 'way':
                way_coords = []
                for node in member.get('geometry', []):
                    way_coords.append([node['lon'], node['lat']])
                
                if len(way_coords) > 3:  # 至少4个点才能形成闭合多边形
                    coordinates.append(way_coords)
        
        if not coordinates:
            print(f"⚠️  跳过 {name}: 无有效边界数据")
            continue
        
        # 构建 GeoJSON Feature
        feature = {
            "type": "Feature",
            "properties": {
                "name": name,
                "name_en": tags.get('name:en', name),
                "name_local": tags.get('name:ja') or tags.get('name:ko') or tags.get('name:zh', name),
                "admin_level": tags.get('admin_level'),
                "type": tags.get('type'),
                "osm_id": element.get('id'),
                "city": city_name,
            },
            "geometry": {
                "type": "Polygon" if len(coordinates) == 1 else "MultiPolygon",
                "coordinates": coordinates if len(coordinates) == 1 else [coordinates]
            }
        }
        
        features.append(feature)
        print(f"✅ {name} - {len(coordinates)} polygon(s)")
    
    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "city": city_name,
            "source": "OpenStreetMap",
            "count": len(features),
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
        }
    }


def generate_visualization_html(geojson: Dict[str, Any], output_file: str):
    """
    生成交互式地图可视化 HTML
    
    Args:
        geojson: GeoJSON FeatureCollection
        output_file: 输出文件路径
    """
    
    city = geojson['metadata']['city']
    count = geojson['metadata']['count']
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{city} Neighbourhoods with Real Boundaries (OSM)</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
:root {{
  --bg: #0d1117; --bg2: #161b22; --bg3: #21262d; --border: #30363d;
  --text: #e6edf3; --text-dim: #7d8590; --accent: #58a6ff;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size:14px; color:var(--text); background:var(--bg); }}

.header {{ padding:24px 32px 16px; border-bottom:1px solid var(--border); }}
.header h1 {{ font-size:22px; font-weight:600; margin-bottom:4px; }}
.header .sub {{ color:var(--text-dim); font-size:13px; }}
.header .badge {{ display:inline-block; background:#238636; color:#fff; padding:4px 12px; border-radius:12px; font-size:11px; font-weight:600; margin-left:12px; }}

.kpi-strip {{ display:flex; gap:1px; background:var(--border); margin:0; }}
.kpi {{ flex:1; background:var(--bg2); padding:18px 20px; text-align:center; }}
.kpi .val {{ font-size:28px; font-weight:700; color:var(--accent); }}
.kpi .lbl {{ font-size:10px; text-transform:uppercase; letter-spacing:.1em; color:var(--text-dim); margin-top:4px; }}

.main {{ display:grid; grid-template-columns:320px 1fr; height:calc(100vh - 180px); }}
.sidebar {{ background:var(--bg2); border-right:1px solid var(--border); overflow-y:auto; }}
.map-area {{ position:relative; }}

.list-item {{ padding:12px 16px; border-bottom:1px solid var(--border); cursor:pointer; transition:background .15s; }}
.list-item:hover {{ background:var(--bg3); }}
.list-item .name {{ font-size:13px; font-weight:600; }}
.list-item .meta {{ font-size:11px; color:var(--text-dim); margin-top:2px; }}

#map {{ width:100%; height:100%; }}
.leaflet-popup-content-wrapper {{ background:var(--bg2)!important; color:var(--text)!important; border:1px solid var(--border)!important; border-radius:8px!important; }}
.leaflet-popup-tip {{ background:var(--bg2)!important; }}
.leaflet-popup-content {{ font-size:13px; line-height:1.6; }}
.leaflet-popup-content b {{ color:var(--accent); }}
</style>
</head>
<body>

<div class="header">
  <h1>{city} Neighbourhoods<span class="badge">OSM Polygons</span></h1>
  <div class="sub">Source: OpenStreetMap (Overpass API) · Real boundary geometry · {geojson['metadata']['generated_at']}</div>
</div>

<div class="kpi-strip">
  <div class="kpi"><div class="val">{count}</div><div class="lbl">Neighbourhoods</div></div>
  <div class="kpi"><div class="val">OSM</div><div class="lbl">Data Source</div></div>
  <div class="kpi"><div class="val">Polygon</div><div class="lbl">Real Boundaries</div></div>
</div>

<div class="main">
  <div class="sidebar" id="sidebar"></div>
  <div class="map-area">
    <div id="map"></div>
  </div>
</div>

<script>
const geojsonData = {json.dumps(geojson, ensure_ascii=False, indent=2)};

// 初始化地图
const map = L.map('map').setView([35.6895, 139.6917], 11);

L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
  attribution: '&copy; <a href="https://www.openstreetmap.org/">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
  subdomains: 'abcd',
  maxZoom: 19,
}}).addTo(map);

// 渲染 GeoJSON 图层
const colors = ['#58a6ff', '#3fb950', '#f85149', '#d29922', '#a371f7', '#ec6cb9'];
let colorIndex = 0;

const geoJsonLayer = L.geoJSON(geojsonData, {{
  style: function(feature) {{
    const color = colors[colorIndex++ % colors.length];
    return {{
      color: color,
      weight: 2,
      opacity: 0.8,
      fillColor: color,
      fillOpacity: 0.15
    }};
  }},
  onEachFeature: function(feature, layer) {{
    const props = feature.properties;
    layer.bindPopup(`
      <b>${{props.name}}</b><br>
      ${{props.name_local !== props.name ? props.name_local + '<br>' : ''}}
      <span style="color:#7d8590">OSM ID: ${{props.osm_id}}</span><br>
      <span style="color:#7d8590">Admin Level: ${{props.admin_level}}</span>
    `);
  }}
}}).addTo(map);

// 自动缩放到所有边界
map.fitBounds(geoJsonLayer.getBounds());

// 侧边栏列表
const sidebar = document.getElementById('sidebar');
geojsonData.features.forEach((feature, idx) => {{
  const div = document.createElement('div');
  div.className = 'list-item';
  div.innerHTML = `
    <div class="name">${{feature.properties.name}}</div>
    <div class="meta">${{feature.properties.name_local}}</div>
  `;
  div.onclick = () => {{
    const layer = geoJsonLayer.getLayers()[idx];
    map.fitBounds(layer.getBounds());
    layer.openPopup();
  }};
  sidebar.appendChild(div);
}});
</script>

</body>
</html>"""
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"\n✅ 可视化 HTML 已生成: {output_file}")


def main():
    """主函数"""
    
    # 默认参数
    city = "Tokyo"
    admin_level = 9  # 9=区/ward (如涩谷区), 10=町/neighbourhood
    limit = 20
    
    # 支持命令行参数
    if len(sys.argv) > 1:
        city = sys.argv[1]
    if len(sys.argv) > 2:
        admin_level = int(sys.argv[2])
    if len(sys.argv) > 3:
        limit = int(sys.argv[3])
    
    print(f"\n{'='*60}")
    print(f"  OSM Neighbourhood Polygon POC")
    print(f"{'='*60}\n")
    
    # Step 1: 查询 OSM 数据
    osm_data = query_osm_neighbourhoods(city, admin_level, limit)
    
    if not osm_data.get('elements'):
        print("\n❌ 未获取到数据，请检查城市名称或网络连接")
        return
    
    # Step 2: 转换为 GeoJSON
    print(f"\n🔄 转换为 GeoJSON...")
    geojson = osm_to_geojson(osm_data, city)
    
    if not geojson['features']:
        print("\n❌ 未能提取有效的边界数据")
        return
    
    # Step 3: 保存 GeoJSON
    geojson_file = f"osm_{city.lower()}_neighbourhoods.geojson"
    with open(geojson_file, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)
    print(f"✅ GeoJSON 已保存: {geojson_file}")
    
    # Step 4: 生成可视化
    html_file = f"osm_{city.lower()}_neighbourhoods_viz.html"
    generate_visualization_html(geojson, html_file)
    
    print(f"\n{'='*60}")
    print(f"  POC 完成！")
    print(f"{'='*60}")
    print(f"  📄 GeoJSON:  {geojson_file}")
    print(f"  🌐 HTML:     {html_file}")
    print(f"  📊 区域数量: {len(geojson['features'])}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
