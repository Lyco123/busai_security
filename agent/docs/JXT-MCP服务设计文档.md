---
title: 默认模块
language_tabs:
  - shell: Shell
  - http: HTTP
  - javascript: JavaScript
  - ruby: Ruby
  - python: Python
  - php: PHP
  - java: Java
  - go: Go
toc_footers: []
includes: []
search: true
code_clipboard: true
highlight_theme: darkula
headingLevel: 2
generator: "@tarslib/widdershins v4.0.30"

---

# MCP接口说明文档
## 📌 接口列表

| 序号 | 模块 | 描述 | 请求方式 |
|------|------|------|----------|
| 1 | 基础数据查询服务 | 车辆明细查询 | POST |
| 2 | 基础数据查询服务 | 驾驶员明细查询 | POST |
| 3 | 基础数据查询服务 | 线路明细查询 | POST |
| 4 | 基础数据查询服务 | 站场明细查询 | POST |
| 5 | 画像查询服务 | 根据车牌日期查询车辆画像明细 | GET |
| 6 | 画像查询服务 | 根据工号日期查询驾驶员画像明细 | GET |
| 7 | 画像查询服务 | 根据名称日期查询线路画像明细 | GET |
| 8 | 画像查询服务 | 根据名称日期查询站场画像明细 | GET |
| 9 | 画像查询服务 | 根据名称日期查询机构画像明细 | GET |
| 10 | 画像查询服务 | 根据机构名称日期查询事故画像明细 | GET |
| 11 | 黑点查询服务 | 根据线路名称查询黑点明细 | GET |
| 12 | 风险追踪查询服务 | 根据车牌日期查询车辆风险明细 | GET |
| 13 | 风险追踪查询服务 | 根据工号日期查询驾驶员风险明细 | GET |
| 14 | 风险追踪查询服务 | 根据名称日期查询线路风险明细 | GET |
| 15 | 风险追踪查询服务 | 根据名称日期查询站场风险明细 | GET |
| 16 | 风险追踪查询服务 | 根据名称日期查询机构风险明细 | GET |

---

# 📌 请求参数构成

| 序号 | 参数类型 | 参数名称 | 参数位置 |
|------|----------|----------|----------|
| 1 | 透传参数 | X-Transparent-Para | HTTP Header |
| 2 | 用户身份参数 | X-Access-Token | HTTP Header |
| 3 | 接口参数（POST） | 详情在各接口说明 | 请求体 Body |
| 4 | 接口参数（GET） | 详情在各接口说明 | URL Parameter |

---

## 🔹 HTTP Header 请求参数示例

### **透传参数示例**

```
X-Transparent-Para={"userName":"admin","requestTime":"2026-03-01 00:00:00"}
```

- **userName**：用户名  
- **requestTime**：请求时间（yyyy-mm-dd hh:mi:ss）

### **用户身份参数示例**

```
X-Access-Token="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJvcmdDb2RlIjoiMDAwMTAwMTAwMDAwMDAwOURaN0ciLCJleHAiOjE3NzQ5MzgyNTgsInVzZXJuYW1lIjoiZ2NpQWRtaW4ifQ.QB1Q7-gqcGX-SPwYZrAlTmNapHzeOiDe1TiNqT8u"
```

---

# 📌 响应参数构成

| 序号 | 参数类型 | 参数名称 | 参数位置 |
|------|----------|----------|----------|
| 1 | 接口响应状态（true 成功 / false 失败） | success | 响应结果体 |
| 2 | 响应时间戳 | timestamp | 响应结果体 |
| 3 | 返回的数据对象 | result | 响应结果体 |
| 4 | 引用源路径（来自大模型 work tools meta） | path | 响应结果体 |
| 5 | 引用源参数（来自大模型 work tools meta） | pathArgs | 响应结果体 |

---

## 🔹 响应参数示例

```json
{
  "success": true,
  "timestamp": 1774932267535,
  "result": {},
  "path": "/driver/safe",
  "pathArgs": {}
}
```

Base URLs:

# Authentication

# mcp服务

## GET 根据车牌日期查询车辆画像明细

GET /mcp/base/absBusProfileMain/queryByNumberplate

根据车牌查询车辆画像明细数据（返回对象包含了车辆基础信息，画像日期、评价类型、风险评分、建议内容、创建人、创建日期、更改人、更改日期、以及接收建议、待确认建议、待优化建议统计数）
仅支持单个车辆的单日画像查询,如果查询条件不存在,则返回对象中result属性null

### 请求参数

|名称|位置|类型|必选|说明|
|---|---|---|---|---|
|bus_anon_id|cookie|string| 否 |匿名用户标识|
|numberplate|query|string| 是 |车牌|
|partition|query|string| 是 |日期，格式是 yyyyMMdd，例如：20251231|
|X-Transparent-Para|header|string| 否 |透明参数，用于传递额外的参数|
|X-Access-Token|header|string| 否 |用户身份的token信息|

