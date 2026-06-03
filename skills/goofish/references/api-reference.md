# 闲管家 Open Platform API Reference

Base URL: `https://open.goofish.pro`

All endpoints use POST with query parameters (`appid`, `timestamp`, `sign`, and optionally `seller_id`) plus a JSON request body.

## Authentication

Every request requires:
- `appid` (query) — AppKey from the open platform
- `timestamp` (query) — Unix timestamp in seconds, valid within 5 minutes
- `sign` (query) — MD5 signature
- `seller_id` (query, optional) — Only for business partner integrations

### Signature Algorithm

```
body_md5 = md5(JSON_body_string)   # use md5("{}") or md5("") for empty body
sign = md5(f"{app_key},{body_md5},{timestamp},{app_secret}")
```

For business partner integrations:
```
sign = md5(f"{app_key},{body_md5},{timestamp},{seller_id},{app_secret}")
```

---

## Response Format

All APIs return:

```json
{
  "code": 0,    // 0 = success, non-zero = error
  "msg": "OK",  // message
  "data": {}    // response data
}
```

---

## 1. 用户 (User)

### POST /api/open/user/authorize/list — 查询闲鱼店铺

Query authorized Xianyu stores.

**Query Parameters:** `appid` (required), `timestamp`, `sign` (required), `seller_id` (optional)

**Response Data:**
```
list[{
  authorize_id: int       // 授权ID
  authorize_expires: int  // 授权过期时间
  user_identity: string   // 闲鱼号唯一标识
  user_name: string       // 闲鱼会员名
  user_nick: string       // 闲鱼号昵称
  shop_name: string       // 店铺名称
  service_support: string // 已开通的服务项 (e.g., "SDR,NFR")
  is_deposit_enough: bool // 是否已缴纳足够的服务保证金
  is_pro: bool            // 是否开通鱼小铺
  is_valid: bool          // 是否有效订购中
  is_trial: bool          // 是否免费试用版本
  valid_end_time: int     // 订购有效结束时间
  item_biz_types: string  // 准入业务类型 (e.g., "2,10,19")
}]
```

---

## 2. 商品 (Product)

### POST /api/open/product/category/list — 查询商品类目

Query product categories by type and industry.

**Query Parameters:** `appid` (required), `timestamp`, `sign` (required), `seller_id` (optional)

**Request Body:**
```json
{
  "item_biz_type": 2,   // required: 商品类型
  "sp_biz_type": 2,     // 行业类型
  "flash_sale_type": 1  // 闲鱼特卖类型 (optional)
}
```

**Response:**
```
list[{
  sp_biz_type: {}       // 行业类型
  sp_biz_name: string   // 行业名称
  channel_cat_id: string  // 渠道类目ID
  channel_cat_name: string // 渠道类目名称
}]
```

### POST /api/open/product/pv/list — 查询商品属性

Query product attributes/properties for a given category.

**Query Parameters:** `appid` (required), `timestamp`, `sign` (required), `seller_id` (optional)

**Request Body:**
```json
{
  "item_biz_type": 2,
  "sp_biz_type": 1,
  "channel_cat_id": "4d8b31d719602249ac899d2620c5df2b",
  "sub_property_id": ""  // optional: 属性值ID for cascaded queries
}
```

**Response:**
```
list[{
  property_id: string      // 属性ID
  property_name: string    // 属性名称
  required: int            // 是否必选 (0/1)
  items[{
    value_id: string       // 属性值ID
    value_name: string     // 属性值名称
    sub_property_id: string // 下级属性ID (非空表示需二次查询)
  }]
}]
```

### POST /api/open/product/list — 查询商品列表

Query product list with filters. Only returns products modified in the last 6 months.

**Query Parameters:** `appid` (required), `timestamp`, `sign` (required), `seller_id` (optional)

**Request Body:**
```json
{
  "product_status": 21,     // 商品状态 (see enums below)
  "sale_status": 2,         // 销售状态: 1=待发布 2=销售中 3=已下架
  "update_time": [1690300800, 1690366883],  // time range [start, end]
  "create_time": [1690300800, 1690366883],
  "online_time": [1690300800, 1690366883],
  "offline_time": [1690300800, 1690366883],
  "sold_time": [1690300800, 1690366883],
  "page_no": 1,
  "page_size": 50           // max 100
}
```

