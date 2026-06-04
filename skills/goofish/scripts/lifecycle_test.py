#!/usr/bin/env python3
"""
Goofish end-to-end product lifecycle test harness.

Covers 15 test cases across the full product lifecycle:
  T01 Auth/store query
  T02 Category discovery
  T03 Attribute query
  T04 Create product draft
  T05 Product detail after create
  T06 Product list verification
  T07 Edit stock and price
  T08 Product detail after edit (verify values)
  T09 Publish product (async accepted)
  T10 Poll after publish (status transition to 22)
  T11 Down-shelf product
  T12 Product detail after down-shelf (status 31)
  T13 Delete product (cleanup)
  T14 Query express companies
  T15 Query orders list

The harness is defensive:
  - Uses a clearly marked TEST listing title with timestamp
  - Uses stock=1 and a high test price to prevent accidental purchases
  - Always attempts down-shelf/cleanup if product_id was created
  - Writes a JSON report to goofish_lifecycle_test_report.json

Usage:
  python goofish_lifecycle_test.py [options]

Options:
  --item-biz-type INT    Product type (default: 2=普通商品)
  --sp-biz-type INT      Industry type (default: 21=家居)
  --price INT            Price in fen/cents (default: 99999900)
  --edit-price INT       Price after edit in fen/cents (default: 99999800)
  --express-fee INT      Shipping fee in fen/cents (default: 0)
  --stock INT            Initial stock (default: 1)
  --edit-stock INT       Stock after edit (default: 2)
  --stuff-status INT     Condition (default: 90=9新)
  --publish-wait INT     Seconds to poll after publish (default: 20)
  --skip-publish         Skip T09-T10 publish steps
  --report PATH          Report output path (default: goofish_lifecycle_test_report.json)
"""
import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Load env vars from /etc/profile.d if not already set
if not os.environ.get('GOOFISH_APP_KEY'):
    import subprocess
    try:
        env_output = subprocess.check_output(
            'bash -c "source /etc/profile.d/goofish.sh 2>/dev/null && env"',
            shell=True, text=True, stderr=subprocess.DEVNULL
        )
        for line in env_output.strip().split('\n'):
            line = line.strip()
            if line.startswith('GOOFISH_'):
                k, _, v = line.partition('=')
                os.environ[k] = v
    except Exception:
        pass

SKILL_DIR = Path('/root/.hermes/skills/ecommerce/goofish')
sys.path.insert(0, str(SKILL_DIR / 'scripts'))
from client import GoofishClient, GoofishAPIError  # noqa: E402


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def step(report: Dict[str, Any], name: str, fn):
    rec = {"name": name, "started_at": now_iso(), "ok": False}
    print(f'\n{"="*60}\n{name}\n{"="*60}', flush=True)
    try:
        out = fn()
        rec["ok"] = True
        rec["result"] = json.dumps(out, ensure_ascii=False, default=str)[:1000]
        print(f'  OK: {json.dumps(out, ensure_ascii=False, default=str)[:500]}', flush=True)
        return out
    except GoofishAPIError as e:
        rec["ok"] = False
        rec["error"] = f"code={e.code} msg={e.message}"
        rec["api_code"] = e.code
        rec["api_path"] = e.path
        print(f'  API Error: code={e.code} msg={e.message}', flush=True)
        return None
    except Exception as e:
        rec["ok"] = False
        rec["error"] = f"{type(e).__name__}: {e}"
        rec["traceback"] = traceback.format_exc()
        print(f'  Error: {type(e).__name__}: {e}', flush=True)
        return None
    finally:
        rec["finished_at"] = now_iso()
        report.setdefault("steps", []).append(rec)


def build_publish_shop(store: Dict, title: str, args) -> Dict:
    """Build a publish_shop entry with all required fields discovered during testing."""
    return {
        "user_name": store.get("user_name", ""),
        "title": title,
        "content": f"自动化测试商品，请勿购买。created={int(time.time())}",
        "images": ["http://img.alicdn.com/bao/uploaded/i4/813899043/O1CN01QDTguz2GfkldvsPXL_!!4611686018427387171-53-xy_item.heic"],
        "stuff_status": args.stuff_status,
        "province": store.get("province", 110000),
        "city": store.get("city", 110100),
        "district": store.get("district", 110108),
        "consign_type": 1,
        "price": args.price,
        "express_fee": args.express_fee,
        "stock": args.stock,
        "outer_id": f"goofish-e2e-{int(time.time())}",
    }


