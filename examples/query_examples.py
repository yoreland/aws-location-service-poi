#!/usr/bin/env python3
"""
AWS Location Service 查询示例
演示各种查询场景的最佳实践
"""

import boto3
import json
from typing import List, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor


# 初始化客户端
location_client = boto3.client('location')
INDEX_NAME = 'poi-poc-index'


def example_1_nearby_search():
    """示例1: 搜索附近的地点"""
    print("=" * 60)
    print("示例 1: 搜索东京塔附近的地点")
    print("=" * 60)
    
    # 东京塔坐标
    tokyo_tower = [139.7454, 35.6586]
    
    response = location_client.search_place_index_for_position(
        IndexName=INDEX_NAME,
        Position=tokyo_tower,
        MaxResults=5
    )
    
    print(f"\n找到 {len(response['Results'])} 个附近地点:\n")
    for i, result in enumerate(response['Results'], 1):
        place = result['Place']
        print(f"{i}. {place['Label']}")
        print(f"   距离: {result.get('Distance', 'N/A')} 米")
        print(f"   相关性: {result['Relevance']:.2f}\n")


def example_2_text_search():
    """示例2: 文本搜索特定类型POI"""
    print("=" * 60)
    print("示例 2: 搜索东京的拉面店")
    print("=" * 60)
    
    response = location_client.search_place_index_for_text(
        IndexName=INDEX_NAME,
        Text='ramen restaurant in Tokyo',
        BiasPosition=[139.6917, 35.6895],
        MaxResults=5
    )
    
    print(f"\n找到 {len(response['Results'])} 家拉面店:\n")
    for i, result in enumerate(response['Results'], 1):
        place = result['Place']
        coords = place['Geometry']['Point']
        print(f"{i}. {place['Label']}")
        print(f"   坐标: ({coords[0]:.6f}, {coords[1]:.6f})")
        print(f"   相关性: {result['Relevance']:.2f}\n")


def example_3_bbox_filter():
    """示例3: 使用边界框过滤"""
    print("=" * 60)
    print("示例 3: 搜索新宿区内的酒店（使用边界框）")
    print("=" * 60)
    
    # 新宿区大致边界
    shinjuku_bbox = [
        139.67,  # 西
        35.67,   # 南
        139.72,  # 东
        35.72    # 北
    ]
    
    response = location_client.search_place_index_for_text(
        IndexName=INDEX_NAME,
        Text='hotel',
        FilterBBox=shinjuku_bbox,
        MaxResults=5
    )
    
    print(f"\n找到 {len(response['Results'])} 家酒店:\n")
    for i, result in enumerate(response['Results'], 1):
        place = result['Place']
        print(f"{i}. {place['Label']}")
        print(f"   区域: {place.get('Neighborhood', 'N/A')}")
        print(f"   相关性: {result['Relevance']:.2f}\n")


def example_4_country_filter():
    """示例4: 使用国家代码过滤"""
    print("=" * 60)
    print("示例 4: 只搜索日本境内的 Tokyo 相关地点")
    print("=" * 60)
    
    response = location_client.search_place_index_for_text(
        IndexName=INDEX_NAME,
        Text='Tokyo',
        FilterCountries=['JPN'],  # ISO 3166-1 alpha-3
        MaxResults=5
    )
    
    print(f"\n找到 {len(response['Results'])} 个结果:\n")
    for i, result in enumerate(response['Results'], 1):
        place = result['Place']
        print(f"{i}. {place['Label']}")
        print(f"   国家: {place['Country']}")
        print(f"   相关性: {result['Relevance']:.2f}\n")


def example_5_batch_query():
    """示例5: 批量并发查询多个城市"""
    print("=" * 60)
    print("示例 5: 并发查询三个城市的景点")
    print("=" * 60)
    
    cities = {
        'Tokyo': [139.6917, 35.6895],
        'Osaka': [135.5022, 34.6937],
        'Kyoto': [135.7681, 35.0116]
    }
    
    def query_city(city_name: str, coords: List[float]) -> Dict:
        """查询单个城市"""
        response = location_client.search_place_index_for_text(
            IndexName=INDEX_NAME,
            Text=f'tourist attraction in {city_name}',
            BiasPosition=coords,
            MaxResults=3
        )
        return {
            'city': city_name,
            'count': len(response['Results']),
            'attractions': [r['Place']['Label'] for r in response['Results']]
        }
    
    # 使用线程池并发查询
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(query_city, name, coords)
            for name, coords in cities.items()
        ]
        results = [f.result() for f in futures]
    
    print("\n查询结果:\n")
    for result in results:
        print(f"📍 {result['city']}: 找到 {result['count']} 个景点")
        for attraction in result['attractions']:
            print(f"   - {attraction}")
        print()


