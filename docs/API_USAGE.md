# AWS Location Service API 使用指南

## 📖 概述

AWS Location Service 提供地理位置服务，包括：
- **Place Index**: POI 搜索和地理编码
- **Maps**: 地图瓦片
- **Routes**: 路线规划
- **Trackers**: 设备追踪
- **Geofences**: 地理围栏

本项目主要使用 **Place Index** 功能。

---

## 🔑 认证配置

### 方法1: AWS CLI 配置

```bash
aws configure
```

输入：
- AWS Access Key ID
- AWS Secret Access Key
- Default region (e.g., us-east-1)
- Default output format (json)

### 方法2: 环境变量

```bash
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
export AWS_DEFAULT_REGION="us-east-1"
```

### 方法3: Python 代码中配置

```python
import boto3

location_client = boto3.client(
    'location',
    aws_access_key_id='YOUR_KEY',
    aws_secret_access_key='YOUR_SECRET',
    region_name='us-east-1'
)
```

---

## 🗺️ 创建 Place Index

### 使用 AWS CLI

```bash
# 使用 Esri 数据源
aws location create-place-index \
    --index-name poi-poc-index \
    --data-source Esri \
    --pricing-plan RequestBasedUsage \
    --description "POI POC Place Index"

# 使用 HERE 数据源
aws location create-place-index \
    --index-name poi-poc-here \
    --data-source Here \
    --pricing-plan RequestBasedUsage
```

### 使用 Python boto3

```python
import boto3

location = boto3.client('location')

response = location.create_place_index(
    IndexName='poi-poc-index',
    DataSource='Esri',  # 或 'Here'
    PricingPlan='RequestBasedUsage',
    Description='POI POC Place Index'
)

print(f"Created Place Index: {response['IndexArn']}")
```

### 数据源对比

| 特性 | Esri | HERE |
|------|------|------|
| 全球覆盖 | ✅ | ✅ |
| POI 数量 | 约 1 亿+ | 约 1.5 亿+ |
| 更新频率 | 季度 | 月度 |
| 中文支持 | 一般 | 较好 |
| 价格 | 相同 | 相同 |

---

## 🔍 搜索 API

### 1. SearchPlaceIndexForPosition (坐标搜索)

根据经纬度查找附近的地点。

#### 基础用法

```python
import boto3

location = boto3.client('location')

response = location.search_place_index_for_position(
    IndexName='poi-poc-index',
    Position=[139.6917, 35.6895],  # [经度, 纬度]
    MaxResults=10
)

for result in response['Results']:
    place = result['Place']
    print(f"{place['Label']} - {place.get('Categories', [])}")
```

#### 高级参数

```python
response = location.search_place_index_for_position(
    IndexName='poi-poc-index',
    Position=[139.6917, 35.6895],
    MaxResults=50,  # 最大 50
    Language='ja',  # 日文结果
)
```

#### 支持的语言代码
- `en`: 英语
- `ja`: 日语
- `zh`: 中文
- `fr`: 法语
- `de`: 德语
- `es`: 西班牙语

---

### 2. SearchPlaceIndexForText (文本搜索)

根据文本查询搜索地点。

#### 基础用法

```python
response = location.search_place_index_for_text(
    IndexName='poi-poc-index',
    Text='Tokyo Tower',
    MaxResults=10
)

for result in response['Results']:
    place = result['Place']
    coords = place['Geometry']['Point']
    print(f"{place['Label']}: {coords}")
```

#### 使用位置偏好

```python
response = location.search_place_index_for_text(
    IndexName='poi-poc-index',
    Text='restaurant',
    BiasPosition=[139.6917, 35.6895],  # 优先返回附近结果
    MaxResults=20
)
```

#### 使用边界框过滤

```python
response = location.search_place_index_for_text(
    IndexName='poi-poc-index',
    Text='hotel in Tokyo',
    FilterBBox=[138.5, 35.0, 140.5, 36.0],  # [西,南,东,北]
    MaxResults=20
)
```

#### 使用国家过滤

```python
response = location.search_place_index_for_text(
    IndexName='poi-poc-index',
    Text='restaurant',
    FilterCountries=['JPN'],  # ISO 3166-1 alpha-3 代码
    BiasPosition=[139.6917, 35.6895],
    MaxResults=20
)
```

---

## 📊 响应结构

### Place 对象字段

```python
{
    'Label': 'Hyatt Regency Tokyo, Shinjuku, Tokyo, JPN',
    'Geometry': {
        'Point': [139.690998544, 35.690886306]  # [经度, 纬度]
    },
    'AddressNumber': '2-7-2',
    'Street': 'Nishi-Shinjuku',
    'Municipality': 'Shinjuku',
    'Neighborhood': 'Nishi-Shinjuku',
    'PostalCode': '160-0023',
    'Country': 'JPN',
    'Region': 'Tokyo',
    'SubRegion': 'Tokyo',
    'Categories': [
        'PointOfInterestType',
        'Hotel'
    ]
}
```

### Result 对象

```python
{
    'Place': { ... },  # Place 对象
    'Distance': 125.5,  # 与查询点的距离（米）
    'Relevance': 0.95,  # 相关性评分 (0-1)
    'PlaceId': 'abc123...'  # Place ID
}
```

---

## 🎯 实用查询示例

### 示例 1: 查找特定区域的餐厅