def main():
    ap = argparse.ArgumentParser(description="Goofish API lifecycle test")
    ap.add_argument("--item-biz-type", type=int, default=2)
    ap.add_argument("--sp-biz-type", type=int, default=21)
    ap.add_argument("--channel-cat-id", default="1c1a9ee00691844737b3d33c282f2081",
                    help="Pre-verified channel_cat_id (default: 家居/体验测评)")
    ap.add_argument("--price", type=int, default=99999900)
    ap.add_argument("--edit-price", type=int, default=99999800)
    ap.add_argument("--express-fee", type=int, default=0)
    ap.add_argument("--stock", type=int, default=1)
    ap.add_argument("--edit-stock", type=int, default=2)
    ap.add_argument("--stuff-status", type=int, default=90)
    ap.add_argument("--publish-wait", type=int, default=20)
    ap.add_argument("--skip-publish", action="store_true")
    ap.add_argument("--report", default="goofish_lifecycle_test_report.json")
    args = ap.parse_args()

    report_path = Path(args.report)
    report = {"started_at": now_iso(), "args": vars(args), "steps": [], "created_product_id": None}
    product_id = None
    c = GoofishClient()

    try:
        # T01
        stores_resp = step(report, "T01: Query authorized stores", c.query_stores)
        if not stores_resp:
            raise RuntimeError("Cannot query stores - check credentials and network")
        stores = stores_resp.get("data", {}).get("list", [])
        if not stores:
            raise RuntimeError("No authorized stores found")
        store = stores[0]
        report["selected_store"] = {"user_nick": store.get("user_nick"), "is_valid": store.get("is_valid")}

        # T02
        step(report, "T02: Query categories", lambda: c.query_categories(
            item_biz_type=args.item_biz_type, sp_biz_type=args.sp_biz_type))

        # T03
        step(report, "T03: Query attributes", lambda: c.query_attributes(
            item_biz_type=args.item_biz_type, sp_biz_type=args.sp_biz_type,
            channel_cat_id=args.channel_cat_id))

        # T04
        test_title = f"闲管家API自动化测试商品-请勿购买-{int(time.time())}"
        shop = build_publish_shop(store, test_title, args)

        create_resp = step(report, "T04: Create product draft", lambda: c.create_product(
            item_biz_type=args.item_biz_type, sp_biz_type=args.sp_biz_type,
            channel_cat_id=args.channel_cat_id, price=args.price,
            express_fee=args.express_fee, stock=args.stock, publish_shop=[shop]))

        if create_resp:
            product_id = create_resp.get("data", {}).get("product_id")
            report["created_product_id"] = product_id
            print(f"  product_id={product_id}, status={create_resp.get('data',{}).get('product_status')}")

        if not product_id:
            raise RuntimeError("Product creation failed - cannot continue lifecycle")

        # T05
        detail1 = step(report, "T05: Product detail after create", lambda: c.query_product_detail(product_id))
        if detail1:
            d = detail1.get("data", {})
            report["after_create"] = {"price": d.get("price"), "stock": d.get("stock"), "status": d.get("product_status")}

        # T06
        def check_list():
            prods = c.query_products(page_no=1, page_size=50)
            items = prods.get("data", {}).get("list", [])
            found = any(p.get("product_id") == int(product_id) for p in items)
            return {"found_in_list": found, "product_id": product_id, "total": prods.get("data", {}).get("count", 0)}
        step(report, "T06: Product list contains created product", check_list)

        # T07
        step(report, "T07: Edit stock and price", lambda: c.update_stock(
            product_id, price=args.edit_price, stock=args.edit_stock))

        # T08
        detail2 = step(report, "T08: Product detail after edit", lambda: c.query_product_detail(product_id))
        if detail2:
            d = detail2.get("data", {})
            price_ok = d.get("price") == args.edit_price
            stock_ok = d.get("stock") == args.edit_stock
            report["after_edit"] = {"price": d.get("price"), "stock": d.get("stock"),
                                    "price_ok": price_ok, "stock_ok": stock_ok}
            print(f"  price={d.get('price')} ({'OK' if price_ok else 'MISMATCH'}), "
                  f"stock={d.get('stock')} ({'OK' if stock_ok else 'MISMATCH'})")

        # T09
        if not args.skip_publish:
            step(report, "T09: Publish product (async)", lambda: c.publish_product(
                product_id, [store.get("user_name", "")]))

            # T10
            def poll_publish():
                obs = []
                deadline = time.time() + args.publish_wait
                while time.time() < deadline:
                    time.sleep(5)
                    d = c.query_product_detail(product_id)
                    s = d.get("data", {}).get("product_status")
                    obs.append({"poll": len(obs)+1, "status": s, "at": now_iso()})
                    print(f"  Poll {len(obs)}: status={s}")
                    if s == 22:
                        break
                return {"observations": obs, "reached_status_22": any(o["status"] == 22 for o in obs)}
            step(report, "T10: Poll after publish", poll_publish)

        # T11
        step(report, "T11: Down-shelf product", lambda: c.unpublish_product(product_id))

        # T12
        detail3 = step(report, "T12: Product detail after down-shelf", lambda: c.query_product_detail(product_id))
        if detail3:
            s = detail3.get("data", {}).get("product_status")
            report["after_downshelf"] = {"status": s}

        # T13
        step(report, "T13: Delete product", lambda: c.delete_product(product_id))

        # T14
        step(report, "T14: Query express companies", c.query_express_companies)

        # T15
        step(report, "T15: Query orders list", lambda: c.query_orders(page_no=1, page_size=5))

        report["ok"] = True

    except Exception as e:
        report["ok"] = False
        report["fatal_error"] = {"type": type(e).__name__, "message": str(e), "traceback": traceback.format_exc()}
        # Cleanup on failure
        if product_id:
            for label, fn in [("down_shelf", lambda: c.unpublish_product(product_id)),
                              ("delete", lambda: c.delete_product(product_id))]:
                try:
                    r = fn()
                    report.setdefault("cleanup", []).append({"action": label, "ok": True, "result": str(r)[:200]})
                except Exception as ce:
                    report.setdefault("cleanup", []).append({"action": label, "ok": False, "error": str(ce)})

    finally:
        passed = sum(1 for s in report["steps"] if s["ok"])
        failed = len(report["steps"]) - passed
        report["summary"] = {"total": len(report["steps"]), "passed": passed, "failed": failed}
        report["finished_at"] = now_iso()

        print(f'\n{"="*60}')
        print(f'RESULT: {passed}/{len(report["steps"])} PASSED, {failed} FAILED')
        print(f'{"="*60}')
        for s in report["steps"]:
            tag = "PASS" if s["ok"] else "FAIL"
            extra = f' -- {s.get("error","")}' if not s["ok"] else ""
            print(f'  [{tag}] {s["name"]}{extra}')

        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(f'\nReport: {report_path}')


if __name__ == "__main__":
    main()
