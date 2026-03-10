#!/usr/bin/env python3
"""
Neighbourhood Verification Script
验证 LLM 生成的 neighbourhood 数据，使用 AWS Location Service (GeoPlaces) 进行实体匹配。

用法:
    python3 verify_neighbourhoods.py data/gpt-5.2-ws_tokyo_B.json
    python3 verify_neighbourhoods.py data/gpt-5.2-ws_tokyo_B.json --report html
    python3 verify_neighbourhoods.py data/gpt-5.2-ws_tokyo_B.json --report json --output results/
"""

import argparse
import boto3
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from collections import Counter


# ─── AWS Location Service Client ────────────────────────────────────────────

def get_geo_client(region="us-west-2"):
    """Initialize AWS GeoPlaces client."""
    return boto3.client("geo-places", region_name=region)


def get_location_client(region="us-west-2"):
    """Initialize AWS Location Service client (legacy)."""
    return boto3.client("location", region_name=region)


# ─── Entity Matching ────────────────────────────────────────────────────────

def search_entity(client, name, city, bias_position=None, index_name="poi-poc-index"):
    """
    Search for a neighbourhood entity using AWS Location Service.
    
    Strategy:
    1. Primary search: "{name}, {city}" with SearchPlaceIndexForText
    2. Fallback: try aliases if primary fails or low confidence
    
    Returns dict with entity_id, entity_type, match_score, match_source
    """
    result = {
        "entity_id": None,
        "entity_type": None,
        "entity_match_score": None,
        "match_source": None,
    }
    
    # Primary search
    try:
        params = {
            "IndexName": index_name,
            "Text": f"{name}, {city}",
            "MaxResults": 5,
        }
        if bias_position:
            params["BiasPosition"] = bias_position
        
        response = client.search_place_index_for_text(**params)
        results = response.get("Results", [])
        
        if results:
            best = results[0]
            place = best.get("Place", {})
            relevance = best.get("Relevance", 0)
            
            # Extract entity info
            place_id = best.get("PlaceId", "")
            categories = place.get("Categories", [])
            entity_type = categories[0] if categories else None
            
            # Check for meaningful match
            label = place.get("Label", "")
            
            # Score: relevance * 100, capped at 100
            score = min(round(relevance * 100, 1), 100.0)
            
            if score >= 50:
                result["entity_id"] = place_id or _extract_id_from_label(label)
                result["entity_type"] = entity_type or _infer_type(place)
                result["entity_match_score"] = score
                result["match_source"] = "primary"
                return result
    except Exception as e:
        # Silently continue to fallback
        pass
    
    return result


def search_entity_with_fallback(client, neighbourhood, city, bias_position=None, index_name="poi-poc-index"):
    """
    Search with primary name, then try aliases as fallback.
    """
    name = neighbourhood["display_name"]
    aliases = neighbourhood.get("aliases", [])
    
    # Primary search
    result = search_entity(client, name, city, bias_position, index_name)
    if result["entity_id"]:
        return result
    
    # Fallback: try each alias
    for alias in aliases:
        result = search_entity(client, alias, city, bias_position, index_name)
        if result["entity_id"]:
            result["match_source"] = "fallback"
            return result
    
    # No match found
    return {
        "entity_id": None,
        "entity_type": None,
        "entity_match_score": None,
        "match_source": None,
    }


def _extract_id_from_label(label):
    """Extract a usable ID from the label if no PlaceId."""
    return str(hash(label) & 0xFFFFFFFF)


def _infer_type(place):
    """Infer entity type from place data."""
    label = place.get("Label", "").lower()
    if "station" in label:
        return "MetroStation"
    elif "district" in label or "ward" in label or "区" in label:
        return "District"
    return "Place"


# ─── GeoPlaces API (newer) ──────────────────────────────────────────────────

