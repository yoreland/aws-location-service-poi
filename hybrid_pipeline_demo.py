#!/usr/bin/env python3
"""
混合方案：LLM + AWS Location Service + OpenStreetMap
完整的 neighbourhood 数据获取和验证流程
"""

import json
import time
import requests
from typing import List, Dict, Any

# ============================================================================
# Step 1: LLM 生成 neighbourhood 列表 (模拟已有数据)
# ============================================================================

def load_llm_generated_neighbourhoods(city: str) -> List[Dict[str, Any]]:
    """
    加载 LLM 生成的 neighbourhood 列表
    实际项目中这些数据来自: aws-location-service-poi/data/gpt-5.2-ws_tokyo_B.json
    """
    print(f"\n{'='*70}")
    print(f"Step 1: 加载 LLM 生成的 {city} neighbourhood 列表")
    print(f"{'='*70}")
    
    # 模拟从已有的 LLM 生成结果加载
    llm_neighbourhoods = [
        {"name": "Shibuya", "name_local": "渋谷"},
        {"name": "Shinjuku", "name_local": "新宿"},
        {"name": "Harajuku", "name_local": "原宿"},
        {"name": "Roppongi", "name_local": "六本木"},
        {"name": "Ginza", "name_local": "銀座"},
    ]
    
    print(f"✅ 加载了 {len(llm_neighbourhoods)} 个 LLM 生成的 neighbourhood")
    for n in llm_neighbourhoods:
        print(f"   - {n['name']} ({n['name_local']})")
    
    return llm_neighbourhoods


# ============================================================================
# Step 2: AWS Location Service 验证 (模拟)
# ============================================================================

def verify_with_aws_location(neighbourhood: Dict[str, Any], city: str) -> Dict[str, Any]:
    """
    使用 AWS Location Service 验证 neighbourhood 是否存在
    实际项目中使用: boto3.client('location').search_place_index_for_text()
    """
    name = neighbourhood['name']
    
    # 模拟 AWS Location Service 调用
    print(f"   🔍 验证: {name}, {city}")
    
    # 模拟返回结果
    aws_result = {
        "PlaceId": f"aws_{name.lower()}_{int(time.time())}",
        "Match": True,
        "MatchScore": 95.5,
        "Position": [139.7017, 35.6595],  # 模拟中心点坐标
        "Address": {
            "Label": f"{name}, {city}",
            "Municipality": city,
            "SubDistrict": name
        }
    }
    
    print(f"   ✅ AWS 验证通过 (匹配度: {aws_result['MatchScore']}%)")
    return aws_result


# ============================================================================
# Step 3: OpenStreetMap 获取 Polygon 边界
# ============================================================================

def get_osm_boundary(neighbourhood: Dict[str, Any], city: str) -> Dict[str, Any]:
    """
    从 OpenStreetMap 获取真实的 Polygon 边界
    使用 Nominatim API
    """
    name = neighbourhood['name']
    print(f"   🗺️  获取 OSM 边界: {name}")
    
    # Nominatim API 查询
    nominatim_url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': f'{name}, {city}, Japan',
        'format': 'json',
        'polygon_geojson': 1,
        'limit': 1
    }
    headers = {'User-Agent': 'OSM-POC-Hybrid/1.0'}
    
    try:
        response = requests.get(nominatim_url, params=params, headers=headers, timeout=10)
        data = response.json()
        
        if data and len(data) > 0:
            result = data[0]
            geojson = result.get('geojson')
            
            if geojson:
                # 统计坐标点数量
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
        
        print(f"   ⚠️  未找到 OSM 边界，使用 AWS 中心点")
        return None
        
    except Exception as e:
        print(f"   ❌ OSM 查询失败: {e}")
        return None


# ============================================================================
# Step 4: 合并数据
# ============================================================================

