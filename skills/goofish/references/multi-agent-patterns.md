# 闲管家 Multi-Agent Orchestration Patterns

本文档描述如何使用 Hermes 的 `delegate_task` 工具启动多个独立 agent 并行处理闲管家 API 任务。结合 `scripts/orchestrator.py` 中的 Task 定义，可以实现复杂的多 agent 工作流。

---

## 核心概念

### 什么可以并行？

闲管家 API 的大部分**查询操作**是天然独立的，可以并行执行：

- 查询店铺 × 查询商品 × 查询订单 → 三者互不依赖
- 不同商品类型的类目查询 → 互不依赖
- 不同店铺的商品查询 → 互不依赖
- 不同订单的详情查询 → 互不依赖
- 批量发货（不同订单） → 互不依赖

### 什么必须串行？

有数据依赖的操作必须按顺序执行：

- 查询类目 → 查询属性 → 创建商品（属性依赖类目 ID）
- 批量创建 → 发布（发布依赖创建返回的 product_id）
- 查询订单详情 → 发货（需要确认订单状态）

---

## Pattern 1: 三路并行快照 (Inventory Snapshot)

**场景：** 获取全量店铺、商品、订单快照，用于数据对比或报表。

### 使用 Hermes delegate_task

```
delegate_task(tasks=[
  {
    goal: "Query all authorized Xianyu stores using GoofishClient.query_stores(). Return the store list with user_name, shop_name, item_biz_types.",
    context: "Use skills/goofish/scripts/client.py. Credentials are configured.",
    toolsets: ["terminal"]
  },
  {
    goal: "Query all products from Xianyu using GoofishClient.query_all_products(). Return total count and summary per store.",
    context: "Use skills/goofish/scripts/client.py. Credentials are configured.",
    toolsets: ["terminal"]
  },
  {
    goal: "Query all orders from Xianyu using GoofishClient.query_all_orders(). Return total count and summary by status.",
    context: "Use skills/goofish/scripts/client.py. Credentials are configured.",
    toolsets: ["terminal"]
  }
])
```

### 使用 orchestrator.py

```bash
python skills/goofish/scripts/orchestrator.py --recipe inventory-sync
```

### 结果处理

三个 agent 并行执行，结果汇总后可以：
1. 对比外部 ERP 库存数据，找出差异
2. 生成运营日报
3. 触发自动补货/调价

---

## Pattern 2: 批量上架流水线 (Batch Publish Pipeline)

**场景：** 批量创建商品然后上架到多个店铺。

### 流程图

```
Phase 1 (串行依赖):
  查询类目 → 查询属性 → [创建商品(批量)]

Phase 2 (并行):
  [发布到店铺A] [发布到店铺B] [发布到店铺C]
```

### 使用 Hermes delegate_task

```
# Phase 1: 创建商品
delegate_task(
  goal: "Create 10 products for Xianyu store. First query categories (item_biz_type=2, sp_biz_type=9), then query attributes, then batch create with correct channel_cat_id and channel_pv.",
  context: "Store user_name: tb924343042. Products are 3C accessories. Use skills/goofish/scripts/client.py.",
  toolsets: ["terminal"]
)

# Phase 2: 拿到 product_ids 后，并行发布到多个店铺
delegate_task(tasks=[
  {
    goal: "Publish product IDs [123, 456] to Xianyu store 'tb924343042' using GoofishClient.publish_product().",
    context: "Use skills/goofish/scripts/client.py.",
    toolsets: ["terminal"]
  },
  {
    goal: "Publish product IDs [789, 012] to Xianyu store 'other_store' using GoofishClient.publish_product().",
    context: "Use skills/goofish/scripts/client.py.",
    toolsets: ["terminal"]
  }
])
```

---

## Pattern 3: 多店铺库存同步 (Multi-Store Inventory Sync)

**场景：** 你有多个闲鱼店铺，需要同步库存数据。

### 架构

```
Agent 0 (协调者):
  └─ 查询所有店铺 → 分配任务

Agent 1 (店铺A):         Agent 2 (店铺B):         Agent 3 (店铺C):
  查询店铺A商品列表        查询店铺B商品列表        查询店铺C商品列表
  查询店铺A订单列表        查询店铺B订单列表        查询店铺C订单列表
```

### 使用 Hermes delegate_task

```
# Step 1: 查询所有店铺
delegate_task(
  goal: "Query all authorized Xianyu stores. Return the list of store names and their user_name values.",
  context: "Use skills/goofish/scripts/client.py.",
  toolsets: ["terminal"]
)

# Step 2: 拿到店铺列表后，并行查询每个店铺
delegate_task(tasks=[
  {
    goal: "For Xianyu store 'store_a_user', query all products and all orders. Return summary: product count, order count by status.",
    context: "Store user_name: store_a_user. Use skills/goofish/scripts/client.py.",
    toolsets: ["terminal"]
  },
  {
    goal: "For Xianyu store 'store_b_user', query all products and all orders. Return summary: product count, order count by status.",
    context: "Store user_name: store_b_user. Use skills/goofish/scripts/client.py.",
    toolsets: ["terminal"]
  }
])
```

---

## Pattern 4: 批量发货 (Bulk Shipment)

**场景：** 有大量待发货订单，需要并行处理。

### 使用 Hermes delegate_task

最多 3 个 agent 并行（Hermes 默认限制），每个 agent 处理一部分订单：