def search_entity_geoplaces(client, name, city, bias_position=None, aliases=None):
    """
    Search using the newer GeoPlaces API (geo-places).
    BiasPosition is required by the API.
    """
    result = {
        "entity_id": None,
        "entity_type": None,
        "entity_match_score": None,
        "match_source": None,
        "matched_title": None,
    }
    
    if not bias_position:
        return result
    
    try:
        response = client.search_text(
            QueryText=f"{name}, {city}",
            BiasPosition=bias_position,
            MaxResults=5,
        )
        items = response.get("ResultItems", [])
        
        if items:
            best = items[0]
            place_id = best.get("PlaceId", "")
            place_type = best.get("PlaceType", "")
            title = best.get("Title", "")
            address = best.get("Address", {})
            address_label = address.get("Label", "")
            sub_district = address.get("SubDistrict", "")
            locality = address.get("Locality", "")
            
            # Build a set of all searchable text from the result
            result_text = f"{title} {address_label} {sub_district} {locality}".lower()
            
            # Build a set of all query names (display_name + aliases)
            query_names = [name.lower()]
            if aliases:
                query_names.extend([a.lower() for a in aliases])
            
            # Score: check if any query name matches the result
            score = 0.0
            matched_by = None
            
            for qn in query_names:
                if qn in result_text:
                    score = 100.0
                    matched_by = qn
                    break
            
            if score == 0:
                # Partial match: first 4+ chars
                for qn in query_names:
                    if len(qn) >= 4 and qn[:4] in result_text:
                        score = 80.0
                        matched_by = qn[:4] + "..."
                        break
            
            if score == 0:
                # GeoPlaces returned something in the right city — low confidence match
                score = 60.0
            
            result["entity_id"] = place_id
            result["entity_type"] = place_type or "Place"
            result["entity_match_score"] = score
            result["match_source"] = "primary"
            result["matched_title"] = title
            return result
            
    except Exception as e:
        result["_error"] = str(e)
    
    return result


def search_with_fallback_geoplaces(client, neighbourhood, city, bias_position=None):
    """Search using GeoPlaces with alias fallback."""
    name = neighbourhood["display_name"]
    aliases = neighbourhood.get("aliases", [])
    
    # Primary search includes aliases for scoring
    result = search_entity_geoplaces(client, name, city, bias_position, aliases=aliases)
    if result.get("entity_id") and result.get("entity_match_score", 0) >= 80:
        return result
    
    # If low confidence, try searching directly with each alias
    primary_result = result  # Keep as fallback
    for alias in aliases:
        result = search_entity_geoplaces(client, alias, city, bias_position, aliases=[name] + aliases)
        if result.get("entity_id") and result.get("entity_match_score", 0) >= 80:
            result["match_source"] = "fallback"
            return result
    
    # Return best we have (primary even if low score)
    if primary_result.get("entity_id"):
        return primary_result
    
    return {
        "entity_id": None,
        "entity_type": None,
        "entity_match_score": None,
        "match_source": None,
        "matched_title": None,
    }


# ─── City Coordinates ────────────────────────────────────────────────────────

# Common city coordinates [longitude, latitude]
CITY_COORDS = {
    "Tokyo": [139.6917, 35.6895], "Mumbai": [72.8777, 19.0760], "Dubai": [55.2708, 25.2048],
    "London": [-0.1276, 51.5074], "Osaka": [135.5023, 34.6937], "Bangkok": [100.5018, 13.7563],
    "Seoul": [126.9780, 37.5665], "Mecca": [39.8579, 21.3891], "Fukuoka": [130.4017, 33.5904],
    "Istanbul": [28.9784, 41.0082], "Paris": [2.3522, 48.8566], "Barcelona": [2.1734, 41.3851],
    "Rome": [12.4964, 41.9028], "New York": [-74.0060, 40.7128], "Singapore": [103.8198, 1.3521],
    "Amsterdam": [4.9041, 52.3676], "Phuket": [98.3923, 7.8804], "Da Nang": [108.2022, 16.0544],
    "Taipei": [121.5654, 25.0330], "Hong Kong": [114.1694, 22.3193], "Madrid": [-3.7038, 40.4168],
    "Pattaya": [100.8825, 12.9236], "Kuala Lumpur": [101.6869, 3.1390], "Sapporo": [141.3545, 43.0621],
    "Milan": [9.1900, 45.4642], "Sydney": [151.2093, -33.8688], "Shanghai": [121.4737, 31.2304],
    "Beijing": [116.4074, 39.9042], "Las Vegas": [-115.1398, 36.1699], "Rio de Janeiro": [-43.1729, -22.9068],
    "Cancun": [-86.8515, 21.1619], "Busan": [129.0756, 35.1796], "Kyoto": [135.7681, 35.0116],
    "San Francisco": [-122.4194, 37.7749], "Berlin": [13.4050, 52.5200], "Vienna": [16.3738, 48.2082],
    "Prague": [14.4378, 50.0755], "Lisbon": [-9.1393, 38.7223], "Athens": [23.7275, 37.9838],
    "Cairo": [31.2357, 30.0444], "Bali": [115.1889, -8.4095], "Hanoi": [105.8342, 21.0278],
    "Ho Chi Minh City": [106.6297, 10.8231], "Nha Trang": [109.1967, 12.2388],
    "Phu Quoc": [103.9610, 10.2270], "Punta Cana": [-68.3725, 18.5601],
    "Bengaluru": [77.5946, 12.9716], "Madinah": [39.6142, 24.4539],
    "Palma": [2.6502, 39.5696], "Koh Samui": [100.0609, 9.5120],
}