def merge_data(
    llm_data: Dict[str, Any],
    aws_data: Dict[str, Any],
    osm_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    合并 LLM、AWS 和 OSM 的数据
    """
    merged = {
        # LLM 生成的基础信息
        "name": llm_data['name'],
        "name_local": llm_data['name_local'],
        
        # AWS 验证结果
        "aws_verified": aws_data['Match'],
        "aws_entity_id": aws_data['PlaceId'],
        "aws_match_score": aws_data['MatchScore'],
        "aws_center": aws_data['Position'],
        
        # OSM 边界数据
        "has_boundary": osm_data is not None,
    }
    
    if osm_data:
        merged.update({
            "osm_type": osm_data['osm_type'],
            "osm_id": osm_data['osm_id'],
            "geometry": osm_data['geometry'],
            "boundary_point_count": osm_data['point_count'],
        })
    else:
        # 如果没有 OSM 边界，使用 AWS 中心点作为 fallback
        merged.update({
            "geometry": {
                "type": "Point",
                "coordinates": aws_data['Position']
            },
            "boundary_point_count": 1,
        })
    
    return merged


# ============================================================================
# Main: 完整的混合方案流程
# ============================================================================

def main():
    """
    执行完整的混合方案流程
    """
    print("\n" + "="*70)
    print("  混合方案：LLM + AWS + OSM")
    print("  完整的 Neighbourhood 数据获取流程")
    print("="*70)
    
    city = "Tokyo"
    
    # Step 1: 加载 LLM 生成的列表
    llm_neighbourhoods = load_llm_generated_neighbourhoods(city)
    
    # Step 2 & 3 & 4: 验证、获取边界、合并
    print(f"\n{'='*70}")
    print(f"Step 2-4: AWS 验证 → OSM 边界 → 合并数据")
    print(f"{'='*70}\n")
    
    final_results = []
    
    for i, neighbourhood in enumerate(llm_neighbourhoods, 1):
        print(f"[{i}/{len(llm_neighbourhoods)}] 处理: {neighbourhood['name']}")
        
        # Step 2: AWS 验证
        aws_result = verify_with_aws_location(neighbourhood, city)
        
        # Step 3: OSM 边界
        osm_result = get_osm_boundary(neighbourhood, city)
        
        # Step 4: 合并
        merged = merge_data(neighbourhood, aws_result, osm_result)
        final_results.append(merged)
        
        print(f"   ✅ 合并完成\n")
        
        # 避免请求过快
        time.sleep(1.5)
    
    # 保存最终结果
    output = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "name": r['name'],
                    "name_local": r['name_local'],
                    "aws_verified": r['aws_verified'],
                    "aws_entity_id": r['aws_entity_id'],
                    "aws_match_score": r['aws_match_score'],
                    "has_boundary": r['has_boundary'],
                    "boundary_point_count": r['boundary_point_count'],
                    "osm_type": r.get('osm_type'),
                    "osm_id": r.get('osm_id'),
                },
                "geometry": r['geometry']
            }
            for r in final_results
        ],
        "metadata": {
            "city": city,
            "source": "Hybrid: LLM + AWS Location Service + OpenStreetMap",
            "total_count": len(final_results),
            "with_boundary": sum(1 for r in final_results if r['has_boundary']),
            "point_only": sum(1 for r in final_results if not r['has_boundary']),
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
        }
    }
    
    output_file = f"hybrid_{city.lower()}_neighbourhoods.geojson"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    # 输出总结
    print(f"\n{'='*70}")
    print(f"  完成！混合方案数据流程总结")
    print(f"{'='*70}\n")
    
    print(f"✅ 输出文件: {output_file}")
    print(f"✅ 总数量: {output['metadata']['total_count']}")
    print(f"✅ 有边界 (Polygon): {output['metadata']['with_boundary']}")
    print(f"✅ 仅中心点 (Point): {output['metadata']['point_only']}")
    
    print(f"\n数据流程:")
    print(f"  1️⃣  LLM 生成 → {len(llm_neighbourhoods)} 个 neighbourhood")
    print(f"  2️⃣  AWS 验证 → {sum(1 for r in final_results if r['aws_verified'])} 个通过验证")
    print(f"  3️⃣  OSM 边界 → {output['metadata']['with_boundary']} 个获取到真实边界")
    print(f"  4️⃣  合并存储 → 完成！")
    
    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    main()
