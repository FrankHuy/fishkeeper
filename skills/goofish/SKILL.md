---
name: goofish
description: Use when working with the 闲管家 (Goofish/Xianyu) Open Platform API. Manage Xianyu (闲鱼) store products, orders, inventory, and shipping. Covers full product lifecycle (create, read, update, delete, publish, unpublish), order management (list, detail, ship, modify price), category/attribute queries, and store info.
version: 1.0.0
author: fishkeeper
license: MIT
metadata:
  hermes:
    tags: [goofish, xianyu, xianyu-open-platform, ecommerce, erp, 闲鱼, 闲管家]
    related_skills: []
---

# 闲管家 (Goofish) Open Platform

## Overview

闲管家开放平台 (Goofish Open Platform) is the official API for managing Xianyu (闲鱼) stores programmatically. It provides full product lifecycle management, order processing, and store information queries.

> **命名说明：** 项目名 **fishkeeper**（闲鱼+管家=fish+keeper）是本工具的品牌名，skill 名 **goofish** 对应闲管家开放平台的官方英文名，用于 agent 关键词匹配。

**Base URL:** `https://open.goofish.pro`

**Auth Method:** MD5 signature with AppKey + request body MD5 + timestamp + AppSecret. All requests use POST with query parameters and JSON body.

The skill includes:
- A Python client library (`scripts/client.py`) for all API operations
- A signer utility (`scripts/signer.py`) for request authentication
- A multi-agent orchestrator (`scripts/orchestrator.py`) for parallel task execution
- Detailed API reference (`references/api-reference.md`)
- Multi-agent orchestration patterns (`references/multi-agent-patterns.md`)
- A configuration template (`config.example.yaml`)

## When to Use

- Managing Xianyu product listings (create, edit, publish, unpublish, delete)
- Syncing inventory across ERP and Xianyu
- Processing orders (query, ship, modify price)
- Building automation workflows for Xianyu store operations
- Querying store info, product categories, attributes, and specs
- Bulk product operations (up to 50 per batch)
- Looking up express companies for shipping
- Retrieving virtual goods order key/password info

Do NOT use for:
- Receiving real-time push notifications (requires a separate webhook server)
- Refund/cancellation processing (not supported by the API)
- Buyer messaging or chat (not supported)
- Store settings or advertising management (not supported)

## Configuration

Copy `config.example.yaml` to a secure location and fill in credentials:

```yaml
goofish:
  app_key: ""        # 开放平台的AppKey
  app_secret: ""     # 开放平台的AppSecret
  base_url: "https://open.goofish.pro"
```

**Config file location priority:**
1. `GOOFISH_CONFIG` environment variable pointing to a YAML file
2. `./goofish.yaml` in the current working directory
3. `~/.goofish/config.yaml`

The `GOOFISH_APP_KEY` and `GOOFISH_APP_SECRET` environment variables override the config file values.

## API Categories

| Category | APIs | Count |
|----------|------|-------|
| 用户 (User) | 查询闲鱼店铺 | 1 |
| 商品 (Product) | 查询类目/属性/列表/详情/规格, 创建(单个/批量), 上架, 下架, 编辑, 编辑库存, 删除 | 12 |
| 订单 (Order) | 查询订单列表, 查询订单详情, 订单卡密列表, 物流发货, 修改价格 | 5 |
| 推送 (Push/Webhook) | 商品回调通知, 商品推送通知, 订单推送通知 | 3 (inbound) |
| 其他 (Other) | 查询快递公司 | 1 |

**Total: 19 API endpoints + 3 push/webhook notifications**

For full API details including request/response schemas, enums, and examples, see `references/api-reference.md`.

## Quick Start

### 1. Install Dependencies

```bash
pip install pyyaml requests
```

### 2. Configure Credentials

```bash
mkdir -p ~/.goofish
cp skills/goofish/config.example.yaml ~/.goofish/config.yaml
# Edit ~/.goofish/config.yaml with your AppKey and AppSecret
```

### 3. Use the Client

```python
from scripts.client import GoofishClient

client = GoofishClient()

# Query authorized stores
stores = client.query_stores()
print(stores)

# Query product list
products = client.query_products(page_no=1, page_size=20)
print(products)

# Query order list
orders = client.query_orders(page_no=1, page_size=20)
print(orders)
```

## What We CAN Do

