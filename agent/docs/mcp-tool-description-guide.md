# MCP Tool Schema 与 Description 编写规范

## 1. 核心结论

MCP 官方将 Tool 定义为 **schema-defined interface**。一个工具通常包含 `name`、`description`、`inputSchema`。

职责分工：

- `inputSchema` 负责结构化约束：`type`、`required`、`enum`、`format`、`pattern`
- `description` 负责自然语言解释：工具用途、字段含义、参数来源、不传时行为、替代工具

不要再写“字段格式、枚举值、必填声明必须写在 tool description 里”。

这些内容应该分别写在：

- 字段格式：标准格式写 `type` + `format`，自定义字符串规则写 `type` + `pattern`，再在字段 `description` 里补示例
- 枚举值约束：写在 `enum`
- 枚举值含义：写在字段 `description`
- 必填声明：写在 `inputSchema.required`
- 参数来源、字段区别、默认行为、调用前提：写在字段或工具 `description`

正确说法是：

- 结构化约束写在 `inputSchema`
- 语义解释和使用前提写在 `description`
- 字段级约束不要塞进工具级 `description` 里替代 schema
- 工具级 `description` 说明“这个工具做什么、何时不用它”
- 字段级 `description` 说明“这个参数是什么意思、该怎么理解”
- 只写 schema 不够，只有 `type` / `required` / `enum` 仍然可能无法消除业务歧义
- 只写 description 也不够，缺少结构化约束会让模型和系统都无法稳定校验参数

---

## 2. 为什么官方示例很简单

官方示例的目标是说明协议结构，不是给业务系统提供生产级写法。例如：

```json
{
  "name": "searchFlights",
  "description": "Search for available flights",
  "inputSchema": {
    "type": "object",
    "properties": {
      "origin": { "type": "string", "description": "Departure city" },
      "destination": { "type": "string", "description": "Arrival city" },
      "date": { "type": "string", "format": "date", "description": "Travel date" }
    },
    "required": ["origin", "destination", "date"]
  }
}
```

它能写得很短，是因为 `origin` / `destination` / `date` 几乎没有业务歧义，`format: "date"` 也足够表达核心约束。

你们的工具不是这个难度。像 `id`、`busId`、`busCode`、`numberPlate` 这种字段，即使 schema 合法，Agent 也可能不知道该填哪个值，所以必须补业务语义。

---

## 3. Agent 实际依赖什么

在决定“要不要调用工具、调用哪个、传什么参数”时，Agent 主要读取 `name`、`description`、`inputSchema`。

因此有两类错误都要避免：

- 只写 schema，不补语义
- 只写 description，不写结构化约束

---

## 4. 一个真实例子

用户说：“帮我查一下粤B88888这辆车的电池容量。”

坏的写法：

```json
{
  "name": "get_base_odsJituanBsBus_queryById",
  "description": "集团车辆-通过id查询",
  "inputSchema": {
    "type": "object",
    "properties": {
      "id": { "type": "string", "description": "车辆ID" }
    },
    "required": ["id"]
  }
}
```

问题在于：`id` 是 `busId` 还是车牌号，Agent 不知道；用户给了 `粤B88888`，模型可能直接把它当 `id` 传入。

好的写法：

```json
{
  "name": "get_base_odsJituanBsBus_queryById",
  "description": "按内部ID查询单辆车完整信息。id 是系统内部 busId，不是车牌号；如果只有车牌号，先用 get_base_odsJituanBsBus_list 按 numberPlate 过滤拿到 busId。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "id": {
        "type": "string",
        "description": "车辆内部ID，从列表接口返回的 busId 字段获取。"
      }
    },
    "required": ["id"]
  }
}
```

这里 `required` 解决“必填”，`type` 解决“类型”，`description` 解决“这个 id 到底是什么、从哪里来”。

---

## 5. 通用规则

### 规则一：工具描述写工具用途和边界

坏的写法：

```json
{
  "name": "put_base_odsJituanBsBus_edit",
  "description": "集团车辆-编辑 - 集团车辆-编辑"
}
```

好的写法：

```json
{
  "name": "put_base_odsJituanBsBus_edit",
  "description": "编辑集团车辆信息。更新前需要先拿到 busId；查询车辆详情请用 get_base_odsJituanBsBus_queryById。"
}
```

### 规则二：固定取值必须用 `enum`

```json
"isAir": {
  "type": "string",
  "enum": ["0", "1"],
  "description": "是否配备空调。\"1\" 表示有空调，\"0\" 表示无空调。"
}
```

`enum` 表达约束，`description` 解释值含义。

### 规则三：标准格式用 `format`，自定义格式用 `pattern`

```json
"planPurchaseDate": {
  "type": "string",
  "format": "date",
  "description": "计划购买日期，使用 YYYY-MM-DD，例如 \"2024-03-15\"。"
}
```

```json
"customDate": {
  "type": "string",
  "pattern": "^(0[1-9]|[12][0-9]|3[01])(0[1-9]|1[0-2])[0-9]{4}$",
  "description": "日期，格式 DDMMYYYY，例如 \"24032026\"。"
}
```

能结构化表达的先结构化表达；示例和补充说明写在 `description`。

### 规则四：必填字段必须写在 `required`

```json
{
  "inputSchema": {
    "type": "object",
    "properties": {
      "busId": {
        "type": "string",
        "description": "车辆内部ID，从列表或 queryById 接口返回的 busId 字段获取。"
      },
      "busCode": {
        "type": "string",
        "description": "车辆编码，仅在需要修改时传入。"
      }
    },
    "required": ["busId"]
  }
}
```

### 规则五：字段描述不要只翻译字段名

坏的写法：

```json
"id": { "type": "string", "description": "车辆ID" }
```

好的写法：

```json
"id": {
  "type": "string",
  "description": "车辆内部ID，即 busId，不是车牌号，也不是车辆编码。"
}
```

字段描述优先补这几类信息：业务含义、与相近字段的区别、参数来源、不传时行为、示例值。

---

## 6. 常见错误

| 错误 | 示例 | 影响 |
|------|------|------|
| 工具描述重复工具名 | `"集团车辆-编辑 - 集团车辆-编辑"` | Agent 不知道何时用 |
| 参数描述只翻译字段名 | `"是否空调"` | Agent 不知道该传什么 |
| 写操作缺少 `required` | `put_edit` 未声明必填 | Agent 可能漏传 `busId` |
| 日期未写 `format` 或示例 | `"计划购买日期"` | Agent 可能传错格式 |

---

## 7. 发布前检查清单

1. 工具级 `description` 是否说明了用途和边界
2. 每个参数是否都有明确的 `type`
3. 固定取值是否写了 `enum`
4. 必填参数是否写进了 `required`
5. 标准格式是否写了 `format`，自定义字符串格式是否写了 `pattern`
6. 字段级 `description` 是否补了业务含义、来源、默认行为或示例
7. 是否避免了“只重复工具名”或“只翻译字段名”