**Response:**
```
{
  list[{
    product_id: int       // 管家商品ID
    product_status: int   // 商品状态
    item_biz_type: int    // 商品类型
    sp_biz_type: int      // 行业类型
    channel_cat_id: string
    original_price: int   // 原价(分)
    price: int            // 售价(分)
    stock: int            // 库存
    sold: int             // 销量
    title: string         // 标题 (max 30 chars)
    district_id: int      // 发货地区ID
    outer_id: string      // 商家编码
    stuff_status: int     // 成色
    express_fee: int      // 运费(分)
    spec_type: int        // 规格类型: 1=单规格 2=多规格
    source: int           // 来源: 11=新建 12=闲鱼APP 21=淘宝搬家 91=ERP
    specify_publish_time: int
    online_time: int
    offline_time: int
    sold_time: int
    update_time: int
    create_time: int
  }],
  count: int,
  page_no: int,
  page_size: int
}
```

Note: `page_no * page_size` must not exceed 10,000.

### POST /api/open/product/detail — 查询商品详情

Get full product details.

**Request Body:** `{"product_id": 220656347074629}`

**Response includes:** All product fields, publish_shop (with images, title, description, location), sku_items, book_data, food_data, report_data, detail_images, sku_images, brand_data, advent_data, ship_region_data, is_tax_included, plus timestamps.

### POST /api/open/product/sku/list — 查询商品规格

Query SKU info for multi-spec products (only works for multi-spec products).

**Request Body:**
```json
{
  "product_id": [537044127563781, 536768661209157]  // max 100
}
```

**Response:**
```
list[{
  product_id: int
  sku_items[{
    sku_id: int       // 管家SKU规格ID
    price: int        // SKU售价(分)
    stock: int        // SKU库存 (max 9999)
    sku_text: string  // e.g., "颜色:黑色;内存:512G"
    outer_id: string  // SKU商家编码
    xy_sku_id: int    // 闲鱼SKUID
  }]
}]
```

### POST /api/open/product/create — 创建商品（单个）

Create a single product.

**Required fields:** `item_biz_type`, `sp_biz_type`, `channel_cat_id`, `price`, `express_fee`, `stock`, `publish_shop`

**publish_shop array** (at least one item):
```json
[{
  "user_name": "tb924343042",     // 闲鱼会员名
  "province": 130000,             // 发货省份
  "city": 130100,                 // 发货城市
  "district": 130101,             // 发货地区
  "title": "商品标题",             // max 60 chars (Chinese = 2 chars)
  "content": "商品描述。",         // min 5, max 5000 chars
  "images": ["https://xxx.com/xxx1.jpg"],  // first image = main image
  "white_images": "https://xxx.com/xxx1.jpg",  // optional
  "service_support": "SDR"       // optional, comma-separated
}]
```

**Optional fields:** `channel_pv`, `original_price`, `outer_id`, `stuff_status`, `sku_items`, `book_data`, `food_data`, `report_data`, `flash_sale_type`, `advent_data`, `inspect_data`, `brand_data`, `detail_images`, `sku_images`, `ship_region_data`, `is_tax_included`

Note: `item_biz_type`, `sp_biz_type`, `channel_cat_id` have dependency relationships — query categories first.

### POST /api/open/product/batchCreate — 创建商品（批量）

Batch create up to 50 products.

**Request Body:**
```json
{
  "product_data": [{
    "item_key": "product-1",  // unique per batch, returned as-is for matching
    // ... same fields as single create
  }]
}
```

### POST /api/open/product/publish — 上架商品

Publish a product to Xianyu App. **Async** — result delivered via callback.

**Request Body:**
```json
{
  "product_id": 220656347074629,
  "user_name": ["tb924343042"],    // which store to publish to
  "specify_publish_time": "2023-07-21 00:00:00",  // optional: scheduled publish
  "notify_url": "https://your-server.com/callback" // optional: callback URL
}
```

### POST /api/open/product/downShelf — 下架商品

Unpublish a product.

**Request Body:** `{"product_id": 220656347074629}`

### POST /api/open/product/edit — 编辑商品

Edit product fields. Partial update — only send fields you want to change.

**Special notes:**
- If product is published (销售中), updates sync to Xianyu App **async** with callback
- If not published, no callback even if `notify_url` is set
- Multi-spec products: cannot clear all SKUs if already published

**Request Body:** `product_id` + any fields you want to update (same structure as create).

### POST /api/open/product/edit/stock — 编辑库存

Update stock and price.

**Request Body:**
```json
{
  "product_id": 441870024105922,
  "price": 199900,        // optional: 售价(分)
  "original_price": 299900, // optional: 原价(分)
  "stock": 10,            // 单规格库存 (single-spec only)
  "sku_items": [{         // 多规格库存 (multi-spec only)
    "sku_id": 441870024105926,
    "price": 199900,
    "stock": 5
  }]
}
```

If product is published, stock updates sync to Xianyu App immediately.

### POST /api/open/product/delete — 删除商品

Delete a product. Only works on draft (草稿箱) or pending (待发布) products.

**Request Body:** `{"product_id": 220656347074629}`