```
delegate_task(tasks=[
  {
    goal: "Ship Xianyu orders: order1, order2, order3. For each: query detail, verify status, then ship via SF Express. Use GoofishClient.",
    context: "Orders: [order1, order2, order3]. Express: shunfeng/顺丰速运. Waybill: [SF001, SF002, SF003]. Use skills/goofish/scripts/client.py.",
    toolsets: ["terminal"]
  },
  {
    goal: "Ship Xianyu orders: order4, order5, order6. For each: query detail, verify status, then ship via YTO Express. Use GoofishClient.",
    context: "Orders: [order4, order5, order6]. Express: yuantong/圆通速递. Waybill: [YT001, YT002, YT003]. Use skills/goofish/scripts/client.py.",
    toolsets: ["terminal"]
  }
])
```

### 使用 orchestrator.py

```python
from orchestrator import Recipes, TaskRunner
from client import GoofishClient

shipments = [
    {"order_no": "123...", "waybill_no": "SF001", "express_code": "shunfeng", "express_name": "顺丰速运"},
    {"order_no": "456...", "waybill_no": "YT001", "express_code": "yuantong", "express_name": "圆通速运"},
    {"order_no": "789...", "waybill_no": "ZT001", "express_code": "zhongtong", "express_name": "中通快递"},
]

tasks = Recipes.bulk_order_shipment(shipments)
runner = TaskRunner(client, max_workers=3)
results = runner.run_parallel(tasks)
runner.print_summary(results)
```

---

## Pattern 5: 类目发现 (Category Discovery)

**场景：** 需要了解所有可用的商品类目和属性，用于构建商品创建模板。

### 使用 Hermes delegate_task

```
delegate_task(tasks=[
  {
    goal: "Query all product categories for 手机 (item_biz_type=2, sp_biz_type=1) and their attributes. Return the full hierarchy.",
    context: "Use skills/goofish/scripts/client.py. First call query_categories, then for each category call query_attributes.",
    toolsets: ["terminal"]
  },
  {
    goal: "Query all product categories for 潮品 (item_biz_type=2, sp_biz_type=2) and their attributes. Return the full hierarchy.",
    context: "Use skills/goofish/scripts/client.py. First call query_categories, then for each category call query_attributes.",
    toolsets: ["terminal"]
  },
  {
    goal: "Query all product categories for 3C数码 (item_biz_type=2, sp_biz_type=9) and their attributes. Return the full hierarchy.",
    context: "Use skills/goofish/scripts/client.py. First call query_categories, then for each category call query_attributes.",
    toolsets: ["terminal"]
  }
])
```

---

## Pattern 6: 日常健康检查 (Daily Health Check)

**场景：** 每天自动检查店铺状态、快递可用性、近期订单。

### 使用 orchestrator.py

```bash
python skills/goofish/scripts/orchestrator.py --recipe health-check
```

### 使用 Hermes delegate_task

```
delegate_task(tasks=[
  {
    goal: "Health check: Query all Xianyu stores and report which are valid/active. Also query available express companies.",
    context: "Use skills/goofish/scripts/client.py.",
    toolsets: ["terminal"]
  },
  {
    goal: "Health check: Query recent 7 days of Xianyu orders. Report total count, pending ship count, and any anomalies.",
    context: "Use skills/goofish/scripts/client.py. Use update_time filter for last 7 days.",
    toolsets: ["terminal"]
  },
  {
    goal: "Health check: Query recently modified Xianyu products. Report total active products and any with zero stock.",
    context: "Use skills/goofish/scripts/client.py. Query products with sale_status=2 (销售中).",
    toolsets: ["terminal"]
  }
])
```

---

## Agent 数量与任务划分建议

| 场景 | 建议 Agent 数 | 划分策略 |
|------|-------------|---------|
| 全量快照 | 3 | 店铺/商品/订单各一个 |
| 多店铺同步 | 2-3 | 按店铺划分 |
| 批量上架 | 2-3 | Phase 1(创建) + Phase 2(并行发布) |
| 批量发货 | 2-3 | 按订单数量均分 |
| 类目发现 | 2-3 | 按行业类型划分 |
| 日常巡检 | 2-3 | 店铺+快递 / 订单 / 商品 |

Hermes 默认允许最多 3 个并发子 agent（由 `delegation.max_concurrent_children` 控制）。

---

## 注意事项

1. **API 限流：** 闲管家 API 可能有频率限制。并行请求过多可能触发限流。建议单个 agent 内对同一类 API 调用加入适当间隔。

2. **时间戳有效期：** 每个 API 请求的签名在 5 分钟内有效。并行 agent 各自生成独立的时间戳，互不影响。

3. **凭证共享：** 所有 agent 共享同一套 AppKey/AppSecret。通过环境变量 `GOOFISH_APP_KEY` / `GOOFISH_APP_SECRET` 传递。

4. **错误处理：** 某个 agent 失败不应阻塞其他 agent。汇总结果时检查每个 agent 的成功状态。

5. **数据量限制：** 商品/订单列表分页上限 10,000 条。大数据量同步时注意分页。

6. **异步操作：** 上架和编辑（已发布商品）是异步的，结果通过回调返回。agent 调用后 API 返回成功只表示请求已接受，不代表操作完成。

7. **幂等性：** 发货、修改价格等操作可能不幂等。并行 agent 要确保不会重复处理同一订单。