def example_6_filter_by_relevance():
    """示例6: 按相关性过滤高质量结果"""
    print("=" * 60)
    print("示例 6: 查找高相关性（>0.95）的东京酒店")
    print("=" * 60)
    
    response = location_client.search_place_index_for_text(
        IndexName=INDEX_NAME,
        Text='hotel in Tokyo',
        BiasPosition=[139.6917, 35.6895],
        MaxResults=20
    )
    
    # 过滤高相关性结果
    high_quality = [
        result for result in response['Results']
        if result['Relevance'] > 0.95
    ]
    
    print(f"\n从 {len(response['Results'])} 个结果中筛选出 {len(high_quality)} 个高质量酒店:\n")
    for i, result in enumerate(high_quality, 1):
        place = result['Place']
        print(f"{i}. {place['Label']}")
        print(f"   相关性: {result['Relevance']:.3f}")
        print(f"   邮编: {place.get('PostalCode', 'N/A')}\n")


def example_7_find_restaurants_within_radius():
    """示例7: 查找指定半径内的餐厅"""
    print("=" * 60)
    print("示例 7: 查找东京站 1km 内的餐厅")
    print("=" * 60)
    
    tokyo_station = [139.7673, 35.6812]
    radius_km = 1.0
    
    # 计算边界框（简化方法）
    offset = radius_km / 111.0  # 1度约111km
    bbox = [
        tokyo_station[0] - offset,
        tokyo_station[1] - offset,
        tokyo_station[0] + offset,
        tokyo_station[1] + offset
    ]
    
    response = location_client.search_place_index_for_text(
        IndexName=INDEX_NAME,
        Text='restaurant',
        BiasPosition=tokyo_station,
        FilterBBox=bbox,
        MaxResults=10
    )
    
    # 计算实际距离并排序
    import math
    
    def haversine_distance(coord1: Tuple[float, float], 
                          coord2: Tuple[float, float]) -> float:
        """计算两点间的距离（千米）"""
        lon1, lat1 = coord1
        lon2, lat2 = coord2
        
        R = 6371  # 地球半径（千米）
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = (math.sin(dlat/2)**2 + 
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
             math.sin(dlon/2)**2)
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c
    
    restaurants = []
    for result in response['Results']:
        place = result['Place']
        coords = place['Geometry']['Point']
        distance = haversine_distance(tokyo_station, coords)
        
        if distance <= radius_km:
            restaurants.append({
                'name': place['Label'],
                'distance': distance,
                'relevance': result['Relevance']
            })
    
    restaurants.sort(key=lambda x: x['distance'])
    
    print(f"\n找到 {len(restaurants)} 家 1km 内的餐厅:\n")
    for i, r in enumerate(restaurants, 1):
        print(f"{i}. {r['name']}")
        print(f"   距离: {r['distance']:.2f} km")
        print(f"   相关性: {r['relevance']:.2f}\n")


def example_8_save_results_to_json():
    """示例8: 保存查询结果到 JSON"""
    print("=" * 60)
    print("示例 8: 查询并保存结果到 JSON 文件")
    print("=" * 60)
    
    response = location_client.search_place_index_for_text(
        IndexName=INDEX_NAME,
        Text='museum in Tokyo',
        BiasPosition=[139.6917, 35.6895],
        MaxResults=5
    )
    
    # 格式化结果
    museums = []
    for result in response['Results']:
        place = result['Place']
        museums.append({
            'name': place['Label'],
            'coordinates': {
                'longitude': place['Geometry']['Point'][0],
                'latitude': place['Geometry']['Point'][1]
            },
            'address': place.get('AddressNumber', '') + ' ' + place.get('Street', ''),
            'municipality': place.get('Municipality', 'N/A'),
            'postal_code': place.get('PostalCode', 'N/A'),
            'relevance': result['Relevance']
        })
    
    # 保存到文件
    output_file = 'tokyo_museums.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(museums, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 已保存 {len(museums)} 个博物馆信息到 {output_file}\n")
    print("示例内容:")
    print(json.dumps(museums[0], ensure_ascii=False, indent=2))


def main():
    """运行所有示例"""
    examples = [
        example_1_nearby_search,
        example_2_text_search,
        example_3_bbox_filter,
        example_4_country_filter,
        example_5_batch_query,
        example_6_filter_by_relevance,
        example_7_find_restaurants_within_radius,
        example_8_save_results_to_json
    ]
    
    print("\n" + "=" * 60)
    print("AWS Location Service 查询示例集")
    print("=" * 60 + "\n")
    
    for i, example_func in enumerate(examples, 1):
        try:
            example_func()
            print()
        except Exception as e:
            print(f"\n❌ 示例 {i} 执行失败: {str(e)}\n")
    
    print("=" * 60)
    print("所有示例执行完成！")
    print("=" * 60)


if __name__ == '__main__':
    main()