Note: Does NOT delete products already published on Xianyu App — those must be deleted manually in the app.

---

## 3. 订单 (Order)

### POST /api/open/order/list — 查询订单列表

Query orders. Total accessible via pagination: 10,000 records.

**Query Parameters:** `appid` (required), `timestamp`, `sign` (required), `seller_id` (optional)

**Request Body:**
```json
{
  "authorize_id": 2670420985643008,  // optional: 店铺授权ID
  "order_status": 22,                // optional: 订单状态
  "refund_status": 0,                // optional: 退款状态
  "order_time": [1685087039, 1685951386],  // deprecated
  "pay_time": [1685087039, 1685951386],
  "consign_time": [1685087039, 1685951386],
  "confirm_time": [1685087039, 1685951386],
  "refund_time": [1685087039, 1685951386],
  "update_time": [1685087039, 1685951386],  // must be within 6 months
  "page_no": 1,
  "page_size": 50
}
```

**Response (list items):**
```
{
  order_no: string        // 闲鱼订单号 (19+ digits)
  order_status: int       // 订单状态
  order_time: int         // 买家下单时间
  total_amount: int       // 下单金额(分)
  pay_amount: int         // 实付金额(分)
  pay_no: string          // 支付宝交易号
  pay_time: int           // 支付时间
  refund_status: int      // 退款状态
  refund_time: int        // 退款时间
  receiver_mobile: string // 收货人号码 (only pending ship)
  receiver_name: string   // 收货人姓名 (only pending ship)
  prov_name: string       // 收货省份
  city_name: string       // 收货城市
  area_name: string       // 收货地区
  town_name: string       // 收货街道
  address: string         // 收货详情地址
  waybill_no: string      // 快递单号
  express_code: string    // 快递公司代码
  express_name: string    // 快递公司名称
  express_fee: int        // 运费(分)
  consign_type: int       // 发货类型: 1=物流 2=虚拟
  consign_time: int       // 发货时间
  confirm_time: int       // 确认收货时间
  cancel_reason: string   // 取消原因
}
```

### POST /api/open/order/detail — 查询订单详情

Get detailed order info.

**Request Body:** `{"order_no": "2226688164543566229"}`

Response includes all order fields plus buyer message, order items, and extended info.

### POST /api/open/order/kam/list — 订单卡密列表

Query virtual goods card/key info for an order.

**Request Body:** `{"order_no": "2226688164543566300"}`

**Response:**
```
list[{
  card_no: string    // 卡密账号
  card_pwd: string   // 卡密密码
  cost: int          // 成本单价(分)
  sold_type: int     // 销售类型
}]
```

### POST /api/open/order/ship — 订单物流发货

Ship an order with logistics info.

**Required fields:** `order_no`, `waybill_no`, `express_code`, `express_name`

**Request Body:**
```json
{
  "order_no": "1339920336328048683",
  "ship_name": "张三",            // sender name
  "ship_mobile": "13800138000",  // sender phone
  "ship_district_id": 440305,    // sender district ID
  "ship_prov_name": "广东省",    // or use district_id
  "ship_city_name": "深圳市",
  "ship_area_name": "南山区",
  "ship_address": "侨香路西丽街道丰泽园仓储中心",
  "waybill_no": "25051016899982",
  "express_code": "shunfeng",
  "express_name": "顺丰速运"     // when express_code="other", use actual name
}
```

Sender info can be provided via 3 methods:
1. `ship_name` + `ship_mobile` + `ship_district_id` + `ship_address`
2. `ship_name` + `ship_mobile` + `ship_prov_name` + `ship_city_name` + `ship_area_name` + `ship_address`
3. None — uses default shipping address configured in Goofish dashboard

### POST /api/open/order/modify/price — 订单修改价格

Modify order price.

**Request Body:**
```json
{
  "order_no": "2226688164543566229",
  "order_price": 10000,   // 订单价格(分), min 1
  "express_fee": 0        // 运费(分), 0 = free shipping
}
```

---

## 4. 推送 (Push/Webhook)

These are inbound notifications sent by Goofish to your server. Configure the callback URL in the Goofish developer console.

### 商品回调通知

Sent when product publish/edit operations complete (async).

### 商品推送通知

Real-time product status change notifications. Configure in Goofish console.

### 订单推送通知

Real-time order status change notifications. Configure in Goofish console.

---

## 5. 其他 (Other)

### POST /api/open/express/companies — 查询快递公司

Query available express companies. If a needed company is missing, contact Goofish support.

**Query Parameters:** `appid` (required), `timestamp`, `sign` (required)

**Response:**
```
list[{
  code: string           // 快递公司代码
  express_name: string   // 快递公司名称
  express_alias: string  // 快递公司简称
  is_hot: bool           // 是否热门
}]
```

