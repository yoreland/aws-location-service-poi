#!/usr/bin/env python3
"""
简化版：从已验证的数据补充 OSM 边界
适用场景：已有 LLM + AWS 验证的数据，只需要补充边界
"""

import json
import time
import requests
from typing import List, Dict, Any


def load_verified_neighbourhoods(file_path: str) -> List[Dict[str, Any]]:
    """
    从现有的验证结果加载 neighbourhood 列表
    
    Args:
        file_path: 验证结果文件路径（如 data/gpt-5.2-ws_tokyo_B.json）
    
    Returns:
        已验证的 neighbourhood 列表
    """
    print(f"\n{'='*70}")
    print(f"Step 1: 加载已验证的 neighbourhood 数据")
    print(f"{'='*70}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 根据你的实际数据结构调整
    neighbourhoods = []
    for item in data.get('neighbourhoods', []):
        if item.get('verified', False):  # 只处理已验证的
            neighbourhoods.append({
                'name': item['name'],
                'name_local': item.get('name_local', ''),
                'city': item.get('city', 'Tokyo'),
                'aws_entity_id': item.get('aws_entity_id'),
                'aws_match_score': item.get('match_score', 0)
            })
    
    print(f"✅ 加载了 {len(neighbourhoods)} 个已验证的 neighbourhood")
    return neighbourhoods


def get_osm_boundary(name: str, city: str) -> Dict[str, Any]:
    """从 OpenStreetMap 获取边界"""
    print(f"   🗺️  获取 OSM 边界: {name}")
    
    nominatim_url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': f'{name}, {city}, Japan',
        'format': 'json',
        'polygon_geojson': 1,
        'limit': 1
    }
    headers = {'User-Agent': 'OSM-Boundary-Enrichment/1.0'}
    
    try:
        response = requests.get(nominatim_url, params=params, headers=headers, timeout=10)
        data = response.json()
        
        if data and len(data) > 0:
            result = data[0]
            geojson = result.get('geojson')
            
            if geojson:
                coords = geojson.get('coordinates', [])
                if geojson['type'] == 'Polygon':
                    point_count = len(coords[0]) if coords else 0
                elif geojson['type'] == 'MultiPolygon':
                    point_count = sum(len(poly[0]) for poly in coords if poly)
                else:
                    point_count = 0
                
                print(f"   ✅ OSM 边界获取成功 ({point_count} 个坐标点)")
                
                return {
                    "osm_type": result.get('osm_type'),
                    "osm_id": result.get('osm_id'),
                    "geometry": geojson,
                    "point_count": point_count
                }
        
        print(f"   ⚠️  未找到 OSM 边界")
        return None
        
    except Exception as e:
        print(f"   ❌ OSM 查询失败: {e}")
        return None


def enrich_with_osm_boundaries(verified_file: str, output_file: str):
    """
    为已验证的 neighbourhoods 补充 OSM 边界
    
    Args:
        verified_file: 输入文件（已验证的数据）
        output_file: 输出文件（补充边界后的完整数据）
    """
    
    print("\n" + "="*70)
    print("  OSM 边界补充工具")
    print("  从已验证的数据补充真实的 Polygon 边界")
    print("="*70)
    
    # Step 1: 加载已验证的数据
    neighbourhoods = load_verified_neighbourhoods(verified_file)
    
    # Step 2: 补充 OSM 边界
    print(f"\n{'='*70}")
    print(f"Step 2: 补充 OSM 边界")
    print(f"{'='*70}\n")
    
    enriched_results = []
    
    for i, neighbourhood in enumerate(neighbourhoods, 1):
        print(f"[{i}/{len(neighbourhoods)}] 处理: {neighbourhood['name']}")
        
        # 获取 OSM 边界
        osm_result = get_osm_boundary(neighbourhood['name'], neighbourhood['city'])
        
        # 合并数据
        enriched = {
            "name": neighbourhood['name'],
            "name_local": neighbourhood['name_local'],
            "city": neighbourhood['city'],
            "aws_entity_id": neighbourhood.get('aws_entity_id'),
            "aws_match_score": neighbourhood.get('aws_match_score'),
            "has_boundary": osm_result is not None
        }
        
        if osm_result:
            enriched.update({
                "osm_type": osm_result['osm_type'],
                "osm_id": osm_result['osm_id'],
                "geometry": osm_result['geometry'],
                "boundary_point_count": osm_result['point_count']
            })
        else:
            # 如果没有 OSM 边界，标记为 None
            enriched.update({
                "geometry": None,
                "boundary_point_count": 0
            })
        
        enriched_results.append(enriched)
        print(f"   ✅ 完成\n")
        
        # 避免请求过快
        time.sleep(1.5)
    
    # Step 3: 保存结果
    output = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "name": r['name'],
                    "name_local": r['name_local'],
                    "city": r['city'],
                    "aws_entity_id": r.get('aws_entity_id'),
                    "aws_match_score": r.get('aws_match_score'),
                    "has_boundary": r['has_boundary'],
                    "boundary_point_count": r['boundary_point_count'],
                    "osm_type": r.get('osm_type'),
                    "osm_id": r.get('osm_id'),
                },
                "geometry": r['geometry'] or {
                    "type": "Point",
                    "coordinates": [0, 0]  # Fallback
                }
            }
            for r in enriched_results
        ],
        "metadata": {
            "source": "Verified data + OSM boundaries",
            "total_count": len(enriched_results),
            "with_boundary": sum(1 for r in enriched_results if r['has_boundary']),
            "no_boundary": sum(1 for r in enriched_results if not r['has_boundary']),
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
        }
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    # 输出总结
    print(f"\n{'='*70}")
    print(f"  完成！")
    print(f"{'='*70}\n")
    
    print(f"✅ 输出文件: {output_file}")
    print(f"✅ 总数量: {output['metadata']['total_count']}")
    print(f"✅ 有边界 (Polygon): {output['metadata']['with_boundary']}")
    print(f"✅ 无边界: {output['metadata']['no_boundary']}")
    
    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    import sys
    
    # 使用示例
    if len(sys.argv) > 2:
        verified_file = sys.argv[1]
        output_file = sys.argv[2]
    else:
        # 默认文件路径
        verified_file = "data/gpt-5.2-ws_tokyo_B.json"  # 你的已验证数据
        output_file = "data/tokyo_with_osm_boundaries.geojson"
    
    enrich_with_osm_boundaries(verified_file, output_file)
