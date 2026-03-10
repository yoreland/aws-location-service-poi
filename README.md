# AWS Location Service — POI & Neighbourhood Verification

🌍 **使用 AWS Location Service 验证地理数据的概念验证项目**

本项目包含两个核心功能：
1. **POI 数据采集** — 从 AWS Location Service 抓取兴趣点 (Point of Interest) 数据
2. **Neighbourhood 验证** — 使用 AWS GeoPlaces API 验证 LLM 生成的 neighbourhood 数据准确性

---

## 📁 项目结构

```
aws-location-service-poi/
├── README.md                          # 项目说明（本文件）
├── aws_location_poi_poc.py            # POI 数据采集脚本
├── verify_neighbourhoods.py           # ⭐ Neighbourhood 验证脚本
├── requirements.txt                   # Python 依赖
├── data/                              # 输入数据
│   ├── gpt-5.2-ws_tokyo_B.json       # 示例：东京 neighbourhood 数据
│   ├── comparison_report.html         # 200 城市对比报告（参考）
│   └── ...
├── results/                           # 验证结果输出
│   ├── verification_tokyo_*.json      # JSON 格式报告
│   └── verification_tokyo_*.html      # HTML 可视化报告
├── docs/                              # 文档
│   ├── DATA_ANALYSIS.md
│   └── API_USAGE.md
└── examples/
    └── query_examples.py
```

---

## ⭐ Neighbourhood 验证（核心功能）

### 这是什么？

LLM（如 GPT-5.2）可以为任意城市生成结构化的 neighbourhood 数据，包括：
- 区域名称和别名
- 层级关系（包含/被包含）
- 旅行者标签和地理标签
- 宏观区域分组

**但 LLM 生成的数据需要验证。** 本脚本使用 AWS GeoPlaces API 对每个 neighbourhood 进行实体匹配验证，确保它们对应真实的地理位置。

### 快速开始

#### 1. 前置条件

```bash
# Python 3.8+
python3 --version

# AWS CLI 已配置，且 IAM 权限包含 GeoPlaces
aws sts get-caller-identity

# 安装依赖
pip install -r requirements.txt
```

#### 2. IAM 权限配置

你的 AWS IAM Role/User 需要以下权限：

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "geo-places:SearchText",
        "geo-places:GetPlace",
        "geo-places:Geocode"
      ],
      "Resource": "*"
    }
  ]
}
```

#### 3. 准备输入数据

Neighbourhood JSON 格式要求：

```json
{
  "city": "Tokyo",
  "city_entity_id": "27542089",
  "macro_areas": [
    {
      "name": "Central Tokyo (Chiyoda / Chuo)",
      "neighbourhoods": [
        {
          "display_name": "Marunouchi",
          "aliases": ["丸の内", "Marunouchi Business District"],
          "contains": ["Otemachi", "Yaesu"],
          "contained_by": [],
          "traveller_tag": ["Business_traveler", "Luxury_traveler"],
          "geo_tag": ["Good transportation", "Safe", "Cost: high"]
        }
      ]
    }
  ]
}
```

> 💡 `data/gpt-5.2-ws_tokyo_B.json` 是一个完整的示例文件。

#### 4. 运行验证

```bash
# 基本用法 — 验证并生成 JSON + HTML 报告
python3 verify_neighbourhoods.py data/gpt-5.2-ws_tokyo_B.json --output results/

# 仅生成 HTML 报告
python3 verify_neighbourhoods.py data/gpt-5.2-ws_tokyo_B.json --report html --output results/

# 仅做结构验证（不调用 AWS API，不产生费用）
python3 verify_neighbourhoods.py data/gpt-5.2-ws_tokyo_B.json --dry-run

# 指定 AWS 区域
python3 verify_neighbourhoods.py data/gpt-5.2-ws_tokyo_B.json --region ap-southeast-1
```

#### 5. 查看结果

运行完成后会输出类似：

```
🌍 Verifying neighbourhoods for: Tokyo
📋 Running structural validation...
   0 errors, 0 warnings, 0 info
📍 Found 39 neighbourhoods across 8 macro areas
📍 City coordinates: 35.6895°N, 139.6917°E
🔌 Using GeoPlaces API

🔍 Verifying entities...
   [39/39] Gotanda                          Done!

==================================================
📊 Results for Tokyo
   Total: 39
   Matched: 39 (100.0%)
   Primary: 38
   Fallback: 1
   No match: 0
==================================================
📄 JSON report: results/verification_tokyo_20260310_034616.json
📄 HTML report: results/verification_tokyo_20260310_034616.html