def get_city_coordinates(city, region="us-west-2"):
    """Get city center coordinates. First check local cache, then try GeoPlaces API."""
    if city in CITY_COORDS:
        return CITY_COORDS[city]
    
    # Try GeoPlaces geocode
    try:
        client = boto3.client("geo-places", region_name=region)
        resp = client.geocode(QueryText=city, MaxResults=1)
        items = resp.get("ResultItems", [])
        if items:
            pos = items[0].get("Position", [])
            if len(pos) == 2:
                return pos
    except Exception:
        pass
    
    return None


# ─── Structural Validation ──────────────────────────────────────────────────

def validate_structure(data):
    """Validate the structural integrity of neighbourhood JSON."""
    issues = []
    
    # Required top-level fields
    if "city" not in data:
        issues.append({"level": "error", "msg": "Missing 'city' field"})
    if "macro_areas" not in data:
        issues.append({"level": "error", "msg": "Missing 'macro_areas' field"})
        return issues
    
    all_names = []
    containment_refs = set()
    defined_names = set()
    
    for ma_idx, ma in enumerate(data["macro_areas"]):
        if "name" not in ma:
            issues.append({"level": "error", "msg": f"macro_area[{ma_idx}] missing 'name'"})
        
        for n_idx, n in enumerate(ma.get("neighbourhoods", [])):
            name = n.get("display_name", f"unknown_{ma_idx}_{n_idx}")
            defined_names.add(name)
            all_names.append(name)
            
            # Required fields
            for field in ["display_name", "aliases", "traveller_tag", "geo_tag"]:
                if field not in n:
                    issues.append({"level": "warn", "msg": f"'{name}' missing field '{field}'"})
            
            # Containment references
            for ref in n.get("contains", []):
                containment_refs.add((name, ref, "contains"))
            for ref in n.get("contained_by", []):
                containment_refs.add((name, ref, "contained_by"))
    
    # Check for duplicates
    name_counts = Counter(all_names)
    for name, count in name_counts.items():
        if count > 1:
            issues.append({"level": "warn", "msg": f"Duplicate neighbourhood: '{name}' appears {count} times"})
    
    # Validate containment references
    for source, target, rel_type in containment_refs:
        if target not in defined_names:
            issues.append({"level": "warn", "msg": f"'{source}' {rel_type} '{target}' but '{target}' is not defined"})
    
    # Check containment symmetry
    contains_map = {}
    contained_by_map = {}
    for ma in data["macro_areas"]:
        for n in ma.get("neighbourhoods", []):
            name = n.get("display_name", "")
            contains_map[name] = set(n.get("contains", []))
            contained_by_map[name] = set(n.get("contained_by", []))
    
    for name, contains in contains_map.items():
        for child in contains:
            if child in contained_by_map and name not in contained_by_map[child]:
                issues.append({
                    "level": "info",
                    "msg": f"Asymmetric containment: '{name}' contains '{child}' but '{child}' doesn't list '{name}' in contained_by"
                })
    
    return issues


# ─── Report Generation ──────────────────────────────────────────────────────

