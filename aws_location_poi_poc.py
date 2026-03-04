#!/usr/bin/env python3
"""
AWS Location Service POI POC
抓取三个不同大洲主流旅游城市的POI信息
"""

import boto3
import json
from datetime import datetime

# 初始化 AWS Location Service 客户端
location_client = boto3.client('location')

# 定义三个不同大洲的主流旅游城市
CITIES = {
    'Tokyo': {
        'continent': 'Asia',
        'coordinates': [139.6917, 35.6895],  # [longitude, latitude]
        'description': '日本东京 - 现代与传统交融的国际大都市'
    },
    'Paris': {
        'continent': 'Europe',
        'coordinates': [2.3522, 48.8566],
        'description': '法国巴黎 - 浪漫之都，艺术与文化的中心'
    },
    'New York': {
        'continent': 'North America',
        'coordinates': [-74.0060, 40.7128],
        'description': '美国纽约 - 世界金融与文化中心'
    }
}

# POI 类别（可以根据需要调整）
POI_CATEGORIES = [
    'Restaurant',
    'Hotel',
    'Museum',
    'Park',
    'Shopping',
    'Transportation'
]


def search_pois_near_location(city_name, coordinates, max_results=10):
    """
    使用 AWS Location Service 搜索指定位置附近的 POI
    
    Args:
        city_name: 城市名称
        coordinates: [longitude, latitude]
        max_results: 最大结果数量
    
    Returns:
        POI 列表
    """
    try:
        print(f"\n🔍 正在搜索 {city_name} 的 POI...")
        
        # 使用 SearchPlaceIndexForPosition 搜索附近的地点
        response = location_client.search_place_index_for_position(
            IndexName='poi-poc-index',  # AWS 默认的 Place Index
            Position=coordinates,
            MaxResults=max_results
        )
        
        pois = []
        for result in response.get('Results', []):
            place = result.get('Place', {})
            
            poi_info = {
                'City': city_name,
                'Continent': CITIES[city_name]['continent'],
                'Name': place.get('Label', 'N/A'),
                'Coordinates': {
                    'Longitude': place.get('Geometry', {}).get('Point', [None, None])[0],
                    'Latitude': place.get('Geometry', {}).get('Point', [None, None])[1]
                },
                'Address': place.get('AddressNumber', '') + ' ' + place.get('Street', ''),
                'Neighborhood': place.get('Neighborhood', 'N/A'),
                'Municipality': place.get('Municipality', 'N/A'),
                'Country': place.get('Country', 'N/A'),
                'Entity_Type': place.get('Categories', ['General'])[0] if place.get('Categories') else 'General',
                'Description': f"{place.get('Label', 'N/A')} in {city_name}",
                'Relevance': result.get('Relevance', 0)
            }
            
            pois.append(poi_info)
        
        print(f"✅ 在 {city_name} 找到 {len(pois)} 个 POI")
        return pois
        
    except Exception as e:
        print(f"❌ 搜索 {city_name} 时出错: {str(e)}")
        return []


def search_pois_by_text(city_name, coordinates, search_text, max_results=10):
    """
    使用文本搜索特定类型的 POI
    
    Args:
        city_name: 城市名称
        coordinates: [longitude, latitude]
        search_text: 搜索关键词
        max_results: 最大结果数量
    
    Returns:
        POI 列表
    """
    try:
        print(f"\n🔍 在 {city_name} 搜索 '{search_text}'...")
        
        # 使用 SearchPlaceIndexForText 进行文本搜索
        response = location_client.search_place_index_for_text(
            IndexName='poi-poc-index',
            Text=f"{search_text} in {city_name}",
            BiasPosition=coordinates,
            MaxResults=max_results
        )
        
        pois = []
        for result in response.get('Results', []):
            place = result.get('Place', {})
            
            poi_info = {
                'City': city_name,
                'Continent': CITIES[city_name]['continent'],
                'Name': place.get('Label', 'N/A'),
                'Coordinates': {
                    'Longitude': place.get('Geometry', {}).get('Point', [None, None])[0],
                    'Latitude': place.get('Geometry', {}).get('Point', [None, None])[1]
                },
                'Address': place.get('AddressNumber', '') + ' ' + place.get('Street', ''),
                'Neighborhood': place.get('Neighborhood', 'N/A'),
                'Municipality': place.get('Municipality', 'N/A'),
                'Country': place.get('Country', 'N/A'),
                'Entity_Type': place.get('Categories', [search_text])[0] if place.get('Categories') else search_text,
                'Description': f"{place.get('Label', 'N/A')} - {search_text} in {city_name}",
                'Relevance': result.get('Relevance', 0)
            }
            
            pois.append(poi_info)
        
        print(f"✅ 找到 {len(pois)} 个 {search_text}")
        return pois
        
    except Exception as e:
        print(f"❌ 搜索时出错: {str(e)}")
        return []


def main():
    """主函数"""
    print("=" * 80)
    print("🌍 AWS Location Service POI POC")
    print("抓取三个不同大洲主流旅游城市的 POI 信息")
    print("=" * 80)
    
    all_pois = []
    
    # 遍历每个城市
    for city_name, city_info in CITIES.items():
        print(f"\n{'=' * 80}")
        print(f"📍 城市: {city_name} ({city_info['continent']})")
        print(f"   坐标: {city_info['coordinates']}")
        print(f"   描述: {city_info['description']}")
        print('=' * 80)
        
        # 方法1：搜索附近的地点
        nearby_pois = search_pois_near_location(
            city_name, 
            city_info['coordinates'], 
            max_results=5
        )
        all_pois.extend(nearby_pois)
        
        # 方法2：按类别搜索特定 POI
        for category in ['tourist attraction', 'restaurant', 'hotel']:
            category_pois = search_pois_by_text(
                city_name,
                city_info['coordinates'],
                category,
                max_results=3
            )
            all_pois.extend(category_pois)
    
    # 保存结果到 JSON 文件
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f'aws_location_pois_{timestamp}.json'
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_pois, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'=' * 80}")
    print(f"✅ 完成！共抓取 {len(all_pois)} 个 POI")
    print(f"📄 结果已保存到: {output_file}")
    print('=' * 80)
    
    # 打印一些示例数据
    print("\n📊 示例数据（前3个）:")
    for i, poi in enumerate(all_pois[:3], 1):
        print(f"\n{i}. {poi['Name']}")
        print(f"   城市: {poi['City']} ({poi['Continent']})")
        print(f"   坐标: {poi['Coordinates']}")
        print(f"   类型: {poi['Entity_Type']}")
        print(f"   描述: {poi['Description']}")


if __name__ == '__main__':
    main()