✅ Done!
```

**HTML 报告**可直接在浏览器中打开，包含：
- 匹配率汇总（总数/命中/未命中）
- 实体类型分布
- 结构验证问题列表
- 每个 neighbourhood 的详细匹配结果

### 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `input` | (必填) | Neighbourhood JSON 文件路径 |
| `--report` | `both` | 输出格式：`json`、`html`、`both` |
| `--output` | `.` | 输出目录 |
| `--region` | `us-west-2` | AWS 区域 |
| `--api` | `auto` | API 选择：`geoplaces`（推荐）、`legacy`、`auto` |
| `--dry-run` | false | 仅做结构验证，跳过 API 调用 |
| `--delay` | `0.1` | API 调用间隔（秒），避免限流 |
| `--index` | `poi-poc-index` | Legacy API 的 Place Index 名称 |

### 验证逻辑说明

脚本执行两层验证：

**1. 结构验证（离线）**
- 必填字段检查（city, macro_areas, display_name 等）
- 重复 neighbourhood 检测
- 包含关系引用有效性（contains/contained_by 指向已定义的 neighbourhood）
- 包含关系对称性检查

**2. 实体匹配验证（在线）**
- 用 neighbourhood 名称 + 城市名调用 GeoPlaces `SearchText` API
- 如果直接命中 → 标记为 `primary`，score 100
- 如果主名称未命中 → 逐个尝试 aliases → 标记为 `fallback`
- 匹配评分基于返回结果的标题/地址是否包含查询名或别名
- 支持多语言匹配（如英文名 "Marunouchi" 匹配日文结果 "丸の内"）

### 匹配结果字段

| 字段 | 说明 |
|------|------|
| `entity_id` | AWS GeoPlaces 返回的 PlaceId |
| `entity_type` | 地点类型（SubDistrict, Locality, PointOfInterest 等）|
| `entity_match_score` | 匹配置信度（100=精确, 80=部分, 60=低置信度）|
| `match_source` | `primary`（主名称命中）或 `fallback`（通过别名命中）|
| `matched_title` | AWS 返回的地点标题 |

### 示例结果（东京）

```
Total: 39 neighbourhoods
Matched: 39 (100.0%)
  - Primary: 38 (直接英文名命中)
  - Fallback: 1 (Shimokitazawa → 通过日文别名 "下北沢" 命中)
Entity types: SubDistrict (26), PointOfInterest (9), Locality (4)
```

---

## 📊 POI 数据采集

### 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置 AWS（需要 geo:SearchPlaceIndex* 权限）
aws configure

# 创建 Place Index（首次使用）
aws location create-place-index \
    --index-name poi-poc-index \
    --data-source Esri \
    --pricing-plan RequestBasedUsage

# 运行采集
python3 aws_location_poi_poc.py
```

### 覆盖城市

默认采集三个城市：东京、巴黎、纽约。可在 `aws_location_poi_poc.py` 中修改 `CITIES` 字典。

---

## 💰 成本说明

| API | 免费额度 | 超出后 |
|-----|---------|--------|
| GeoPlaces SearchText | 前 12 个月每月 50,000 次 | $0.50 / 1,000 次 |
| Location Service SearchPlaceIndexForText | 前 12 个月每月 50,000 次 | $0.50 / 1,000 次 |

> 💡 验证一个城市（~40 个 neighbourhoods）大约消耗 40-80 次 API 调用。200 个城市约 8,000-16,000 次。

---

## 🔧 常见问题

**Q: 出现 `AccessDeniedException`**
A: 检查 IAM 权限，确保包含 `geo-places:SearchText`。参考上方 IAM 配置。

**Q: `--dry-run` 有什么用？**
A: 仅做结构验证（字段完整性、重复检测、包含关系检查），不调用 AWS API，不产生费用。适合在提交 API 验证前先检查数据质量。

**Q: 如何验证其他城市？**
A: 只需准备符合格式要求的 JSON 文件，脚本会自动识别城市名并查找坐标。支持 50+ 常见旅游城市的内置坐标，其他城市会通过 GeoPlaces Geocode API 自动获取。

**Q: `entity_match_score` 60 是什么意思？**
A: GeoPlaces 返回了结果但无法在标题/地址中找到精确匹配。可能是因为返回了当地语言（如日文）而输入是英文。通常仍然是有效匹配，建议人工抽查确认。

---

## 📄 许可证

MIT License

## 👤 作者

**yoreland** — GitHub: [@yoreland](https://github.com/yoreland)