def generate_summary(data, results):
    """Generate verification summary statistics."""
    total = len(results)
    matched = sum(1 for r in results if r["entity_id"])
    primary = sum(1 for r in results if r["match_source"] == "primary")
    fallback = sum(1 for r in results if r["match_source"] == "fallback")
    no_match = total - matched
    
    entity_types = Counter(r["entity_type"] for r in results if r["entity_type"])
    
    return {
        "city": data.get("city", "Unknown"),
        "city_entity_id": data.get("city_entity_id"),
        "macro_areas_count": len(data.get("macro_areas", [])),
        "total_neighbourhoods": total,
        "matched": matched,
        "primary_matches": primary,
        "fallback_matches": fallback,
        "no_match": no_match,
        "hit_rate": f"{matched/total*100:.1f}%" if total > 0 else "N/A",
        "entity_types": dict(entity_types.most_common()),
        "timestamp": datetime.now().isoformat(),
    }


def generate_json_report(data, results, structural_issues, summary):
    """Generate full JSON report."""
    # Merge results back into neighbourhood data
    enriched = json.loads(json.dumps(data))  # deep copy
    idx = 0
    for ma in enriched["macro_areas"]:
        for n in ma.get("neighbourhoods", []):
            if idx < len(results):
                n["verification"] = results[idx]
            idx += 1
    
    return {
        "summary": summary,
        "structural_issues": structural_issues,
        "verified_data": enriched,
    }