> 返回示例

> 200 Response

```json
{
  "path": "",
  "pathArgs": {
    "": ""
  },
  "success": "true",
  "message": "",
  "code": "0",
  "result": {
    "main": {
      "id": "",
      "ppartition": "",
      "busId": "",
      "busName": "",
      "organId": "",
      "organName": "",
      "calculateDate": "",
      "evalutaionType": "",
      "score": 0,
      "suggestedContent": "",
      "creator": "",
      "createTime": "",
      "updater": "",
      "updateTime": "",
      "deleted": "",
      "manager": "",
      "routeName": "",
      "numberPlate": "",
      "ranking": 0,
      "pendingReceiveCount": 0,
      "pendingConfirmCount": 0,
      "pendingOptimizeCount": 0
    },
    "quotaScoreSubList": [
      {
        "id": "",
        "ppartition": "",
        "mainId": "",
        "quotaId": "",
        "quotaName": "",
        "score": 0,
        "weightRate": 0,
        "originalValue": 0,
        "riskData": "",
        "quotaLevel": "",
        "parentId": "",
        "creator": "",
        "createTime": "",
        "updater": "",
        "updateTime": "",
        "deleted": "",
        "ranking": 0,
        "firstQuotaName": "",
        "busId": "",
        "numberPlate": ""
      }
    ]
  },
  "timestamp": "System.currentTimeMillis()"
}
```

### 返回结果

