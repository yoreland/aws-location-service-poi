# OSM 边界补充工具 vs 混合方案演示

## 问题：AWS 验证步骤的意义

你提出的问题**非常正确**：

```python
def verify_with_aws_location(neighbourhood, city):
    # 模拟的 AWS 调用
    return {
        "PlaceId": "aws_shibuya_xxx",  # ← 假数据
        "Match": True,                  # ← 总是 True
        "MatchScore": 95.5,            # ← 固定值
    }
```

**问题：**
- ❌ 没有真正调用 AWS API
- ❌ 返回硬编码的假数据
- ❌ 对最终结果没有实际贡献
- ❌ 只是为了演示数据流程

---

## 解决方案

### 方案 A：简化工具（推荐）⭐

**文件：** `enrich_with_osm_boundaries.py`

**用途：** 从**已验证的数据**直接补充 OSM 边界

**适用场景：**
- ✅ 已有 LLM 生成的 neighbourhood 列表
- ✅ AWS 验证已完成（在 `verify_neighbourhoods.py` 中）
- ✅ 只需要补充 OSM Polygon 边界

**数据流程：**
```
已验证的数据 (JSON)
        ↓
    加载数据
        ↓
OSM 获取边界 (Nominatim API)
        ↓
    合并保存
        ↓
完整数据 (GeoJSON)
```

**使用方法：**
```bash
python enrich_with_osm_boundaries.py \
    data/gpt-5.2-ws_tokyo_B.json \
    data/tokyo_with_osm_boundaries.geojson
```

**输出数据格式：**
```json
{
  "type": "Feature",
  "properties": {
    "name": "Shibuya",
    "name_local": "渋谷",
    "aws_entity_id": "real_aws_id_from_verify_neighbourhoods",
    "aws_match_score": 95.5,
    "osm_id": 1759477,
    "boundary_point_count": 1000
  },
  "geometry": {
    "type": "Polygon",
    "coordinates": [[...]]  // 真实的 OSM 边界
  }
}
```

---

### 方案 B：完整混合方案（演示用）

**文件：** `hybrid_pipeline_demo.py`

**用途：** 演示完整的数据流程（LLM → AWS → OSM）

**适用场景：**
- ✅ 需要展示完整的混合方案概念
- ✅ 用于技术演示和文档说明
- ✅ 实际使用时需要替换为真实 AWS API 调用

**数据流程：**
```
LLM 生成列表
    ↓
AWS 验证 (需要真实 boto3 调用)
    ↓
OSM 获取边界
    ↓
合并存储
```

**如何改进：**

将模拟的 AWS 调用替换为真实调用：

```python
import boto3

def verify_with_aws_location(neighbourhood, city):
    """真实的 AWS Location Service 调用"""
    
    client = boto3.client('location', region_name='us-west-2')
    
    response = client.search_place_index_for_text(
        IndexName='YourPlaceIndexName',
        Text=f"{neighbourhood['name']}, {city}, Japan",
        MaxResults=1
    )
    
    if response['Results']:
        place = response['Results'][0]
        return {
            "PlaceId": place['PlaceId'],
            "Match": True,
            "MatchScore": place.get('Relevance', 0),
            "Position": place['Place']['Geometry']['Point']
        }
    else:
        return {"Match": False}
```

---

## 对比总结

| 特性 | 简化工具 (A) | 混合方案演示 (B) |
|------|-------------|-----------------|
| **文件名** | `enrich_with_osm_boundaries.py` | `hybrid_pipeline_demo.py` |
| **AWS 调用** | ❌ 不需要（使用已有数据） | ⚠️ 需要（当前是模拟） |
| **输入数据** | 已验证的 JSON | LLM 生成的列表 |
| **实际价值** | ⭐⭐⭐⭐⭐ 立即可用 | ⭐⭐⭐ 需要改进 |
| **适用场景** | **生产环境** | 技术演示 |

---

## 推荐做法

### 对于你的项目 ✅

**使用简化工具：** `enrich_with_osm_boundaries.py`

**原因：**
1. 你已经有 LLM 生成的数据
2. AWS 验证已完成（`verify_neighbourhoods.py`）
3. 只需要补充 OSM 边界
4. 避免重复的 AWS API 调用
5. 更简单、更高效

**工作流程：**
```bash
# 1. LLM 生成 (已完成)
# 已有文件: data/gpt-5.2-ws_tokyo_B.json

# 2. AWS 验证 (已完成)
python verify_neighbourhoods.py

# 3. 补充 OSM 边界 (新工具)
python enrich_with_osm_boundaries.py \
    data/verified_tokyo.json \
    data/tokyo_complete.geojson
```

---

## 结论

你的观察**完全正确**：

- ❌ `hybrid_pipeline_demo.py` 中的 AWS 验证步骤**确实意义不大**（因为是模拟数据）
- ✅ `enrich_with_osm_boundaries.py` 是**实际可用的工具**
- ✅ 直接从已验证数据补充 OSM 边界，避免重复工作
- ✅ 更符合实际项目需求

---

**建议：**
- 在生产环境使用 `enrich_with_osm_boundaries.py`
- `hybrid_pipeline_demo.py` 仅作为概念演示
- 如需完整的混合方案，替换 AWS 模拟调用为真实 boto3 代码