def generate_html_report(data, results, structural_issues, summary):
    """Generate an HTML report similar to comparison_report.html."""
    city = summary["city"]
    total = summary["total_neighbourhoods"]
    matched = summary["matched"]
    primary = summary["primary_matches"]
    fallback = summary["fallback_matches"]
    no_match = summary["no_match"]
    hit_rate = summary["hit_rate"]
    
    # Build neighbourhood rows
    rows = []
    idx = 0
    for ma in data["macro_areas"]:
        for n in ma.get("neighbourhoods", []):
            r = results[idx] if idx < len(results) else {}
            eid = r.get("entity_id") or "—"
            etype = r.get("entity_type") or "—"
            score = r.get("entity_match_score")
            score_str = f"{score}" if score is not None else "—"
            source = r.get("match_source") or "—"
            
            # Color coding
            if r.get("entity_id"):
                status_class = "ok" if source == "primary" else "warn"
                status = "✓" if source == "primary" else "⚡"
            else:
                status_class = "err"
                status = "✗"
            
            rows.append(f"""<tr>
  <td>{n.get('display_name','')}</td>
  <td>{ma['name']}</td>
  <td>{', '.join(n.get('aliases', []))}</td>
  <td class="{status_class}">{status} {etype}</td>
  <td>{score_str}</td>
  <td>{source}</td>
  <td>{r.get('matched_title', '') or ''}</td>
  <td><code>{eid[:20]}{'...' if len(str(eid))>20 else ''}</code></td>
</tr>""")
            idx += 1
    
    # Structural issues rows
    issue_rows = ""
    for issue in structural_issues:
        lvl = issue["level"]
        css = {"error": "err", "warn": "warn", "info": "text-dim"}.get(lvl, "")
        issue_rows += f'<tr><td class="{css}">{lvl.upper()}</td><td>{issue["msg"]}</td></tr>\n'
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Neighbourhood Verification — {city}</title>
<style>
:root {{
  --bg: #0d1117; --bg2: #161b22; --bg3: #21262d; --border: #30363d;
  --text: #e6edf3; --text-dim: #7d8590; --ok: #3fb950; --err: #f85149; --warn: #d29922;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: system-ui, sans-serif; font-size:14px; color:var(--text); background:var(--bg); padding:24px; }}
.container {{ max-width:1200px; margin:0 auto; }}
h1 {{ font-size:20px; margin-bottom:4px; }}
h2 {{ font-size:11px; font-weight:500; letter-spacing:.1em; text-transform:uppercase; color:var(--text-dim); margin:28px 0 12px; padding-bottom:8px; border-bottom:1px solid var(--border); }}
.subtitle {{ color:var(--text-dim); font-size:13px; margin-bottom:20px; }}
.card {{ background:var(--bg2); border:1px solid var(--border); border-radius:6px; padding:20px; margin-bottom:16px; }}
.summary-grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(140px,1fr)); gap:12px; }}
.summary-card {{ background:var(--bg3); border:1px solid var(--border); border-radius:6px; padding:16px; text-align:center; }}
.summary-card .label {{ font-size:10px; text-transform:uppercase; color:var(--text-dim); margin-bottom:6px; }}
.summary-card .value {{ font-size:1.5rem; font-weight:700; }}
.ok {{ color:var(--ok); }} .err {{ color:var(--err); }} .warn {{ color:var(--warn); }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th {{ text-align:left; padding:8px 10px; border-bottom:2px solid var(--border); color:var(--text-dim); font-size:10px; text-transform:uppercase; letter-spacing:.08em; }}
td {{ padding:8px 10px; border-bottom:1px solid var(--border); }}
tr:hover {{ background:var(--bg3); }}
code {{ font-family: monospace; font-size:12px; color:var(--text-dim); }}
</style>
</head>
<body>
<div class="container">
  <h1>Neighbourhood Verification — {city}</h1>
  <div class="subtitle">Generated {summary['timestamp']} · AWS Location Service Entity Match</div>

  <h2>Summary</h2>
  <div class="summary-grid">
    <div class="summary-card"><div class="label">Total</div><div class="value">{total}</div></div>
    <div class="summary-card"><div class="label">Matched</div><div class="value ok">{matched}</div></div>
    <div class="summary-card"><div class="label">Primary</div><div class="value ok">{primary}</div></div>
    <div class="summary-card"><div class="label">Fallback</div><div class="value warn">{fallback}</div></div>
    <div class="summary-card"><div class="label">No Match</div><div class="value {'err' if no_match else 'ok'}">{no_match}</div></div>
    <div class="summary-card"><div class="label">Hit Rate</div><div class="value ok">{hit_rate}</div></div>
  </div>

  <h2>Entity Types</h2>
  <div class="card">
    <table>
      <tr><th>Type</th><th>Count</th></tr>
      {''.join(f'<tr><td>{t}</td><td>{c}</td></tr>' for t, c in summary['entity_types'].items())}
    </table>
  </div>

  {'<h2>Structural Issues</h2><div class="card"><table><tr><th>Level</th><th>Message</th></tr>' + issue_rows + '</table></div>' if structural_issues else ''}

  <h2>Neighbourhood Details</h2>
  <div class="card" style="overflow-x:auto;">
    <table>
      <tr><th>Neighbourhood</th><th>Macro Area</th><th>Aliases</th><th>Entity Type</th><th>Score</th><th>Source</th><th>Matched Title</th><th>Entity ID</th></tr>
      {''.join(rows)}
    </table>
  </div>
</div>
</body>
</html>"""
    return html


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Verify LLM-generated neighbourhood data using AWS Location Service"
    )
    parser.add_argument("input", help="Path to neighbourhood JSON file (e.g., gpt-5.2-ws_tokyo_B.json)")
    parser.add_argument("--report", choices=["json", "html", "both"], default="both",
                        help="Output format (default: both)")
    parser.add_argument("--output", default=".", help="Output directory (default: current dir)")
    parser.add_argument("--index", default="poi-poc-index", help="Place Index name (legacy API)")
    parser.add_argument("--region", default="us-west-2", help="AWS region")
    parser.add_argument("--api", choices=["legacy", "geoplaces", "auto"], default="auto",
                        help="AWS API to use (default: auto)")
    parser.add_argument("--dry-run", action="store_true", help="Validate structure only, skip API calls")
    parser.add_argument("--delay", type=float, default=0.1, help="Delay between API calls in seconds")
    
    args = parser.parse_args()
    
    # Load input
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ File not found: {input_path}", file=sys.stderr)
        sys.exit(1)
    
    with open(input_path) as f:
        data = json.load(f)
    
    city = data.get("city", "Unknown")
    print(f"🌍 Verifying neighbourhoods for: {city}")
    
    # Structural validation
    print(f"📋 Running structural validation...")
    issues = validate_structure(data)
    errors = [i for i in issues if i["level"] == "error"]
    warnings = [i for i in issues if i["level"] == "warn"]
    infos = [i for i in issues if i["level"] == "info"]
    print(f"   {len(errors)} errors, {len(warnings)} warnings, {len(infos)} info")
    
    if errors:
        for e in errors:
            print(f"   ❌ {e['msg']}")
        if not args.dry_run:
            print("   Fix errors before running entity verification.")
            sys.exit(1)
    
    # Collect all neighbourhoods
    neighbourhoods = []
    for ma in data.get("macro_areas", []):
        for n in ma.get("neighbourhoods", []):
            neighbourhoods.append(n)
    
    total = len(neighbourhoods)
    print(f"📍 Found {total} neighbourhoods across {len(data.get('macro_areas',[]))} macro areas")
    
    if args.dry_run:
        print(f"\n🔍 Dry run — skipping API verification")
        results = [{"entity_id": None, "entity_type": None, "entity_match_score": None, "match_source": None} for _ in neighbourhoods]
    else:
        # Initialize AWS client
        use_geoplaces = False
        geo_client = None
        loc_client = None
        
        # Get city coordinates for BiasPosition
        city_coords = get_city_coordinates(city, args.region)
        if city_coords:
            print(f"📍 City coordinates: {city_coords[1]:.4f}°N, {city_coords[0]:.4f}°E")
        
        if args.api in ("geoplaces", "auto"):
            try:
                geo_client = get_geo_client(args.region)
                # Test call with BiasPosition
                if city_coords:
                    geo_client.search_text(QueryText=f"test, {city}", BiasPosition=city_coords, MaxResults=1)
                    use_geoplaces = True
                    print(f"🔌 Using GeoPlaces API")
                else:
                    print(f"⚠️  No city coordinates found, trying legacy API")
            except Exception as e:
                if args.api == "geoplaces":
                    print(f"❌ GeoPlaces API not available: {e}", file=sys.stderr)
                    sys.exit(1)
                # Fall back to legacy
                use_geoplaces = False
        
        if not use_geoplaces:
            try:
                loc_client = get_location_client(args.region)
                print(f"🔌 Using legacy Location Service (index: {args.index})")
            except Exception as e:
                print(f"❌ Cannot initialize AWS client: {e}", file=sys.stderr)
                sys.exit(1)
        
        # Verify each neighbourhood
        print(f"\n🔍 Verifying entities...")
        results = []
        for i, n in enumerate(neighbourhoods):
            name = n.get("display_name", "?")
            sys.stdout.write(f"\r   [{i+1}/{total}] {name:<30}")
            sys.stdout.flush()
            
            if use_geoplaces:
                result = search_with_fallback_geoplaces(geo_client, n, city, bias_position=city_coords)
            else:
                result = search_entity_with_fallback(loc_client, n, city, index_name=args.index)
            
            results.append(result)
            
            if args.delay > 0:
                time.sleep(args.delay)
        
        print(f"\r   {'Done!':<50}")
    
    # Generate summary
    summary = generate_summary(data, results)
    
    print(f"\n{'='*50}")
    print(f"📊 Results for {city}")
    print(f"   Total: {summary['total_neighbourhoods']}")
    print(f"   Matched: {summary['matched']} ({summary['hit_rate']})")
    print(f"   Primary: {summary['primary_matches']}")
    print(f"   Fallback: {summary['fallback_matches']}")
    print(f"   No match: {summary['no_match']}")
    print(f"{'='*50}")
    
    # Output
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    city_slug = city.lower().replace(" ", "_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if args.report in ("json", "both"):
        json_report = generate_json_report(data, results, issues, summary)
        json_path = output_dir / f"verification_{city_slug}_{ts}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_report, f, ensure_ascii=False, indent=2)
        print(f"📄 JSON report: {json_path}")
    
    if args.report in ("html", "both"):
        html_report = generate_html_report(data, results, issues, summary)
        html_path = output_dir / f"verification_{city_slug}_{ts}.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_report)
        print(f"📄 HTML report: {html_path}")
    
    print(f"\n✅ Done!")


if __name__ == "__main__":
    main()