```python
def find_restaurants_in_area(center_coords, radius_km=1.0):
    """
    查找指定区域内的餐厅
    
    Args:
        center_coords: [经度, 纬度]
        radius_km: 搜索半径（公里）
    """
    location = boto3.client('location')
    
    # 计算边界框（简化方法，1度约111km）
    offset = radius_km / 111.0
    bbox = [
        center_coords[0] - offset,  # 西
        center_coords[1] - offset,  # 南
        center_coords[0] + offset,  # 东
        center_coords[1] + offset   # 北
    ]
    
    response = location.search_place_index_for_text(
        IndexName='poi-poc-index',
        Text='restaurant',
        BiasPosition=center_coords,
        FilterBBox=bbox,
        MaxResults=50
    )
    
    restaurants = []
    for result in response['Results']:
        place = result['Place']
        restaurants.append({
            'name': place['Label'],
            'coordinates': place['Geometry']['Point'],
            'distance': result.get('Distance', 0),
            'relevance': result['Relevance']
        })
    
    # 按距离排序
    restaurants.sort(key=lambda x: x['distance'])
    return restaurants
```

### 示例 2: 批量查询多个城市

```python
import boto3
from concurrent.futures import ThreadPoolExecutor

def query_city(city_name, coords):
    """单个城市查询"""
    location = boto3.client('location')
    
    response = location.search_place_index_for_text(
        IndexName='poi-poc-index',
        Text=f'tourist attraction in {city_name}',
        BiasPosition=coords,
        MaxResults=20
    )
    
    return {
        'city': city_name,
        'pois': [r['Place']['Label'] for r in response['Results']]
    }

def batch_query_cities(cities_dict):
    """并发查询多个城市"""
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [
            executor.submit(query_city, name, info['coordinates'])
            for name, info in cities_dict.items()
        ]
        results = [f.result() for f in futures]
    
    return results

# 使用示例
cities = {
    'Tokyo': {'coordinates': [139.6917, 35.6895]},
    'Paris': {'coordinates': [2.3522, 48.8566]},
    'New York': {'coordinates': [-74.0060, 40.7128]}
}

results = batch_query_cities(cities)
```

### 示例 3: 过滤和排序结果

```python
def find_high_quality_hotels(city_name, coords, min_relevance=0.9):
    """
    查找高质量酒店（高相关性评分）
    """
    location = boto3.client('location')
    
    response = location.search_place_index_for_text(
        IndexName='poi-poc-index',
        Text=f'hotel in {city_name}',
        BiasPosition=coords,
        MaxResults=50
    )
    
    # 过滤高相关性结果
    high_quality = [
        result for result in response['Results']
        if result['Relevance'] >= min_relevance
    ]
    
    # 按相关性排序
    high_quality.sort(key=lambda x: x['Relevance'], reverse=True)
    
    return [
        {
            'name': r['Place']['Label'],
            'relevance': r['Relevance'],
            'coordinates': r['Place']['Geometry']['Point']
        }
        for r in high_quality
    ]
```

---

## 💰 成本优化

### 免费套餐
- **前 12 个月**: 每月 50,000 次请求免费
- **持续免费**: 无（12个月后开始计费）

### 定价（按请求计费）
- **SearchPlaceIndexForPosition**: $0.50 / 1,000 次
- **SearchPlaceIndexForText**: $0.50 / 1,000 次
- **其他操作**: 参见 [AWS 定价页面](https://aws.amazon.com/location/pricing/)

### 优化建议

1. **缓存结果**
```python
import json
from functools import lru_cache

@lru_cache(maxsize=1000)
def cached_search(text, coords_tuple):
    """缓存搜索结果"""
    location = boto3.client('location')
    response = location.search_place_index_for_text(
        IndexName='poi-poc-index',
        Text=text,
        BiasPosition=list(coords_tuple),
        MaxResults=10
    )
    return response

# 使用
result = cached_search('restaurant', (139.69, 35.68))
```

2. **批量处理**
```python
# 不好的做法：单个查询
for city in cities:
    result = search_poi(city)  # 100 次请求

# 好的做法：使用更大的 MaxResults
result = search_poi(region, MaxResults=50)  # 1 次请求
```

3. **使用 FilterBBox 减少不相关结果**

---

## 🛠️ 错误处理

### 常见错误

#### 1. ResourceNotFoundException
```python
try:
    response = location.search_place_index_for_text(
        IndexName='non-existent-index',
        Text='restaurant'
    )
except location.exceptions.ResourceNotFoundException:
    print("Place Index 不存在，请先创建")
```

#### 2. ValidationException
```python
try:
    response = location.search_place_index_for_position(
        IndexName='poi-poc-index',
        Position=[200, 100],  # 无效坐标
        MaxResults=10
    )
except location.exceptions.ValidationException as e:
    print(f"参数验证失败: {e}")
```

#### 3. AccessDeniedException
```python
try:
    response = location.search_place_index_for_text(...)
except location.exceptions.AccessDeniedException:
    print("权限不足，请检查 IAM 策略")
```

### IAM 权限示例

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "geo:SearchPlaceIndexForPosition",
                "geo:SearchPlaceIndexForText",
                "geo:SearchPlaceIndexForSuggestions"
            ],
            "Resource": "arn:aws:geo:us-east-1:123456789012:place-index/poi-poc-index"
        }
    ]
}
```

---

## 📚 参考资源

- [AWS Location Service 官方文档](https://docs.aws.amazon.com/location/)
- [boto3 API 参考](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/location.html)
- [AWS CLI 命令参考](https://awscli.amazonaws.com/v2/documentation/api/latest/reference/location/index.html)
- [定价详情](https://aws.amazon.com/location/pricing/)

---

**最后更新**: 2026-03-04  
**维护者**: yoreland
