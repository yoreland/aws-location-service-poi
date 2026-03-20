# OSM Neighbourhood Polygon POC - 技术方案说明

## 📋 概述

这个 POC 演示了如何使用 **OpenStreetMap (OSM)** 数据获取**真实的不规则地理边界**（Polygon/MultiPolygon），解决 AWS Location Service 只提供中心点坐标的限制。

---

## 🎯 核心对比

### AWS Location Service (现有方案)

**提供的数据：**
```json
{
  "PlaceId": "abc123",
  "Position": [139.7017, 35.6895],  // ⚠️ 只有中心点
  "Address": {
    "SubDistrict": "Shibuya"
  }
}
```

**问题：**
- ❌ 只有一个中心点坐标 `[lon, lat]`
- ❌ 没有边界 Polygon 数据
- ❌ 无法绘制真实的区域轮廓
- ❌ 网格采样得到的点分布看起来"规则"

---

### OpenStreetMap (OSM) - 本 POC 方案

**提供的数据：**
```json
{
  "type": "Feature",
  "properties": {
    "name": "Shibuya",
    "name_local": "渋谷区",
    "osm_id": "1803019"
  },
  "geometry": {
    "type": "Polygon",  // ✅ 真实的不规则边界
    "coordinates": [[
      [139.6634, 35.6462],
      [139.6845, 35.6462],
      [139.7056, 35.6585],
      [139.7123, 35.6708],
      // ... 更多坐标点构成闭合多边形
      [139.6634, 35.6462]
    ]]
  }
}
```

**优势：**
- ✅ 完整的 **Polygon/MultiPolygon** 边界数据
- ✅ **不规则形状**，贴合真实行政区划
- ✅ 可以直接在地图上绘制填充区域
- ✅ **免费、开源**
- ✅ 全球覆盖

---

## 🛠️ 技术实现

### 1. 数据获取 - Overpass API

```python
# 查询东京的区（admin_level=9）边界
query = """
[out:json][timeout:60];
area[name="Tokyo"]->.city;
(
  relation["boundary"="administrative"]["admin_level"="9"](area.city);
);
out geom 20;
"""

response = requests.post(
    'https://overpass-api.de/api/interpreter',
    data={'data': query}
)
data = response.json()
```

**参数说明：**
- `admin_level=9`: 东京的区级别（如涩谷区、新宿区）
- `admin_level=10`: 更细粒度的町/neighbourhood
- `out geom`: 返回完整的几何坐标

---

### 2. 数据转换 - OSM → GeoJSON

```python
def osm_to_geojson(osm_data):
    features = []
    
    for element in osm_data['elements']:
        # 提取 Polygon 坐标
        coordinates = []
        for member in element['members']:
            if member['role'] == 'outer':
                way_coords = [
                    [node['lon'], node['lat']]
                    for node in member['geometry']
                ]
                coordinates.append(way_coords)
        
        # 构建 GeoJSON Feature
        feature = {
            "type": "Feature",
            "properties": {
                "name": element['tags']['name'],
                "osm_id": element['id']
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": coordinates
            }
        }
        features.append(feature)
    
    return {"type": "FeatureCollection", "features": features}
```

---

### 3. 可视化 - Leaflet.js

```javascript
// 在地图上绘制 Polygon 边界
L.geoJSON(geojsonData, {
  style: function(feature) {
    return {
      color: '#58a6ff',
      weight: 2,
      fillColor: '#58a6ff',
      fillOpacity: 0.2  // 半透明填充
    };
  }
}).addTo(map);
```

---

## 📊 数据对比示例

### 东京 - 渋谷区 (Shibuya)

#### AWS Location Service
```json
{
  "SubDistrict": "Shibuya",
  "Position": [139.7017, 35.6895]  // ⚠️ 只有中心点
}
```

**在地图上显示为：** 一个小圆点 🔵

---

#### OpenStreetMap (本POC)
```json
{
  "name": "Shibuya",
  "geometry": {
    "type": "Polygon",
    "coordinates": [[
      [139.6634, 35.6462],  // 西南角
      [139.6845, 35.6462],
      [139.7056, 35.6585],
      [139.7123, 35.6708],  // 东北角
      // ... 15个坐标点
      [139.6634, 35.6462]   // 闭合回起点
    ]]
  }
}
```

**在地图上显示为：** 一个完整的不规则多边形区域 🟦

---

## 🎨 可视化效果对比