### Product Management (Complete)
- **Create products** individually or in batches (up to 50/batch)
- **Query products** by status, time range, with pagination
- **Get product details** including images, SKUs, shipping info, special attributes
- **Edit products** — partial updates supported, syncs to Xianyu App if published
- **Edit inventory/price** — updates stock and price, syncs to App if published
- **Publish products** to Xianyu App (async, result via callback)
- **Unpublish products** from sale
- **Delete products** (draft/pending status only)
- **Query categories** by product type and industry
- **Query attributes** for category-specific property values
- **Query SKU specs** for multi-spec products (up to 100 products at once)

### Order Management
- **Query order list** by status, refund status, time range (up to 10k records)
- **Query order details** including buyer info, shipping address, payment info
- **Ship orders** with logistics info (express company, tracking number, sender info)
- **Modify order price** (item price + shipping fee)
- **Query order card/key info** for virtual goods orders

### Store & Utility
- **Query authorized Xianyu stores** linked to the account
- **Query express companies** available for shipping

### Supported Product Types
- 普通商品 (General), 已验货 (Verified), 验货宝 (Inspection Treasure)
- 品牌授权 (Brand Authorized), 闲鱼严选 (Xianyu Select), 闲鱼特卖 (Flash Sale)
- 品牌捡漏 (Brand Bargain), 跨境商品 (Cross-border)

### Supported Industries (22 categories)
手机, 潮品, 家电, 乐器, 3C数码, 奢品, 母婴, 美妆个护, 文玩/珠宝, 游戏电玩, 家居, 虚拟游戏, 租号, 图书, 卡券, 食品, 潮玩, 二手车, 宠植, 工艺礼品, 汽车服务, 其他

## What We CANNOT Do

### Not Supported by the API
- **Refund processing** — no API to approve/reject/handle refunds
- **Order cancellation** — no API to cancel orders
- **Buyer messaging** — no chat or message API
- **Store settings** — no store profile, banner, or configuration management
- **Advertising/promotion** — no marketing campaign API
- **Review management** — no review/reputation API
- **Analytics/dashboard** — no sales analytics or reporting API
- **Automatic price adjustment** — no dynamic pricing API
- **Batch order shipping** — orders must be shipped one at a time

### Platform Limitations
- **Product list only returns items modified in the last 6 months**
- **Product list capped at 10,000 total records** (page_no × page_size ≤ 10,000)
- **Delete only works on draft/pending products** — published items on Xianyu App must be deleted manually
- **Push notifications require a webhook server** — you must deploy a publicly accessible HTTP endpoint to receive product/order callbacks
- **Timestamp must be within 5 minutes** — requests expire quickly
- **All parameters are strongly validated** — must match documented types exactly

## Common Pitfalls

1. **Signature calculation order matters.** The MD5 sign is computed as `md5(appKey,bodyMd5,timestamp,appSecret)` in that exact order. For requests without a body, use `md5("{}")` or `md5("")`.

2. **Timestamp is in seconds, not milliseconds.** Using millisecond timestamps will cause signature validation failures.

3. **Body MD5 must be computed from the raw JSON string.** Whitespace and key ordering in the JSON body affect the MD5 hash. Use the exact string that will be sent.

4. **Product types, industries, and categories are interdependent.** You must first query categories (`/api/open/product/category/list`) with the correct `item_biz_type` and `sp_biz_type` to get valid `channel_cat_id` values.

5. **Multi-spec products require SKU consistency.** For multi-spec products, the top-level `price` must match one of the SKU prices, and `stock` must equal the sum of all SKU stocks.

6. **Edit is partial — only send fields you want to change.** Unset fields are left unchanged. However, for multi-spec products already published to Xianyu, you cannot clear all SKUs (at least one must remain).

7. **Publish and edit-in-place are async.** Results are delivered via callback URL, not in the API response. You must set up a webhook server to receive these notifications.

8. **The `seller_id` parameter is only for business-partner integrations.** For self-developed or third-party ERP integrations, omit this parameter.

9. **Product images use relative paths** (e.g., `product/20230722/161018-6546kdnp.jpg`), not full URLs, in the response. The full URL prefix varies.

10. **Push/Webhook endpoints are set in the Goofish developer console**, not via API. You must configure callback URLs manually for product and order push notifications.

## Multi-Agent Orchestration

When a task is too large for a single agent, split it across multiple agents running in parallel using Hermes `delegate_task` or the `orchestrator.py` script.