---

## Enum Reference

### 商品类型 (item_biz_type)
| Value | Description |
|-------|-------------|
| 2 | 普通商品 |
| 0 | 已验货 |
| 10 | 验货宝 |
| 16 | 品牌授权 |
| 19 | 闲鱼严选 |
| 24 | 闲鱼特卖 |
| 26 | 品牌捡漏 |
| 35 | 跨境商品 |

### 行业类型 (sp_biz_type)
| Value | Description |
|-------|-------------|
| 1 | 手机 |
| 2 | 潮品 |
| 3 | 家电 |
| 8 | 乐器 |
| 9 | 3C数码 |
| 16 | 奢品 |
| 17 | 母婴 |
| 18 | 美妆个护 |
| 19 | 文玩/珠宝 |
| 20 | 游戏电玩 |
| 21 | 家居 |
| 22 | 虚拟游戏 |
| 23 | 租号 |
| 24 | 图书 |
| 25 | 卡券 |
| 27 | 食品 |
| 28 | 潮玩 |
| 29 | 二手车 |
| 30 | 宠植 |
| 31 | 工艺礼品 |
| 33 | 汽车服务 |
| 99 | 其他 |

### 商品状态 (product_status)
| Value | Description |
|-------|-------------|
| -1 | 已删除 |
| 21 | 待发布 |
| 22 | 销售中 |
| 23 | 已售罄 |
| 31 | 手动下架 |
| 33 | 售出下架 |
| 36 | 自动下架 |

### 发布状态 (publish_status)
| Value | Description | Actions |
|-------|-------------|---------|
| -1 | 不可操作 | — |
| 1 | 草稿箱 | 编辑/删除 |
| 2 | 待发布 | 上架/编辑/删除 |
| 3 | 销售中 | 下架/编辑 |
| 4 | 已下架 | 上架/编辑/删除 |
| 5 | 已售罄 | 上架/编辑/删除 |
| 9 | 商品异常 | 编辑/删除 |

### 商品成色 (stuff_status)
| Value | Description |
|-------|-------------|
| 0 | 无成色 (普通商品) |
| 100 | 全新 |
| -1 | 准新 |
| 99 | 99新 |
| 95 | 95新 |
| 90 | 9新 |
| 80 | 8新 |
| 70 | 7新 |
| 60 | 6新 |
| 50 | 5新及以下 |

品牌捡漏专用: 40=未使用·中度瑕疵, 30=未使用·轻微瑕疵, 20=未使用·仅拆封, 10=未使用·准新, 100=全新未使用

### 订单状态 (order_status)
Refer to the Goofish platform for the full order status enum.

### 退款状态 (refund_status)
Refer to the Goofish platform for the full refund status enum.

### 商品来源 (source)
| Value | Description |
|-------|-------------|
| 11 | 新建商品 |
| 12 | 闲鱼APP |
| 21 | 淘宝搬家 |
| 91 | ERP |

### 规格类型 (spec_type)
| Value | Description |
|-------|-------------|
| 1 | 单规格 |
| 2 | 多规格 |

### 发货类型 (consign_type)
| Value | Description |
|-------|-------------|
| 1 | 物流发货 |
| 2 | 虚拟发货 |

### 商品服务 (service_support)
Multiple values comma-separated (e.g., "SDR,NFR"):
| Code | Description |
|------|-------------|
| SDR | 七天无理由退货 |
| NFR | 描述不符包邮退 |
| VNR | 描述不符全额退（虚拟类） |
| FD_10MS | 10分钟极速发货（虚拟类） |
| FD_24HS | 24小时极速发货 |
| FD_48HS | 48小时极速发货 |
| FD_GPA | 正品保障（包赔） |
| NFGC | 不符必赔 |
| RISK_30D | 30天收货 |
| RISK_90D | 90天收货 |

### 闲鱼特卖类型 (flash_sale_type)
| Value | Description | Scope |
|-------|-------------|-------|
| 1 | 临期 | 闲鱼特卖 |
| 2 | 孤品 | 闲鱼特卖 |
| 3 | 断码 | 闲鱼特卖 |
| 4 | 微瑕 | 闲鱼特卖 |
| 5 | 尾货 | 闲鱼特卖 |
| 6 | 官翻 | 闲鱼特卖 |
| 7 | 全新 | 闲鱼特卖 |
| 8 | 福袋 | 闲鱼特卖 |
| 99 | 其他 | 闲鱼特卖 |
| 2601 | 微瑕 | 品牌捡漏 |
| 2602 | 临期 | 品牌捡漏 |
| 2603 | 清仓 | 品牌捡漏 |
| 2604 | 官翻 | 品牌捡漏 |