### 原方案（网格点）
```
    ·  ·  ·  ·  ·
    ·  ·  ·  ·  ·
    ·  ·  ·  ·  ·
    ·  ·  ·  ·  ·
```
- 规则的网格状分布
- 只有中心点
- 无法看出真实边界

---

### OSM方案（Polygon）
```
    ╔═══════╗
    ║       ║
    ║   🏙️  ║ Shibuya
    ║       ║
    ╚═══════╝
```
- 不规则的真实边界
- 填充的区域形状
- 清晰的边界轮廓

---

## 🚀 部署建议

### 方案 A：混合方案（推荐）

```python
# 1. 用 AWS Location Service 验证 neighbourhood 是否存在
aws_response = location.search_text(QueryText="Shibuya, Tokyo")
if aws_response['Results']:
    entity_id = aws_response['Results'][0]['PlaceId']
    
    # 2. 用 OSM 获取边界 Polygon
    osm_polygon = fetch_osm_boundary("Shibuya", admin_level=9)
    
    # 3. 合并数据
    final_data = {
        'name': 'Shibuya',
        'aws_entity_id': entity_id,      # AWS 验证
        'geometry': osm_polygon,          # OSM 边界
        'center': [139.7017, 35.6895]     # 计算的中心点
    }
```

**优势：**
- ✅ AWS 保证数据真实性
- ✅ OSM 提供边界几何
- ✅ 两者互补

---

### 方案 B：纯 OSM 方案

```python
# 直接从 OSM 获取所有数据
osm_data = query_overpass_api(
    city="Tokyo",
    admin_level=9,
    limit=50
)
geojson = osm_to_geojson(osm_data)
```

**优势：**
- ✅ 完全免费
- ✅ 数据完整
- ✅ 无 API 调用限制

**注意：**
- ⚠️ 数据质量取决于 OSM 社区
- ⚠️ 需要自己验证数据准确性

---

## 📦 POC 文件说明

### 1. `osm_neighbourhood_poc.py`
- 完整的 Python 脚本
- 查询 OSM → 转换 GeoJSON → 生成 HTML
- 支持命令行参数：`python osm_neighbourhood_poc.py Tokyo 9 20`

### 2. `osm_tokyo_sample.geojson`
- 示例 GeoJSON 数据
- 包含 5 个东京区的 Polygon 边界
- 标准的 GeoJSON FeatureCollection 格式

### 3. `osm_tokyo_neighbourhoods_poc.html`
- 交互式可视化页面
- Leaflet.js 地图
- 实时显示 Polygon 边界

---

## 🌍 支持的城市/国家

OSM 数据全球覆盖，但质量因地区而异：

| 地区 | 数据质量 | admin_level 参考 |
|------|---------|-----------------|
| 日本 | ⭐⭐⭐⭐⭐ | 9=区, 10=町 |
| 欧美 | ⭐⭐⭐⭐⭐ | 8=城市, 9=区 |
| 中国 | ⭐⭐⭐ | 8=市辖区, 9=街道 |
| 东南亚 | ⭐⭐⭐⭐ | 因国家而异 |

---

## 💰 成本对比

| 方案 | API 调用成本 | 数据存储 | 更新频率 |
|------|-------------|---------|---------|
| AWS Location | $0.04 / 1000次 | S3成本 | 按需 |
| OSM (本POC) | **$0 免费** | 本地/S3 | 每日可更新 |

---

## 🎯 总结

### 为什么选择 OSM？

1. ✅ **真实的 Polygon 边界**：不是网格点，是真实的不规则行政区划
2. ✅ **免费开源**：无 API 调用费用
3. ✅ **全球覆盖**：支持 200+ 国家和地区
4. ✅ **标准格式**：GeoJSON，兼容所有主流地图库
5. ✅ **灵活定制**：可以查询任意 admin_level

### 局限性

- ⚠️ 数据质量取决于 OSM 社区贡献
- ⚠️ Overpass API 有查询超时限制（可自建 OSM 数据库解决）
- ⚠️ 需要自行处理数据验证

---

## 📚 相关资源

- **Overpass API 文档**: https://wiki.openstreetmap.org/wiki/Overpass_API
- **Admin Level 参考**: https://wiki.openstreetmap.org/wiki/Tag:boundary=administrative
- **GeoJSON 规范**: https://geojson.org/
- **Leaflet.js 文档**: https://leafletjs.com/

---

**作者**: Ning Xia  
**日期**: 2026-03-20  
**目的**: 演示 OSM 获取真实 neighbourhood 边界数据的可行性