### Quick Patterns

| Scenario | Agents | Strategy |
|----------|--------|----------|
| Full inventory snapshot | 3 | Stores / Products / Orders in parallel |
| Multi-store sync | 2-3 | One agent per store |
| Batch publish pipeline | 2-3 | Phase 1: create, Phase 2: parallel publish |
| Bulk order shipment | 2-3 | Split orders across agents |
| Category discovery | 2-3 | One agent per industry type |
| Daily health check | 2-3 | Stores+Express / Orders / Products |

### Using orchestrator.py (Thread-based Parallelism)

```bash
# Pre-defined recipes
python scripts/orchestrator.py --recipe inventory-sync
python scripts/orchestrator.py --recipe health-check --dry-run  # preview only

# Custom task set
python -c "
from scripts.orchestrator import Task, TaskRunner, Recipes
from scripts.client import GoofishClient

client = GoofishClient()
runner = TaskRunner(client, max_workers=3)

# Parallel: query stores, products, and orders simultaneously
tasks = Recipes.store_inventory_sync()
results = runner.run_parallel(tasks)
runner.print_summary(results)
"
```

### Using Hermes delegate_task (Agent-based Parallelism)

For truly independent subtasks, delegate to parallel agents:

```
delegate_task(tasks=[
  {
    goal: "Query all Xianyu stores. Return store list.",
    context: "Use skills/goofish/scripts/client.py. Credentials configured.",
    toolsets: ["terminal"]
  },
  {
    goal: "Query all Xianyu products. Return count and summary.",
    context: "Use skills/goofish/scripts/client.py. Credentials configured.",
    toolsets: ["terminal"]
  },
  {
    goal: "Query all Xianyu orders. Return count by status.",
    context: "Use skills/goofish/scripts/client.py. Credentials configured.",
    toolsets: ["terminal"]
  }
])
```

### When to Use Which

- **orchestrator.py** — data processing within one Python process (thread pool). Good for API calls that return quickly and need post-processing.
- **delegate_task** — heavy reasoning tasks (multi-step logic, error recovery, format conversion). Each agent gets its own LLM context. Good for complex workflows like "create a product with correct categories and attributes".
- **Hybrid** — orchestrator for the fast API calls, delegate_task for the reasoning-heavy coordination.

Full patterns and examples: `references/multi-agent-patterns.md`

### Important Notes for Multi-Agent Setups

1. All agents share the same AppKey/AppSecret via env vars
2. Each agent generates its own timestamp (5-min validity per request)
3. API rate limits may apply — add delays if hitting limits
4. Hermes default max concurrent sub-agents: 3
5. Failed agents should not block others — always check per-agent results
6. Publish and edit operations are async — API returns "accepted", not "completed"

## Verification Checklist

- [ ] `~/.goofish/config.yaml` exists with valid `app_key` and `app_secret`
- [ ] `python scripts/client.py --test` runs successfully (lists stores)
- [ ] `python scripts/orchestrator.py --recipe inventory-sync --dry-run` shows expected tasks
- [ ] Signature generation produces valid signatures (test with a known request)
- [ ] Product operations (create → publish → unpublish → delete) work end-to-end
- [ ] Order queries return expected results
- [ ] Webhook server is deployed and reachable (if using push notifications)
- [ ] Multi-agent patterns tested with delegate_task (at least one parallel pattern)

## One-Shot Recipes

### Create and publish a product

```bash
cd /opt/fishkeeper
python -c "
from skills.goofish.scripts.client import GoofishClient
c = GoofishClient()
# Create product
result = c.create_product(
    item_biz_type=2, sp_biz_type=1, channel_cat_id='...',
    price=550000, express_fee=0, stock=10,
    publish_shop=[{...}]
)
# Publish
c.publish_product(product_id=result['data']['product_id'], user_name='...')
"
```

### Sync inventory from external system

```bash
python -c "
from skills.goofish.scripts.client import GoofishClient
c = GoofishClient()
products = c.query_all_products()
for p in products:
    c.update_stock(product_id=p['product_id'], stock=get_external_stock(p['outer_id']))
"
```

### Ship an order

```bash
python -c "
from skills.goofish.scripts.client import GoofishClient
c = GoofishClient()
c.ship_order(
    order_no='2226688164543566229',
    waybill_no='SF1234567890',
    express_code='shunfeng',
    express_name='顺丰速运'
)
"
```
