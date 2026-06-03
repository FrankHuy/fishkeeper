#!/usr/bin/env python3
"""
闲管家 (Goofish) Open Platform — Python API Client

Complete client for all Goofish Open Platform API endpoints.

Usage:
    from client import GoofishClient

    client = GoofishClient()
    # or with explicit config:
    client = GoofishClient(app_key="...", app_secret="...")

    # User
    stores = client.query_stores()

    # Products
    products = client.query_products(page_no=1, page_size=20)
    detail = client.query_product_detail(product_id=123)
    result = client.create_product(item_biz_type=2, sp_biz_type=1, ...)
    result = client.batch_create_products(product_data=[...])
    result = client.publish_product(product_id=123, user_name="...")
    result = client.unpublish_product(product_id=123)
    result = client.edit_product(product_id=123, title="New Title")
    result = client.update_stock(product_id=123, stock=10)
    result = client.delete_product(product_id=123)

    # Categories & Attributes
    categories = client.query_categories(item_biz_type=2, sp_biz_type=1)
    attrs = client.query_attributes(item_biz_type=2, sp_biz_type=1, channel_cat_id="...")
    skus = client.query_sku_list(product_ids=[123, 456])

    # Orders
    orders = client.query_orders(page_no=1, page_size=20)
    order_detail = client.query_order_detail(order_no="...")
    result = client.ship_order(order_no="...", waybill_no="...", express_code="...", express_name="...")
    result = client.modify_order_price(order_no="...", order_price=10000, express_fee=0)
    kam_list = client.query_order_kam(order_no="...")

    # Utilities
    companies = client.query_express_companies()
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests  # type: ignore

# Add parent scripts directory for signer import
_script_dir = Path(__file__).resolve().parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

from signer import GoofishSigner  # noqa: E402


class GoofishClient:
    """Client for the 闲管家 Open Platform API."""

    BASE_URL = "https://open.goofish.pro"

    def __init__(
        self,
        app_key: Optional[str] = None,
        app_secret: Optional[str] = None,
        base_url: Optional[str] = None,
        config_path: Optional[str] = None,
    ):
        """
        Initialize the Goofish client.

        Credential resolution order:
        1. Explicit app_key/app_secret arguments
        2. GOOFISH_APP_KEY / GOOFISH_APP_SECRET environment variables
        3. YAML config file (GOOFISH_CONFIG env var, ./goofish.yaml, ~/.goofish/config.yaml)

        Args:
            app_key: 开放平台AppKey
            app_secret: 开放平台AppSecret
            base_url: API base URL (default: https://open.goofish.pro)
            config_path: Path to YAML config file
        """
        self.base_url = (base_url or self.BASE_URL).rstrip("/")

        # Resolve credentials: explicit args > env vars > config file
        # Use str() to normalize: None means "not provided", empty string means "not set"
        self.app_key = str(app_key) if app_key else os.environ.get("GOOFISH_APP_KEY", "")
        self.app_secret = str(app_secret) if app_secret else os.environ.get("GOOFISH_APP_SECRET", "")

        if not self.app_key or not self.app_secret:
            config = self._load_config(config_path)
            if not self.app_key:
                self.app_key = config.get("app_key", "")
            if not self.app_secret:
                self.app_secret = config.get("app_secret", "")
            if config.get("base_url") and base_url is None:
                self.base_url = config["base_url"].rstrip("/")

        if not self.app_key or not self.app_secret:
            raise ValueError(
                "app_key and app_secret are required. "
                "Provide them directly, via GOOFISH_APP_KEY/GOOFISH_APP_SECRET env vars, "
                "or in a config file (~/.goofish/config.yaml)."
            )

        self.signer = GoofishSigner(app_key=self.app_key, app_secret=self.app_secret)
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def _load_config(self, config_path: Optional[str] = None) -> Dict[str, str]:
        """Load configuration from YAML file."""
        import yaml  # type: ignore

        paths = []
        if config_path:
            paths.append(Path(config_path))
        env_config = os.environ.get("GOOFISH_CONFIG", "")
        if env_config:
            paths.append(Path(env_config))
        paths.append(Path.cwd() / "goofish.yaml")
        paths.append(Path.home() / ".goofish" / "config.yaml")

        for p in paths:
            try:
                if p.is_file():
                    with open(p) as f:
                        data = yaml.safe_load(f) or {}
                    goofish = data.get("goofish", data)
                    return {
                        "app_key": str(goofish.get("app_key", "")),
                        "app_secret": str(goofish.get("app_secret", "")),
                        "base_url": str(goofish.get("base_url", "")),
                    }
            except Exception:
                continue

        return {"app_key": "", "app_secret": "", "base_url": ""}

    def _request(
        self,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        seller_id: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make an API request with automatic signing.

        Args:
            path: API path (e.g., '/api/open/user/authorize/list')
            body: JSON request body
            seller_id: Optional seller ID for business partner integrations
            extra_params: Additional query parameters

        Returns:
            Parsed JSON response dict
        """
        url = f"{self.base_url}{path}"
        params = self.signer.sign_headers(body=body, seller_id=seller_id)
        if extra_params:
            params.update(extra_params)

        # Serialize body with the SAME compact format used by signer for MD5.
        # Using requests' json= parameter would produce default separators
        # (", ", ": ") which differ from the compact separators (",", ":")
        # used in the MD5 calculation, causing server-side signature mismatch.
        if body is not None:
            body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        else:
            body_str = json.dumps({}, separators=(",", ":"))

        resp = self.session.post(
            url, params=params, data=body_str, timeout=30,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        result = resp.json()

        if result.get("code") != 0:
            raise GoofishAPIError(
                code=result.get("code", -1),
                message=result.get("msg", "Unknown error"),
                path=path,
            )

        return result

    # ============================================================
    # User / Store
    # ============================================================

    def query_stores(self) -> Dict[str, Any]:
        """查询闲鱼店铺 — query authorized Xianyu stores."""
        return self._request("/api/open/user/authorize/list", body={})

    # ============================================================
    # Product Categories & Attributes
    # ============================================================

    def query_categories(
        self,
        item_biz_type: int,
        sp_biz_type: Optional[int] = None,
        flash_sale_type: Optional[int] = None,
    ) -> Dict[str, Any]:
        """查询商品类目 — query product categories.

        Args:
            item_biz_type: 商品类型 (2=普通商品, 0=已验货, 10=验货宝, etc.)
            sp_biz_type: 行业类型 (1=手机, 2=潮品, etc.)
            flash_sale_type: 闲鱼特卖类型 (optional)
        """
        body: Dict[str, Any] = {"item_biz_type": item_biz_type}
        if sp_biz_type is not None:
            body["sp_biz_type"] = sp_biz_type
        if flash_sale_type is not None:
            body["flash_sale_type"] = flash_sale_type
        return self._request("/api/open/product/category/list", body=body)

    def query_attributes(
        self,
        item_biz_type: int,
        sp_biz_type: int,
        channel_cat_id: str,
        sub_property_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """查询商品属性 — query product attributes for a category.

        Args:
            item_biz_type: 商品类型
            sp_biz_type: 行业类型
            channel_cat_id: 渠道类目ID (from query_categories)
            sub_property_id: 属性值ID for cascaded queries (optional)
        """
        body: Dict[str, Any] = {
            "item_biz_type": item_biz_type,
            "sp_biz_type": sp_biz_type,
            "channel_cat_id": channel_cat_id,
        }
        if sub_property_id is not None:
            body["sub_property_id"] = sub_property_id
        return self._request("/api/open/product/pv/list", body=body)

    # ============================================================
    # Product CRUD
    # ============================================================

    def query_products(
        self,
        product_status: Optional[int] = None,
        sale_status: Optional[int] = None,
        update_time: Optional[List[int]] = None,
        create_time: Optional[List[int]] = None,
        online_time: Optional[List[int]] = None,
        offline_time: Optional[List[int]] = None,
        sold_time: Optional[List[int]] = None,
        page_no: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """查询商品列表 — query product list.

        Only returns products modified in the last 6 months.
        page_no * page_size must not exceed 10,000.

        Args:
            product_status: 商品状态 (-1/21/22/23/31/33/36)
            sale_status: 销售状态 (1=待发布 2=销售中 3=已下架)
            update_time: [start_timestamp, end_timestamp]
            create_time: [start_timestamp, end_timestamp]
            online_time: [start_timestamp, end_timestamp]
            offline_time: [start_timestamp, end_timestamp]
            sold_time: [start_timestamp, end_timestamp]
            page_no: 页码 (1-based)
            page_size: 每页行数 (max 100)
        """
        body: Dict[str, Any] = {}
        if product_status is not None:
            body["product_status"] = product_status
        if sale_status is not None:
            body["sale_status"] = sale_status
        if update_time:
            body["update_time"] = update_time
        if create_time:
            body["create_time"] = create_time
        if online_time:
            body["online_time"] = online_time
        if offline_time:
            body["offline_time"] = offline_time
        if sold_time:
            body["sold_time"] = sold_time

        body["page_no"] = page_no
        body["page_size"] = page_size

        return self._request("/api/open/product/list", body=body)

    def query_all_products(
        self,
        product_status: Optional[int] = None,
        sale_status: Optional[int] = None,
        update_time: Optional[List[int]] = None,
        page_size: int = 100,
    ) -> List[Dict[str, Any]]:
        """查询所有商品 — auto-paginate through all products.

        Automatically handles pagination to retrieve all matching products.
        Stops when the full 10,000 record limit is reached.
        """
        all_products = []
        page_no = 1
        while True:
            result = self.query_products(
                product_status=product_status,
                sale_status=sale_status,
                update_time=update_time,
                page_no=page_no,
                page_size=page_size,
            )
            data = result.get("data", {})
            items = data.get("list", [])
            all_products.extend(items)
            # Stop when current page returns fewer items than requested,
            # or when we hit the platform's 10,000 record cap.
            if len(items) < page_size or page_no * page_size >= 10000:
                break
            page_no += 1
        return all_products

    def query_product_detail(self, product_id: int) -> Dict[str, Any]:
        """查询商品详情 — get full product details."""
        return self._request(
            "/api/open/product/detail",
            body={"product_id": product_id},
        )

    def query_sku_list(self, product_ids: List[int]) -> Dict[str, Any]:
        """查询商品规格 — query SKU info for multi-spec products (max 100)."""
        return self._request(
            "/api/open/product/sku/list",
            body={"product_id": product_ids},
        )

    def create_product(
        self,
        item_biz_type: int,
        sp_biz_type: int,
        channel_cat_id: str,
        price: int,
        express_fee: int,
        stock: int,
        publish_shop: List[Dict[str, Any]],
        channel_pv: Optional[List[Dict[str, Any]]] = None,
        original_price: Optional[int] = None,
        outer_id: Optional[str] = None,
        stuff_status: Optional[int] = None,
        sku_items: Optional[List[Dict[str, Any]]] = None,
        book_data: Optional[Dict[str, Any]] = None,
        food_data: Optional[Dict[str, Any]] = None,
        report_data: Optional[Dict[str, Any]] = None,
        flash_sale_type: Optional[int] = None,
        advent_data: Optional[Dict[str, Any]] = None,
        inspect_data: Optional[Dict[str, Any]] = None,
        brand_data: Optional[Dict[str, Any]] = None,
        detail_images: Optional[List[str]] = None,
        sku_images: Optional[Dict[str, Any]] = None,
        ship_region_data: Optional[Dict[str, Any]] = None,
        is_tax_included: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """创建商品（单个） — create a single product.

        Required: item_biz_type, sp_biz_type, channel_cat_id, price, express_fee, stock, publish_shop

        publish_shop format (at least one item):
        [{
            "user_name": "闲鱼会员名",
            "province": 130000,
            "city": 130100,
            "district": 130101,
            "title": "商品标题",
            "content": "商品描述",
            "images": ["https://..."],
            "white_images": "https://...",    // optional
            "service_support": "SDR,NFR"       // optional
        }]
        """
        body: Dict[str, Any] = {
            "item_biz_type": item_biz_type,
            "sp_biz_type": sp_biz_type,
            "channel_cat_id": channel_cat_id,
            "price": price,
            "express_fee": express_fee,
            "stock": stock,
            "publish_shop": publish_shop,
        }

        # Optional fields
        if channel_pv is not None:
            body["channel_pv"] = channel_pv
        if original_price is not None:
            body["original_price"] = original_price
        if outer_id is not None:
            body["outer_id"] = outer_id
        if stuff_status is not None:
            body["stuff_status"] = stuff_status
        if sku_items is not None:
            body["sku_items"] = sku_items
        if book_data is not None:
            body["book_data"] = book_data
        if food_data is not None:
            body["food_data"] = food_data
        if report_data is not None:
            body["report_data"] = report_data
        if flash_sale_type is not None:
            body["flash_sale_type"] = flash_sale_type
        if advent_data is not None:
            body["advent_data"] = advent_data
        if inspect_data is not None:
            body["inspect_data"] = inspect_data
        if brand_data is not None:
            body["brand_data"] = brand_data
        if detail_images is not None:
            body["detail_images"] = detail_images
        if sku_images is not None:
            body["sku_images"] = sku_images
        if ship_region_data is not None:
            body["ship_region_data"] = ship_region_data
        if is_tax_included is not None:
            body["is_tax_included"] = is_tax_included

        return self._request("/api/open/product/create", body=body)

    def batch_create_products(
        self,
        product_data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """创建商品（批量） — batch create up to 50 products.

        Each item in product_data must include 'item_key' (unique per batch).
        Field requirements same as single create.
        """
        return self._request(
            "/api/open/product/batchCreate",
            body={"product_data": product_data},
        )

    def publish_product(
        self,
        product_id: int,
        user_name: List[str],
        specify_publish_time: Optional[str] = None,
        notify_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """上架商品 — publish product to Xianyu App (async, result via callback).

        Args:
            product_id: 管家商品ID
            user_name: [闲鱼会员名] — which store to publish to
            specify_publish_time: 定时上架时间 (e.g., '2023-07-21 00:00:00')
            notify_url: 上架回调地址
        """
        body: Dict[str, Any] = {
            "product_id": product_id,
            "user_name": user_name,
        }
        if specify_publish_time:
            body["specify_publish_time"] = specify_publish_time
        if notify_url:
            body["notify_url"] = notify_url
        return self._request("/api/open/product/publish", body=body)

    def unpublish_product(self, product_id: int) -> Dict[str, Any]:
        """下架商品 — unpublish a product."""
        return self._request(
            "/api/open/product/downShelf",
            body={"product_id": product_id},
        )

    def edit_product(
        self,
        product_id: int,
        notify_url: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """编辑商品 — edit product fields (partial update).

        Only send fields you want to change. If product is published,
        updates sync to Xianyu App asynchronously.

        Args:
            product_id: 管家商品ID
            notify_url: 回调地址 (only used when product is published)
            **kwargs: Any product fields to update (item_biz_type, price, title, etc.)
        """
        body: Dict[str, Any] = {"product_id": product_id}
        body.update(kwargs)
        if notify_url:
            body["notify_url"] = notify_url
        return self._request("/api/open/product/edit", body=body)

    def update_stock(
        self,
        product_id: int,
        price: Optional[int] = None,
        original_price: Optional[int] = None,
        stock: Optional[int] = None,
        sku_items: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """编辑库存 — update stock and/or price.

        For single-spec products, use stock parameter.
        For multi-spec products, use sku_items parameter.

        If product is published, stock updates sync to Xianyu App immediately.
        """
        body: Dict[str, Any] = {"product_id": product_id}
        if price is not None:
            body["price"] = price
        if original_price is not None:
            body["original_price"] = original_price
        if stock is not None:
            body["stock"] = stock
        if sku_items is not None:
            body["sku_items"] = sku_items
        return self._request("/api/open/product/edit/stock", body=body)

    def delete_product(self, product_id: int) -> Dict[str, Any]:
        """删除商品 — delete product (draft/pending only).

        Does NOT delete products already published on Xianyu App.
        """
        return self._request(
            "/api/open/product/delete",
            body={"product_id": product_id},
        )

    # ============================================================
    # Orders
    # ============================================================

    def query_orders(
        self,
        authorize_id: Optional[int] = None,
        order_status: Optional[int] = None,
        refund_status: Optional[int] = None,
        update_time: Optional[List[int]] = None,
        pay_time: Optional[List[int]] = None,
        consign_time: Optional[List[int]] = None,
        confirm_time: Optional[List[int]] = None,
        page_no: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """查询订单列表 — query order list.

        Total accessible via pagination: 10,000 records.
        update_time must be within the last 6 months.
        """
        body: Dict[str, Any] = {}
        if authorize_id is not None:
            body["authorize_id"] = authorize_id
        if order_status is not None:
            body["order_status"] = order_status
        if refund_status is not None:
            body["refund_status"] = refund_status
        if update_time:
            body["update_time"] = update_time
        if pay_time:
            body["pay_time"] = pay_time
        if consign_time:
            body["consign_time"] = consign_time
        if confirm_time:
            body["confirm_time"] = confirm_time

        body["page_no"] = page_no
        body["page_size"] = page_size

        return self._request("/api/open/order/list", body=body)

    def query_all_orders(
        self,
        order_status: Optional[int] = None,
        refund_status: Optional[int] = None,
        update_time: Optional[List[int]] = None,
        page_size: int = 100,
    ) -> List[Dict[str, Any]]:
        """查询所有订单 — auto-paginate through all orders."""
        all_orders = []
        page_no = 1
        while True:
            result = self.query_orders(
                order_status=order_status,
                refund_status=refund_status,
                update_time=update_time,
                page_no=page_no,
                page_size=page_size,
            )
            data = result.get("data", {})
            items = data.get("list", [])
            all_orders.extend(items)
            if len(items) < page_size or page_no * page_size >= 10000:
                break
            page_no += 1
        return all_orders

    def query_order_detail(self, order_no: str) -> Dict[str, Any]:
        """查询订单详情 — get full order details."""
        return self._request(
            "/api/open/order/detail",
            body={"order_no": order_no},
        )

    def query_order_kam(self, order_no: str) -> Dict[str, Any]:
        """订单卡密列表 — query virtual goods card/key info."""
        return self._request(
            "/api/open/order/kam/list",
            body={"order_no": order_no},
        )

    def ship_order(
        self,
        order_no: str,
        waybill_no: str,
        express_code: str,
        express_name: str,
        ship_name: Optional[str] = None,
        ship_mobile: Optional[str] = None,
        ship_district_id: Optional[int] = None,
        ship_prov_name: Optional[str] = None,
        ship_city_name: Optional[str] = None,
        ship_area_name: Optional[str] = None,
        ship_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """订单物流发货 — ship an order.

        Sender info can be provided via 3 methods:
        1. ship_district_id + ship_address (+ ship_name, ship_mobile)
        2. ship_prov_name + ship_city_name + ship_area_name + ship_address
        3. None — uses default shipping address from Goofish dashboard

        Required: order_no, waybill_no, express_code, express_name
        """
        body: Dict[str, Any] = {
            "order_no": order_no,
            "waybill_no": waybill_no,
            "express_code": express_code,
            "express_name": express_name,
        }
        if ship_name is not None:
            body["ship_name"] = ship_name
        if ship_mobile is not None:
            body["ship_mobile"] = ship_mobile
        if ship_district_id is not None:
            body["ship_district_id"] = ship_district_id
        if ship_prov_name is not None:
            body["ship_prov_name"] = ship_prov_name
        if ship_city_name is not None:
            body["ship_city_name"] = ship_city_name
        if ship_area_name is not None:
            body["ship_area_name"] = ship_area_name
        if ship_address is not None:
            body["ship_address"] = ship_address
        return self._request("/api/open/order/ship", body=body)

    def modify_order_price(
        self,
        order_no: str,
        order_price: int,
        express_fee: int,
    ) -> Dict[str, Any]:
        """订单修改价格 — modify order price.

        Args:
            order_no: 闲鱼订单号
            order_price: 订单价格(分), min 1
            express_fee: 运费(分), 0 = free shipping
        """
        return self._request(
            "/api/open/order/modify/price",
            body={
                "order_no": order_no,
                "order_price": order_price,
                "express_fee": express_fee,
            },
        )

    # ============================================================
    # Utilities
    # ============================================================

    def query_express_companies(self) -> Dict[str, Any]:
        """查询快递公司 — query available express companies."""
        return self._request("/api/open/express/companies", body={})


class GoofishAPIError(Exception):
    """Raised when the Goofish API returns a non-zero code."""

    def __init__(self, code: int, message: str, path: str):
        self.code = code
        self.message = message
        self.path = path
        super().__init__(f"Goofish API error [{path}]: code={code}, msg={message}")


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="闲管家 Open Platform CLI Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--app-key", help="AppKey")
    parser.add_argument("--app-secret", help="AppSecret")
    parser.add_argument("--test", action="store_true", help="Test connection by listing stores")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # stores
    subparsers.add_parser("stores", help="List authorized stores")

    # categories
    cat_parser = subparsers.add_parser("categories", help="List product categories")
    cat_parser.add_argument("--item-biz-type", type=int, required=True, help="商品类型")
    cat_parser.add_argument("--sp-biz-type", type=int, help="行业类型")

    # attributes
    attr_parser = subparsers.add_parser("attributes", help="List product attributes")
    attr_parser.add_argument("--item-biz-type", type=int, required=True)
    attr_parser.add_argument("--sp-biz-type", type=int, required=True)
    attr_parser.add_argument("--channel-cat-id", required=True)

    # products
    prod_parser = subparsers.add_parser("products", help="List products")
    prod_parser.add_argument("--status", type=int, help="商品状态")
    prod_parser.add_argument("--page", type=int, default=1)
    prod_parser.add_argument("--page-size", type=int, default=20)

    # product detail
    detail_parser = subparsers.add_parser("product-detail", help="Get product detail")
    detail_parser.add_argument("--product-id", type=int, required=True)

    # orders
    order_parser = subparsers.add_parser("orders", help="List orders")
    order_parser.add_argument("--status", type=int, help="订单状态")
    order_parser.add_argument("--page", type=int, default=1)
    order_parser.add_argument("--page-size", type=int, default=20)

    # order detail
    od_parser = subparsers.add_parser("order-detail", help="Get order detail")
    od_parser.add_argument("--order-no", required=True)

    # express companies
    subparsers.add_parser("express-companies", help="List express companies")

    args = parser.parse_args()

    try:
        client = GoofishClient(app_key=args.app_key, app_secret=args.app_secret)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("\nConfigure credentials via:", file=sys.stderr)
        print("  1. --app-key and --app-secret arguments", file=sys.stderr)
        print("  2. GOOFISH_APP_KEY and GOOFISH_APP_SECRET env vars", file=sys.stderr)
        print("  3. ~/.goofish/config.yaml", file=sys.stderr)
        sys.exit(1)

    try:
        if args.test or args.command == "stores":
            result = client.query_stores()
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif args.command == "categories":
            result = client.query_categories(
                item_biz_type=args.item_biz_type,
                sp_biz_type=args.sp_biz_type,
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif args.command == "attributes":
            result = client.query_attributes(
                item_biz_type=args.item_biz_type,
                sp_biz_type=args.sp_biz_type,
                channel_cat_id=args.channel_cat_id,
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif args.command == "products":
            result = client.query_products(
                product_status=args.status,
                page_no=args.page,
                page_size=args.page_size,
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif args.command == "product-detail":
            result = client.query_product_detail(product_id=args.product_id)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif args.command == "orders":
            result = client.query_orders(
                order_status=args.status,
                page_no=args.page,
                page_size=args.page_size,
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif args.command == "order-detail":
            result = client.query_order_detail(order_no=args.order_no)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif args.command == "express-companies":
            result = client.query_express_companies()
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            # Default: test connection
            result = client.query_stores()
            print(json.dumps(result, indent=2, ensure_ascii=False))

    except GoofishAPIError as e:
        print(f"API Error: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Request Error: {e}", file=sys.stderr)
        sys.exit(1)
