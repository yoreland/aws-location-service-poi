# AWS Location Service POI POC

🌍 **AWS Location Service 兴趣点(POI)概念验证项目**

本项目演示如何使用 AWS Location Service 从多个国际城市抓取兴趣点(Point of Interest)数据。

## 📊 项目概述

- **数据源**: AWS Location Service (基于 HERE Technologies/Esri)
- **覆盖城市**: 东京、巴黎、纽约（三大洲代表性城市）
- **POI 类型**: 景点、餐厅、酒店、地址等
- **数据格式**: JSON

## 🎯 功能特性

### 核心功能
- ✅ 基于地理位置搜索附近 POI
- ✅ 基于文本关键词搜索特定类型 POI
- ✅ 多城市批量数据采集
- ✅ 结构化 JSON 输出
- ✅ 详细的相关性评分

### 数据字段
每个 POI 包含以下信息：
- 城市和大洲
- 名称和地址
- 精确坐标（经纬度）
- POI 类型/分类
- 相关性评分

## 📁 项目结构

```
aws-location-service-poi/
├── README.md                           # 项目说明
├── aws_location_poi_poc.py             # 主程序脚本
├── requirements.txt                    # Python 依赖
├── data/                               # 数据目录
│   ├── aws_location_pois_20260303_090038.json    # 原始数据
│   └── tokyo_pois_sample.json          # 东京样本数据
├── docs/                               # 文档目录
│   ├── DATA_ANALYSIS.md                # 数据分析报告
│   └── API_USAGE.md                    # API 使用说明
└── examples/                           # 示例代码
    └── query_examples.py               # 查询示例
```

## 🚀 快速开始

### 前置要求

- Python 3.8+
- AWS 账户
- AWS CLI 配置完成
- boto3 SDK

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置 AWS 凭证

```bash
aws configure
```

输入你的 AWS Access Key ID 和 Secret Access Key。

### 创建 Place Index

```bash
aws location create-place-index \
    --index-name poi-poc-index \
    --data-source Esri \
    --pricing-plan RequestBasedUsage
```

### 运行脚本

```bash
python aws_location_poi_poc.py
```

## 📊 数据样本

### 东京 POI 示例

```json
{
  "City": "Tokyo",
  "Continent": "Asia",
  "Name": "Hyatt Regency Tokyo, Shinjuku, Tokyo, JPN",
  "Coordinates": {
    "Longitude": 139.690998544,
    "Latitude": 35.690886306
  },
  "Address": " ",
  "Country": "JPN",
  "Entity_Type": "PointOfInterestType",
  "Description": "Hyatt Regency Tokyo, Shinjuku, Tokyo, JPN - hotel in Tokyo",
  "Relevance": 1
}
```

## 📈 数据规模

### 当前采样数据
- **东京**: 10 个 POI（新宿区西新宿周边）
- **巴黎**: 10 个 POI（市政厅周边）
- **纽约**: 10 个 POI（市政厅/自由岛周边）

### AWS Location Service 实际数据规模
- **东京全域**: 约 50万-100万+ POI
- **新宿区**: 约 5万-10万 POI
- **查询区域限制**: 本脚本使用 `max_results=3-5` 作为示例

> 💡 **提示**: 要获取更多数据，可修改 `max_results` 参数或调整查询区域。

## 🔧 API 使用说明

### 1. 位置搜索 (SearchPlaceIndexForPosition)

根据经纬度坐标搜索附近的 POI：

```python
response = location_client.search_place_index_for_position(
    IndexName='poi-poc-index',
    Position=[139.6917, 35.6895],  # [经度, 纬度]
    MaxResults=10
)
```

### 2. 文本搜索 (SearchPlaceIndexForText)

根据关键词和位置偏好搜索 POI：

```python
response = location_client.search_place_index_for_text(
    IndexName='poi-poc-index',
    Text="restaurant in Tokyo",
    BiasPosition=[139.6917, 35.6895],
    MaxResults=10
)
```

## 🎓 学习资源

- [AWS Location Service 官方文档](https://docs.aws.amazon.com/location/)
- [boto3 Location API 参考](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/location.html)
- [HERE Technologies 数据源](https://www.here.com/)

## 📝 注意事项

### 成本
- AWS Location Service 按请求计费
- 免费套餐: 前12个月每月 50,000 次请求
- 超出后按每 1,000 次请求 $0.50 计费

### 数据准确性
- POI 数据由第三方提供（HERE/Esri）
- 数据更新频率取决于数据源
- 相关性评分范围: 0-1（1 = 最相关）

### 限制
- 单次查询最多返回 50 个结果
- 需要 AWS IAM 权限: `geo:SearchPlaceIndex*`

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 👤 作者

**yoreland**

- GitHub: [@yoreland](https://github.com/yoreland)

---

⭐ 如果这个项目对你有帮助，请给个 Star！