|状态码|状态码含义|说明|数据模型|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|none|[McpresultAbsBusProfileVO](#schemamcpresultabsbusprofilevo)|

## POST 线路明细查询

POST /mcp/ods/odsJituanBsRoute/list

根据线路属性字段去查询线路明细的列表信息，入参是线路信息实体类，包含查询条件，
例如：入参带上线路名称和线路编号信息时，接口会返回同时满足这两个条件的线路列表。
例如：入参{"routeName": "126","routeCode":"1000051"}，接口会返回同时满足这两个条件的线路列表,
如果入参为空，默认查询所有线路;
另一入参是机构编号，如果入参不为空，默认查询该机构下的所有线路，包括子机构的线路

> Body 请求参数

```json
{
  "routeId": "string",
  "routeCode": "string"
}
```

### 请求参数

|名称|位置|类型|必选|说明|
|---|---|---|---|---|
|bus_anon_id|cookie|string| 否 |匿名用户标识|
|organId|query|string| 否 |none|
|pageNo|query|integer| 否 |页码|
|pageSize|query|integer| 否 |每页页数量|
|X-Transparent-Para|header|string| 否 |透明参数，用于传递额外的参数|
|X-Access-Token|header|string| 否 |用户身份的token信息|
|body|body|[OdsJituanBsRoute](#schemaodsjituanbsroute)| 是 |none|

> 返回示例

> 200 Response

```json
{
  "path": "",
  "pathArgs": {
    "": ""
  },
  "success": "true",
  "message": "",
  "code": "0",
  "result": [
    {
      "routeId": "",
      "routeCode": "",
      "intelligenceCode": "",
      "routeName": "",
      "intelligenceName": "",
      "mileage": 0,
      "startToEndSite": "",
      "direction": "",
      "organId": "",
      "motorcadeId": 0,
      "motorcadeCode": "",
      "motorcadeName": "",
      "mileageUp": 0,
      "mileageDown": 0,
      "routeType": "",
      "upFirstTime": "",
      "upLatestTime": "",
      "downFirstTime": "",
      "downLatestTime": "",
      "linePlateOrg": "",
      "plateTypeOrg": "",
      "lineNatureOrg": "",
      "lineTypeOrg": "",
      "remark": "",
      "userTag1": "",
      "userTag2": "",
      "upFirstStationId": "",
      "upLastStationId": "",
      "downFirstStationId": "",
      "downLastStationId": "",
      "organName": "",
      "routeProfileMain": {
        "id": "",
        "ppartition": "",
        "routeId": "",
        "routeName": "",
        "organId": "",
        "organName": "",
        "calculateDate": "",
        "evalutaionType": "",
        "score": 0,
        "suggestedContent": "",
        "creator": "",
        "createTime": "",
        "updater": "",
        "updateTime": "",
        "deleted": "",
        "manager": "",
        "ranking": 0,
        "pendingReceiveCount": 0,
        "pendingConfirmCount": 0,
        "pendingOptimizeCount": 0
      },
      "busCount": 0,
      "driverCount": 0
    }
  ],
  "timestamp": "System.currentTimeMillis()"
}
```

### 返回结果

|状态码|状态码含义|说明|数据模型|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|none|[McpresultListOdsJituanBsRoute](#schemamcpresultlistodsjituanbsroute)|

## POST 车辆明细查询

POST /mcp/base/odsJituanBsBus/list

根据车辆属性字段去查询车辆明细的列表信息，入参是车辆信息实体类，包含查询条件，
例如：入参带上车牌和车辆编号信息时，接口会返回同时满足这两个条件的车辆列表。
例如：入参{"numberPlate": "粤A34049D","busCode":"1000051"}，接口会返回同时满足这两个条件的车辆列表,
如果入参为空，默认查询所有车辆 。另一入参是机构编号，如果入参不为空，默认查询该机构下的所有车辆，包括子机构的车辆

> Body 请求参数

```json
{
  "busId": "string",
  "busCode": "string",
  "numberPlate": "string"
}
```

### 请求参数

|名称|位置|类型|必选|说明|
|---|---|---|---|---|
|bus_anon_id|cookie|string| 否 |匿名用户标识|
|organId|query|string| 否 |机构编号|
|pageNo|query|integer| 否 |页码，默认1|
|pageSize|query|integer| 否 |每页条数，默认10|
|X-Transparent-Para|header|string| 否 |透明参数，用于传递额外的参数|
|X-Access-Token|header|string| 否 |用户身份的token信息|
|body|body|[OdsJituanBsBus](#schemaodsjituanbsbus)| 是 |none|

> 返回示例

> 200 Response

```json
{
  "path": "",
  "pathArgs": {
    "": ""
  },
  "success": "true",
  "message": "",
  "code": "0",
  "result": [
    {
      "busId": "",
      "busCode": "",
      "numberPlate": "",
      "obuid": "",
      "frameNo": "",
      "routeId": "",
      "orgName": "",
      "organId": "",
      "orgCode": "",
      "busType": "",
      "busAge": 0,
      "vehicleType": "",
      "useNature": "",
      "busFactory": "",
      "carryPersonNumber": 0,
      "busLength": 0,
      "busLengthM": 0,
      "busColor": "",
      "fuelType": "",
      "emiStandard": "",
      "batteryCapacity": "",
      "planPurchaseDate": "",
      "isAir": "",
      "engineNo": "",
      "engineType": "",
      "engineFactory": "",
      "hybridBusPowerFactory": "",
      "powerBatteryFactory": "",
      "drivingRange": 0,
      "batteryManufacturer": "",
      "batteryVoltage": "",
      "userTag1": "",
      "userTag2": "",
      "motorcadeId": 0,
      "motorcadeCode": "",
      "routeName": "",
      "motorcadeName": "",
      "busProfileMain": {
        "id": "",
        "ppartition": "",
        "busId": "",
        "busName": "",
        "organId": "",
        "organName": "",
        "calculateDate": "",
        "evalutaionType": "",
        "score": 0,
        "suggestedContent": "",
        "creator": "",
        "createTime": "",
        "updater": "",
        "updateTime": "",
        "deleted": "",
        "manager": "",
        "routeName": "",
        "numberPlate": "",
        "ranking": 0,
        "pendingReceiveCount": 0,
        "pendingConfirmCount": 0,
        "pendingOptimizeCount": 0
      }
    }
  ],
  "timestamp": "System.currentTimeMillis()"
}
```

### 返回结果

|状态码|状态码含义|说明|数据模型|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|none|[McpresultListOdsJituanBsBus](#schemamcpresultlistodsjituanbsbus)|

# 数据模型

<h2 id="tocS_OdsJituanBsBus">OdsJituanBsBus</h2>

<a id="schemaodsjituanbsbus"></a>
<a id="schema_OdsJituanBsBus"></a>
<a id="tocSodsjituanbsbus"></a>
<a id="tocsodsjituanbsbus"></a>

```json
{
  "busId": "string",
  "busCode": "string",
  "numberPlate": "string",
  "obuid": "string",
  "frameNo": "string",
  "routeId": "string",
  "orgName": "string",
  "organId": "string",
  "orgCode": "string",
  "busType": "string",
  "busAge": 0,
  "vehicleType": "string",
  "useNature": "string",
  "busFactory": "string",
  "carryPersonNumber": 0,
  "busLength": 0,
  "busLengthM": 0,
  "busColor": "string",
  "fuelType": "string",
  "emiStandard": "string",
  "batteryCapacity": "string",
  "planPurchaseDate": "string",
  "isAir": "string",
  "engineNo": "string",
  "engineType": "string",
  "engineFactory": "string",
  "hybridBusPowerFactory": "string",
  "powerBatteryFactory": "string",
  "drivingRange": 0,
  "batteryManufacturer": "string",
  "batteryVoltage": "string",
  "userTag1": "string",
  "userTag2": "string",
  "motorcadeId": 0,
  "motorcadeCode": "string",
  "routeName": "string",
  "motorcadeName": "string",
  "busProfileMain": {
    "id": "string",
    "ppartition": "string",
    "busId": "string",
    "busName": "string",
    "organId": "string",
    "organName": "string",
    "calculateDate": "string",
    "evalutaionType": "string",
    "score": 0,
    "suggestedContent": "string",
    "creator": "string",
    "createTime": "string",
    "updater": "string",
    "updateTime": "string",
    "deleted": "string",
    "manager": "string",
    "routeName": "string",
    "numberPlate": "string",
    "ranking": 0,
    "pendingReceiveCount": 0,
    "pendingConfirmCount": 0,
    "pendingOptimizeCount": 0
  }
}

```

### 属性

|名称|类型|必选|约束|中文名|说明|
|---|---|---|---|---|---|
|busId|string|false|none||车辆id|
|busCode|string|false|none||车辆自编号|
|numberPlate|string|false|none||车牌号|
|obuid|string|false|none||智能调度obuid号|
|frameNo|string|false|none||车架号|
|routeId|string|false|none||归属线路编号|
|orgName|string|false|none||机构名称(到车队)|
|organId|string|false|none||机构ID(到车队)|
|orgCode|string|false|none||机构编码(到车队)|
|busType|string|false|none||车辆型号|
|busAge|integer|false|none||车龄|
|vehicleType|string|false|none||车辆类型|
|useNature|string|false|none||使用性质|
|busFactory|string|false|none||制造厂名称|
|carryPersonNumber|integer|false|none||核载人数|
|busLength|number|false|none||车长|
|busLengthM|number|false|none||统计车长|
|busColor|string|false|none||车辆颜色|
|fuelType|string|false|none||燃料类型|
|emiStandard|string|false|none||排放标准|
|batteryCapacity|string|false|none||动力电池容量|
|planPurchaseDate|string|false|none||计划采购日期|
|isAir|string|false|none||是否空调车|
|engineNo|string|false|none||发动机号|
|engineType|string|false|none||发动机类型|
|engineFactory|string|false|none||发动机厂家|
|hybridBusPowerFactory|string|false|none||混合动力动力电池厂家|
|powerBatteryFactory|string|false|none||动力电池厂家|
|drivingRange|number|false|none||纯电动车续驶里程（km）|
|batteryManufacturer|string|false|none||电池生产厂商|
|batteryVoltage|string|false|none||动力电池额定电压|
|userTag1|string|false|none||用户标识1|
|userTag2|string|false|none||用户标识2|
|motorcadeId|integer|false|none||车队id|
|motorcadeCode|string|false|none||车队code|
|routeName|string|false|none||线路名称|
|motorcadeName|string|false|none||车队名|
|busProfileMain|[AbsBusProfileMain](#schemaabsbusprofilemain)|false|none||车辆画像主表（含排名、待接收/待确认/待优化建议数）|

<h2 id="tocS_AbsBusProfileMain">AbsBusProfileMain</h2>

<a id="schemaabsbusprofilemain"></a>
<a id="schema_AbsBusProfileMain"></a>
<a id="tocSabsbusprofilemain"></a>
<a id="tocsabsbusprofilemain"></a>

```json
{
  "id": "string",
  "ppartition": "string",
  "busId": "string",
  "busName": "string",
  "organId": "string",
  "organName": "string",
  "calculateDate": "string",
  "evalutaionType": "string",
  "score": 0,
  "suggestedContent": "string",
  "creator": "string",
  "createTime": "string",
  "updater": "string",
  "updateTime": "string",
  "deleted": "string",
  "manager": "string",
  "routeName": "string",
  "numberPlate": "string",
  "ranking": 0,
  "pendingReceiveCount": 0,
  "pendingConfirmCount": 0,
  "pendingOptimizeCount": 0
}

```

### 属性

|名称|类型|必选|约束|中文名|说明|
|---|---|---|---|---|---|
|id|string|false|none||主键|
|ppartition|string|false|none||分区字段(yyyymmdd)|
|busId|string|false|none||车辆ID（或者叫自编号）|
|busName|string|false|none||车辆名称|
|organId|string|false|none||机构ID|
|organName|string|false|none||机构名称（或者叫所属机构）|
|calculateDate|string|false|none||画像日期（或者叫画像日期）|
|evalutaionType|string|false|none||评价类型（或者叫综合评价）|
|score|integer|false|none||总分（或者叫风险评分）|
|suggestedContent|string|false|none||建议内容|
|creator|string|false|none||创建人|
|createTime|string|false|none||创建日期|
|updater|string|false|none||更改人|
|updateTime|string|false|none||更改时间|
|deleted|string|false|none||是否删除|
|manager|string|false|none||负责人（或者叫负责人）|
|routeName|string|false|none||所属线路（可从车辆基础数据服务关联填充）|
|numberPlate|string|false|none||车牌号（可从车辆基础数据服务关联填充）|
|ranking|integer|false|none||同线路排名|
|pendingReceiveCount|integer(int64)|false|none||待接受建议数（或者叫未接受建议数）|
|pendingConfirmCount|integer(int64)|false|none||待确认建议数（或者叫已接受待处理建议数|
|pendingOptimizeCount|integer(int64)|false|none||待优化建议数（或者叫已处理待优化建议数）|

<h2 id="tocS_OdsJituanBsRoute">OdsJituanBsRoute</h2>

<a id="schemaodsjituanbsroute"></a>
<a id="schema_OdsJituanBsRoute"></a>
<a id="tocSodsjituanbsroute"></a>
<a id="tocsodsjituanbsroute"></a>

```json
{
  "routeId": "string",
  "routeCode": "string",
  "intelligenceCode": "string",
  "routeName": "string",
  "intelligenceName": "string",
  "mileage": 0,
  "startToEndSite": "string",
  "direction": "string",
  "organId": "string",
  "motorcadeId": 0,
  "motorcadeCode": "string",
  "motorcadeName": "string",
  "mileageUp": 0,
  "mileageDown": 0,
  "routeType": "string",
  "upFirstTime": "string",
  "upLatestTime": "string",
  "downFirstTime": "string",
  "downLatestTime": "string",
  "linePlateOrg": "string",
  "plateTypeOrg": "string",
  "lineNatureOrg": "string",
  "lineTypeOrg": "string",
  "remark": "string",
  "userTag1": "string",
  "userTag2": "string",
  "upFirstStationId": "string",
  "upLastStationId": "string",
  "downFirstStationId": "string",
  "downLastStationId": "string",
  "organName": "string",
  "routeProfileMain": {
    "id": "string",
    "ppartition": "string",
    "routeId": "string",
    "routeName": "string",
    "organId": "string",
    "organName": "string",
    "calculateDate": "string",
    "evalutaionType": "string",
    "score": 0,
    "suggestedContent": "string",
    "creator": "string",
    "createTime": "string",
    "updater": "string",
    "updateTime": "string",
    "deleted": "string",
    "manager": "string",
    "ranking": 0,
    "pendingReceiveCount": 0,
    "pendingConfirmCount": 0,
    "pendingOptimizeCount": 0
  },
  "busCount": 0,
  "driverCount": 0
}

```

### 属性

|名称|类型|必选|约束|中文名|说明|
|---|---|---|---|---|---|
|routeId|string|false|none||线路编号|
|routeCode|string|false|none||线路编码|
|intelligenceCode|string|false|none||智能调度系统线路编码|
|routeName|string|false|none||线路名称|
|intelligenceName|string|false|none||智能调度系统线路名称|
|mileage|number|false|none||线路里程|
|startToEndSite|string|false|none||首站往末站停靠站点|
|direction|string|false|none||智能调度系统上行行向|
|organId|string|false|none||机构ID(到车队)|
|motorcadeId|integer|false|none||车队id|
|motorcadeCode|string|false|none||车队code|
|motorcadeName|string|false|none||车队名称|
|mileageUp|number|false|none||首站往末站里程|
|mileageDown|number|false|none||末站往首站里程|
|routeType|string|false|none||线路类型|
|upFirstTime|string|false|none||首站首班车时间|
|upLatestTime|string|false|none||首站末班车时间|
|downFirstTime|string|false|none||末站首班车时间|
|downLatestTime|string|false|none||末站末班车时间|
|linePlateOrg|string|false|none||线路板块(集团)|
|plateTypeOrg|string|false|none||板块分类(集团)|
|lineNatureOrg|string|false|none||线路属性(集团)|
|lineTypeOrg|string|false|none||线路类别(集团)|
|remark|string|false|none||备注|
|userTag1|string|false|none||用户标识1|
|userTag2|string|false|none||用户标识2|
|upFirstStationId|string|false|none||上行首站编号|
|upLastStationId|string|false|none||上行末站编号|
|downFirstStationId|string|false|none||下行首站编号|
|downLastStationId|string|false|none||下行末站编号|
|organName|string|false|none||机构名称|
|routeProfileMain|[AbsRouteProfileMain](#schemaabsrouteprofilemain)|false|none||线路画像主表（含排名、待接收/待确认/待优化建议数）|
|busCount|integer|false|none||车辆数|
|driverCount|integer|false|none||驾驶员数|

<h2 id="tocS_AbsRouteProfileMain">AbsRouteProfileMain</h2>

<a id="schemaabsrouteprofilemain"></a>
<a id="schema_AbsRouteProfileMain"></a>
<a id="tocSabsrouteprofilemain"></a>
<a id="tocsabsrouteprofilemain"></a>

```json
{
  "id": "string",
  "ppartition": "string",
  "routeId": "string",
  "routeName": "string",
  "organId": "string",
  "organName": "string",
  "calculateDate": "string",
  "evalutaionType": "string",
  "score": 0,
  "suggestedContent": "string",
  "creator": "string",
  "createTime": "string",
  "updater": "string",
  "updateTime": "string",
  "deleted": "string",
  "manager": "string",
  "ranking": 0,
  "pendingReceiveCount": 0,
  "pendingConfirmCount": 0,
  "pendingOptimizeCount": 0
}

```

### 属性

|名称|类型|必选|约束|中文名|说明|
|---|---|---|---|---|---|
|id|string|false|none||主键|
|ppartition|string|false|none||分区字段(yyyymmdd)|
|routeId|string|false|none||线路ID（导出：线路ID）|
|routeName|string|false|none||线路名称（导出：线路）|
|organId|string|false|none||机构ID|
|organName|string|false|none||机构名称（导出：所属机构）|
|calculateDate|string|false|none||画像日期（导出：画像日期）|
|evalutaionType|string|false|none||评价类型（导出：综合评价）|
|score|integer|false|none||总分（导出：风险评分）|
|suggestedContent|string|false|none||建议内容|
|creator|string|false|none||创建人|
|createTime|string|false|none||创建日期|
|updater|string|false|none||更改人|
|updateTime|string|false|none||更改时间|
|deleted|string|false|none||是否删除|
|manager|string|false|none||负责人（导出：负责人）|
|ranking|integer|false|none||排名|
|pendingReceiveCount|integer(int64)|false|none||待接受建议数（未接受）（导出：待接受建议）|
|pendingConfirmCount|integer(int64)|false|none||待确认建议数（已接受待处理）（导出：待确认干预）|
|pendingOptimizeCount|integer(int64)|false|none||待优化建议数（已处理待优化）（导出：待优化风险）|

<h2 id="tocS_MapString">MapString</h2>

<a id="schemamapstring"></a>
<a id="schema_MapString"></a>
<a id="tocSmapstring"></a>
<a id="tocsmapstring"></a>

```json
{
  "key": "string"
}

```

### 属性

|名称|类型|必选|约束|中文名|说明|
|---|---|---|---|---|---|
|key|string|false|none||none|

<h2 id="tocS_AbsBusProfileVO">AbsBusProfileVO</h2>

<a id="schemaabsbusprofilevo"></a>
<a id="schema_AbsBusProfileVO"></a>
<a id="tocSabsbusprofilevo"></a>
<a id="tocsabsbusprofilevo"></a>

```json
{
  "main": {
    "id": "string",
    "ppartition": "string",
    "busId": "string",
    "busName": "string",
    "organId": "string",
    "organName": "string",
    "calculateDate": "string",
    "evalutaionType": "string",
    "score": 0,
    "suggestedContent": "string",
    "creator": "string",
    "createTime": "string",
    "updater": "string",
    "updateTime": "string",
    "deleted": "string",
    "manager": "string",
    "routeName": "string",
    "numberPlate": "string",
    "ranking": 0,
    "pendingReceiveCount": 0,
    "pendingConfirmCount": 0,
    "pendingOptimizeCount": 0
  },
  "quotaScoreSubList": [
    {
      "id": "string",
      "ppartition": "string",
      "mainId": "string",
      "quotaId": "string",
      "quotaName": "string",
      "score": 0,
      "weightRate": 0,
      "originalValue": 0,
      "riskData": "string",
      "quotaLevel": "string",
      "parentId": "string",
      "creator": "string",
      "createTime": "string",
      "updater": "string",
      "updateTime": "string",
      "deleted": "string",
      "ranking": 0,
      "firstQuotaName": "string",
      "busId": "string",
      "numberPlate": "string"
    }
  ]
}

```

### 属性

|名称|类型|必选|约束|中文名|说明|
|---|---|---|---|---|---|
|main|[AbsBusProfileMain](#schemaabsbusprofilemain)|false|none||车辆画像主数据|
|quotaScoreSubList|[[AbsBusQuotaScoreSub](#schemaabsbusquotascoresub)]|false|none||车辆画像指标数据列表|

<h2 id="tocS_McpresultListOdsJituanBsRoute">McpresultListOdsJituanBsRoute</h2>

<a id="schemamcpresultlistodsjituanbsroute"></a>
<a id="schema_McpresultListOdsJituanBsRoute"></a>
<a id="tocSmcpresultlistodsjituanbsroute"></a>
<a id="tocsmcpresultlistodsjituanbsroute"></a>

```json
{
  "path": "string",
  "pathArgs": {
    "key": "string"
  },
  "success": true,
  "message": "string",
  "code": 0,
  "result": [
    {
      "routeId": "string",
      "routeCode": "string",
      "intelligenceCode": "string",
      "routeName": "string",
      "intelligenceName": "string",
      "mileage": 0,
      "startToEndSite": "string",
      "direction": "string",
      "organId": "string",
      "motorcadeId": 0,
      "motorcadeCode": "string",
      "motorcadeName": "string",
      "mileageUp": 0,
      "mileageDown": 0,
      "routeType": "string",
      "upFirstTime": "string",
      "upLatestTime": "string",
      "downFirstTime": "string",
      "downLatestTime": "string",
      "linePlateOrg": "string",
      "plateTypeOrg": "string",
      "lineNatureOrg": "string",
      "lineTypeOrg": "string",
      "remark": "string",
      "userTag1": "string",
      "userTag2": "string",
      "upFirstStationId": "string",
      "upLastStationId": "string",
      "downFirstStationId": "string",
      "downLastStationId": "string",
      "organName": "string",
      "routeProfileMain": {
        "id": "string",
        "ppartition": "string",
        "routeId": "string",
        "routeName": "string",
        "organId": "string",
        "organName": "string",
        "calculateDate": "string",
        "evalutaionType": "string",
        "score": 0,
        "suggestedContent": "string",
        "creator": "string",
        "createTime": "string",
        "updater": "string",
        "updateTime": "string",
        "deleted": "string",
        "manager": "string",
        "ranking": 0,
        "pendingReceiveCount": 0,
        "pendingConfirmCount": 0,
        "pendingOptimizeCount": 0
      },
      "busCount": 0,
      "driverCount": 0
    }
  ],
  "timestamp": 0
}

```

### 属性

|名称|类型|必选|约束|中文名|说明|
|---|---|---|---|---|---|
|path|string|false|none||引用源路径|
|pathArgs|[MapString](#schemamapstring)|false|none||引用源消息参数|
|success|boolean|false|none||接口响应状态（true是成功，false是失败）|
|message|string|false|none||接口响应消息|
|code|integer|false|none||接口响应状态码|
|result|[[OdsJituanBsRoute](#schemaodsjituanbsroute)]|false|none||返回的数据对象|
|timestamp|integer(int64)|false|none||响应时间戳|

<h2 id="tocS_McpresultListOdsJituanBsBus">McpresultListOdsJituanBsBus</h2>

<a id="schemamcpresultlistodsjituanbsbus"></a>
<a id="schema_McpresultListOdsJituanBsBus"></a>
<a id="tocSmcpresultlistodsjituanbsbus"></a>
<a id="tocsmcpresultlistodsjituanbsbus"></a>

```json
{
  "path": "string",
  "pathArgs": {
    "key": "string"
  },
  "success": true,
  "message": "string",
  "code": 0,
  "result": [
    {
      "busId": "string",
      "busCode": "string",
      "numberPlate": "string",
      "obuid": "string",
      "frameNo": "string",
      "routeId": "string",
      "orgName": "string",
      "organId": "string",
      "orgCode": "string",
      "busType": "string",
      "busAge": 0,
      "vehicleType": "string",
      "useNature": "string",
      "busFactory": "string",
      "carryPersonNumber": 0,
      "busLength": 0,
      "busLengthM": 0,
      "busColor": "string",
      "fuelType": "string",
      "emiStandard": "string",
      "batteryCapacity": "string",
      "planPurchaseDate": "string",
      "isAir": "string",
      "engineNo": "string",
      "engineType": "string",
      "engineFactory": "string",
      "hybridBusPowerFactory": "string",
      "powerBatteryFactory": "string",
      "drivingRange": 0,
      "batteryManufacturer": "string",
      "batteryVoltage": "string",
      "userTag1": "string",
      "userTag2": "string",
      "motorcadeId": 0,
      "motorcadeCode": "string",
      "routeName": "string",
      "motorcadeName": "string",
      "busProfileMain": {
        "id": "string",
        "ppartition": "string",
        "busId": "string",
        "busName": "string",
        "organId": "string",
        "organName": "string",
        "calculateDate": "string",
        "evalutaionType": "string",
        "score": 0,
        "suggestedContent": "string",
        "creator": "string",
        "createTime": "string",
        "updater": "string",
        "updateTime": "string",
        "deleted": "string",
        "manager": "string",
        "routeName": "string",
        "numberPlate": "string",
        "ranking": 0,
        "pendingReceiveCount": 0,
        "pendingConfirmCount": 0,
        "pendingOptimizeCount": 0
      }
    }
  ],
  "timestamp": 0
}

```

### 属性

|名称|类型|必选|约束|中文名|说明|
|---|---|---|---|---|---|
|path|string|false|none||引用源路径|
|pathArgs|[MapString](#schemamapstring)|false|none||引用源消息参数|
|success|boolean|false|none||接口响应状态（true是成功，false是失败）|
|message|string|false|none||接口响应消息|
|code|integer|false|none||接口响应状态码|
|result|[[OdsJituanBsBus](#schemaodsjituanbsbus)]|false|none||返回的数据对象|
|timestamp|integer(int64)|false|none||响应时间戳|

<h2 id="tocS_McpresultAbsBusProfileVO">McpresultAbsBusProfileVO</h2>

<a id="schemamcpresultabsbusprofilevo"></a>
<a id="schema_McpresultAbsBusProfileVO"></a>
<a id="tocSmcpresultabsbusprofilevo"></a>
<a id="tocsmcpresultabsbusprofilevo"></a>

```json
{
  "path": "string",
  "pathArgs": {
    "key": "string"
  },
  "success": true,
  "message": "string",
  "code": 0,
  "result": {
    "main": {
      "id": "string",
      "ppartition": "string",
      "busId": "string",
      "busName": "string",
      "organId": "string",
      "organName": "string",
      "calculateDate": "string",
      "evalutaionType": "string",
      "score": 0,
      "suggestedContent": "string",
      "creator": "string",
      "createTime": "string",
      "updater": "string",
      "updateTime": "string",
      "deleted": "string",
      "manager": "string",
      "routeName": "string",
      "numberPlate": "string",
      "ranking": 0,
      "pendingReceiveCount": 0,
      "pendingConfirmCount": 0,
      "pendingOptimizeCount": 0
    },
    "quotaScoreSubList": [
      {
        "id": "string",
        "ppartition": "string",
        "mainId": "string",
        "quotaId": "string",
        "quotaName": "string",
        "score": 0,
        "weightRate": 0,
        "originalValue": 0,
        "riskData": "string",
        "quotaLevel": "string",
        "parentId": "string",
        "creator": "string",
        "createTime": "string",
        "updater": "string",
        "updateTime": "string",
        "deleted": "string",
        "ranking": 0,
        "firstQuotaName": "string",
        "busId": "string",
        "numberPlate": "string"
      }
    ]
  },
  "timestamp": 0
}

```

### 属性

|名称|类型|必选|约束|中文名|说明|
|---|---|---|---|---|---|
|path|string|false|none||引用源路径|
|pathArgs|[MapString](#schemamapstring)|false|none||引用源消息参数|
|success|boolean|false|none||接口响应状态（true是成功，false是失败）|
|message|string|false|none||接口响应消息|
|code|integer|false|none||接口响应状态码|
|result|[AbsBusProfileVO](#schemaabsbusprofilevo)|false|none||返回的数据对象|
|timestamp|integer(int64)|false|none||响应时间戳|

<h2 id="tocS_AbsBusQuotaScoreSub">AbsBusQuotaScoreSub</h2>

<a id="schemaabsbusquotascoresub"></a>
<a id="schema_AbsBusQuotaScoreSub"></a>
<a id="tocSabsbusquotascoresub"></a>
<a id="tocsabsbusquotascoresub"></a>

```json
{
  "id": "string",
  "ppartition": "string",
  "mainId": "string",
  "quotaId": "string",
  "quotaName": "string",
  "score": 0,
  "weightRate": 0,
  "originalValue": 0,
  "riskData": "string",
  "quotaLevel": "string",
  "parentId": "string",
  "creator": "string",
  "createTime": "string",
  "updater": "string",
  "updateTime": "string",
  "deleted": "string",
  "ranking": 0,
  "firstQuotaName": "string",
  "busId": "string",
  "numberPlate": "string"
}

```

### 属性

|名称|类型|必选|约束|中文名|说明|
|---|---|---|---|---|---|
|id|string|false|none||主键|
|ppartition|string|false|none||分区字段(yyyymmdd)|
|mainId|string|false|none||车辆画像主表主键|
|quotaId|string|false|none||指标ID|
|quotaName|string|false|none||指标名称|
|score|number|false|none||指标值|
|weightRate|number|false|none||计算权重|
|originalValue|number|false|none||原始值|
|riskData|string|false|none||风险数据值|
|quotaLevel|string|false|none||指标等级 1-一级指标 2-二级指标 3-三级指标|
|parentId|string|false|none||父级指标ID|
|creator|string|false|none||创建人|
|createTime|string|false|none||创建日期|
|updater|string|false|none||更改人|
|updateTime|string|false|none||更改时间|
|deleted|string|false|none||是否删除|
|ranking|integer|false|none||排名|
|firstQuotaName|string|false|none||一级指标（从quotaId解析，列表展示，非表字段）|
|busId|string|false|none||车辆ID（导出：自编号）|
|numberPlate|string|false|none||车牌号（导出：车牌号）|

