#!/usr/bin/env python3
"""
闲管家 (Goofish) — Multi-Agent Orchestrator

Defines reusable task definitions and a parallel runner for multi-agent workflows.
Each task is a self-contained unit of work that can be delegated to an independent
agent (e.g., via Hermes delegate_task) and executed in parallel.

Usage:
    # CLI: run pre-defined recipes
    python orchestrator.py --recipe inventory-sync

    # Programmatic: build and run custom task sets
    from orchestrator import Task, TaskRunner

    runner = TaskRunner(client)
    results = runner.run_parallel([
        Task("sync_products", "query_all_products"),
        Task("sync_orders", "query_all_orders"),
    ])

    # With Hermes delegate_task (see references/multi-agent-patterns.md):
    # delegate_task(goal="sync inventory for store XXX", context=task_context)
"""

from __future__ import annotations

import concurrent.futures
import json
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# Allow importing from the same directory
_script_dir = Path(__file__).resolve().parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

from client import GoofishClient  # noqa: E402


# ============================================================
# Task Definition
# ============================================================

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Task:
    """A unit of work that can be delegated to an agent.

    Each Task wraps one or more API calls and produces a structured result.
    Tasks can be run in parallel when they have no data dependencies.

    Attributes:
        id: Unique task identifier
        description: Human-readable description for agent context
        method: Client method name to call
        args: Positional arguments for the method
        kwargs: Keyword arguments for the method
        depends_on: List of task IDs that must complete before this one
        agent_role: Suggested role for the agent (for delegate_task)
        store_filter: Optional store name to scope the task to a specific store
    """

    id: str
    description: str
    method: str
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    agent_role: str = "leaf"
    store_filter: Optional[str] = None

    # Runtime state
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: float = 0.0

    def to_agent_context(self) -> str:
        """Generate a self-contained context for delegating this task to an agent."""
        lines = [
            f"Task: {self.id}",
            f"Description: {self.description}",
            f"Action: Call client.{self.method}()",
        ]
        if self.args:
            lines.append(f"Args: {json.dumps(self.args, ensure_ascii=False)}")
        if self.kwargs:
            lines.append(f"Kwargs: {json.dumps(self.kwargs, ensure_ascii=False)}")
        if self.store_filter:
            lines.append(f"Store: {self.store_filter}")
        lines.append("")
        lines.append("Use the GoofishClient to execute this task.")
        lines.append("Return a JSON summary: {\"success\": true/false, \"summary\": \"...\", \"count\": N}")
        return "\n".join(lines)


# ============================================================
# Task Runner
# ============================================================

class TaskRunner:
    """Runs Tasks against a GoofishClient, with parallel execution support."""

    def __init__(self, client: GoofishClient, max_workers: int = 5):
        self.client = client
        self.max_workers = max_workers

    def _execute_task(self, task: Task) -> Task:
        """Execute a single task and update its state."""
        task.status = TaskStatus.RUNNING
        start = time.monotonic()

        try:
            method = getattr(self.client, task.method)
            result = method(*task.args, **task.kwargs)
            task.result = result
            task.status = TaskStatus.SUCCESS
        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.FAILED

        task.duration_ms = (time.monotonic() - start) * 1000
        return task

    def run_sequential(self, tasks: List[Task]) -> List[Task]:
        """Run tasks one at a time, respecting dependencies."""
        completed: Dict[str, Task] = {}
        results: List[Task] = []

        for task in tasks:
            # Check dependencies
            deps_ok = True
            for dep_id in task.depends_on:
                if dep_id not in completed:
                    task.status = TaskStatus.SKIPPED
                    task.error = f"Dependency '{dep_id}' not found in completed tasks"
                    results.append(task)
                    deps_ok = False
                    break
                if completed[dep_id].status == TaskStatus.FAILED:
                    task.status = TaskStatus.SKIPPED
                    task.error = f"Dependency '{dep_id}' failed"
                    results.append(task)
                    deps_ok = False
                    break
            if not deps_ok:
                continue

            task = self._execute_task(task)
            completed[task.id] = task
            results.append(task)

        return results

    def run_parallel(self, tasks: List[Task]) -> List[Task]:
        """Run independent tasks in parallel using a thread pool.

        Tasks with dependencies are run after their dependencies complete.
        Independent tasks are submitted concurrently (up to max_workers).
        """
        # Separate tasks by dependency level
        independent = [t for t in tasks if not t.depends_on]
        dependent = [t for t in tasks if t.depends_on]

        results: List[Task] = []

        # Phase 1: Run all independent tasks in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_map = {
                executor.submit(self._execute_task, task): task
                for task in independent
            }
            for future in concurrent.futures.as_completed(future_map):
                task = future.result()
                results.append(task)

        # Phase 2: Run dependent tasks sequentially (they may depend on phase 1 results)
        if dependent:
            # Rebuild completed map from phase 1
            completed = {t.id: t for t in results}
            for task in dependent:
                deps_ok = True
                for dep_id in task.depends_on:
                    if dep_id not in completed:
                        task.status = TaskStatus.SKIPPED
                        task.error = f"Dependency '{dep_id}' not found"
                        results.append(task)
                        deps_ok = False
                        break
                    if completed[dep_id].status == TaskStatus.FAILED:
                        task.status = TaskStatus.SKIPPED
                        task.error = f"Dependency '{dep_id}' failed"
                        results.append(task)
                        deps_ok = False
                        break
                if not deps_ok:
                    continue
                task = self._execute_task(task)
                completed[task.id] = task
                results.append(task)

        return results

    def run_with_topology(self, tasks: List[Task]) -> List[Task]:
        """Run tasks with full topology-aware parallel execution.

        Groups tasks into levels based on dependency depth, then runs
        each level in parallel before proceeding to the next level.
        """
        if not tasks:
            return []

        task_map = {t.id: t for t in tasks}

        # Calculate depth for each task
        def get_depth(task: Task, visited: Optional[set] = None) -> int:
            if visited is None:
                visited = set()
            if task.id in visited:
                return 0  # Circular dependency, break
            visited.add(task.id)
            if not task.depends_on:
                return 0
            max_dep = 0
            for dep_id in task.depends_on:
                dep_task = task_map.get(dep_id)
                if dep_task:
                    max_dep = max(max_dep, get_depth(dep_task, visited.copy()))
            return max_dep + 1

        # Group by depth
        levels: Dict[int, List[Task]] = {}
        for task in tasks:
            depth = get_depth(task)
            levels.setdefault(depth, []).append(task)

        all_results: List[Task] = []
        completed: Dict[str, Task] = {}

        for depth in sorted(levels.keys()):
            level_tasks = levels[depth]

            for task in level_tasks:
                # Verify dependencies are completed
                deps_ok = True
                for dep_id in task.depends_on:
                    if dep_id not in completed or completed[dep_id].status == TaskStatus.FAILED:
                        task.status = TaskStatus.SKIPPED
                        task.error = f"Dependency '{dep_id}' failed or missing"
                        deps_ok = False
                        break
                if not deps_ok:
                    all_results.append(task)
                    completed[task.id] = task
                    continue

            # Filter out already-skipped tasks
            ready = [t for t in level_tasks if t.status == TaskStatus.PENDING]

            if len(ready) <= 1:
                for task in ready:
                    task = self._execute_task(task)
                    completed[task.id] = task
                    all_results.append(task)
            else:
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    future_map = {
                        executor.submit(self._execute_task, task): task
                        for task in ready
                    }
                    for future in concurrent.futures.as_completed(future_map):
                        task = future.result()
                        completed[task.id] = task
                        all_results.append(task)

        return all_results

    def print_summary(self, tasks: List[Task]) -> None:
        """Print a human-readable summary of task execution results."""
        total = len(tasks)
        succeeded = sum(1 for t in tasks if t.status == TaskStatus.SUCCESS)
        failed = sum(1 for t in tasks if t.status == TaskStatus.FAILED)
        skipped = sum(1 for t in tasks if t.status == TaskStatus.SKIPPED)
        total_ms = sum(t.duration_ms for t in tasks)

        print(f"\n{'='*60}")
        print(f"Task Execution Summary: {succeeded}/{total} succeeded, "
              f"{failed} failed, {skipped} skipped")
        print(f"Total wall time: {total_ms:.0f}ms")
        print(f"{'='*60}")

        for task in tasks:
            icon = "✓" if task.status == TaskStatus.SUCCESS else \
                   "✗" if task.status == TaskStatus.FAILED else \
                   "○" if task.status == TaskStatus.SKIPPED else "…"
            print(f"  {icon} {task.id} [{task.status.value}] ({task.duration_ms:.0f}ms)")
            if task.error:
                print(f"    Error: {task.error}")
            elif task.result:
                # Print a compact result summary
                data = task.result.get("data", task.result)
                if isinstance(data, dict):
                    if "count" in data:
                        print(f"    Count: {data['count']}")
                    if "list" in data:
                        print(f"    Items: {len(data['list'])}")
                elif isinstance(data, list):
                    print(f"    Items: {len(data)}")


# ============================================================
# Pre-defined Recipes (Multi-Agent Patterns)
# ============================================================

class Recipes:
    """Collection of pre-defined multi-agent task recipes."""

    @staticmethod
    def store_inventory_sync(
        product_status: Optional[int] = None,
        sale_status: int = 2,
    ) -> List[Task]:
        """Full inventory sync: query stores, products, and orders in parallel.

        Pattern: Parallel store/product/order discovery, then sequential processing.

        This is the foundation recipe. After getting results, you can:
        - Compare with external ERP data
        - Identify discrepancies
        - Trigger stock updates
        """
        return [
            Task(
                id="query_stores",
                description="Query all authorized Xianyu stores to get store list and capabilities",
                method="query_stores",
                agent_role="leaf",
            ),
            Task(
                id="query_products",
                description="Query all products (paginated) to get full inventory snapshot",
                method="query_all_products",
                kwargs={"product_status": product_status, "sale_status": sale_status},
                agent_role="leaf",
            ),
            Task(
                id="query_orders",
                description="Query all orders (paginated) to get order snapshot",
                method="query_all_orders",
                kwargs={"order_status": None, "refund_status": None},
                agent_role="leaf",
            ),
        ]

    @staticmethod
    def product_listing_pipeline(
        store_user_name: str,
        products: List[Dict[str, Any]],
    ) -> List[Task]:
        """Batch create products then publish them.

        Pattern: Phase 1 (batch create) → Phase 2 (parallel publish).

        Args:
            store_user_name: 闲鱼会员名 to publish to
            products: List of product data dicts (same format as create_product params)
        """
        create_task = Task(
            id="batch_create",
            description=f"Batch create {len(products)} products",
            method="batch_create_products",
            kwargs={"product_data": products},
            agent_role="leaf",
        )

        # Publish tasks depend on batch_create — they can run in parallel
        # after the batch create returns product IDs
        # Note: actual product IDs come from batch_create result,
        # so in practice you'd parse the result and create publish tasks.
        publish_task = Task(
            id="publish_all",
            description=f"Publish all created products to store '{store_user_name}'",
            method="publish_product",  # placeholder — real impl parses batch result
            kwargs={"user_name": [store_user_name]},
            depends_on=["batch_create"],
            agent_role="leaf",
        )

        return [create_task, publish_task]

    @staticmethod
    def order_processing_pipeline(
        order_no: str,
        waybill_no: str,
        express_code: str,
        express_name: str,
    ) -> List[Task]:
        """Query order detail, then ship it.

        Pattern: Sequential pipeline (detail → ship).
        """
        return [
            Task(
                id="get_order_detail",
                description=f"Get full details for order {order_no}",
                method="query_order_detail",
                kwargs={"order_no": order_no},
                agent_role="leaf",
            ),
            Task(
                id="ship_order",
                description=f"Ship order {order_no} via {express_name} ({waybill_no})",
                method="ship_order",
                kwargs={
                    "order_no": order_no,
                    "waybill_no": waybill_no,
                    "express_code": express_code,
                    "express_name": express_name,
                },
                depends_on=["get_order_detail"],
                agent_role="leaf",
            ),
        ]

    @staticmethod
    def category_discovery(
        item_biz_types: Optional[List[int]] = None,
        sp_biz_types: Optional[List[int]] = None,
    ) -> List[Task]:
        """Parallel category and attribute discovery for multiple product types.

        Pattern: Parallel queries across different item_biz_type × sp_biz_type combos.
        Results can be cached for subsequent product creation.
        """
        if item_biz_types is None:
            item_biz_types = [2]  # Default: 普通商品
        if sp_biz_types is None:
            sp_biz_types = [1, 2, 3, 9]  # Common: 手机, 潮品, 家电, 3C数码

        tasks = []
        for item_type in item_biz_types:
            for sp_type in sp_biz_types:
                tasks.append(Task(
                    id=f"categories_{item_type}_{sp_type}",
                    description=f"Query categories for item_biz_type={item_type}, sp_biz_type={sp_type}",
                    method="query_categories",
                    kwargs={"item_biz_type": item_type, "sp_biz_type": sp_type},
                    agent_role="leaf",
                ))
        return tasks

    @staticmethod
    def multi_store_batch_publish(
        product_ids: List[int],
        store_names: List[str],
    ) -> List[Task]:
        """Publish products to multiple stores in parallel.

        Pattern: Parallel publishing across stores.

        Args:
            product_ids: List of product IDs to publish
            store_names: List of 闲鱼会员名 (one per store)
        """
        tasks = []
        for i, (pid, store) in enumerate(zip(product_ids, store_names)):
            tasks.append(Task(
                id=f"publish_{pid}",
                description=f"Publish product {pid} to store '{store}'",
                method="publish_product",
                kwargs={"product_id": pid, "user_name": [store]},
                agent_role="leaf",
            ))
        return tasks

    @staticmethod
    def multi_store_inventory_sync(
        store_product_map: Dict[str, List[int]],
    ) -> List[Task]:
        """Query product details across multiple stores in parallel.

        Pattern: Parallel detail queries grouped by store.

        Args:
            store_product_map: {store_name: [product_ids]}
        """
        tasks = []
        for store, product_ids in store_product_map.items():
            for pid in product_ids:
                tasks.append(Task(
                    id=f"detail_{pid}",
                    description=f"Query product detail for ID {pid} (store: {store})",
                    method="query_product_detail",
                    kwargs={"product_id": pid},
                    store_filter=store,
                    agent_role="leaf",
                ))
        return tasks

    @staticmethod
    def bulk_order_shipment(
        shipments: List[Dict[str, Any]],
    ) -> List[Task]:
        """Ship multiple orders in parallel.

        Pattern: Parallel order shipping (each order is independent).

        Args:
            shipments: List of {order_no, waybill_no, express_code, express_name, ...}
        """
        tasks = []
        for s in shipments:
            tasks.append(Task(
                id=f"ship_{s['order_no']}",
                description=f"Ship order {s['order_no']} via {s['express_name']}",
                method="ship_order",
                kwargs={
                    "order_no": s["order_no"],
                    "waybill_no": s["waybill_no"],
                    "express_code": s["express_code"],
                    "express_name": s["express_name"],
                },
                agent_role="leaf",
            ))
        return tasks

    @staticmethod
    def daily_health_check() -> List[Task]:
        """Daily check: stores, express companies, and recent orders.

        Pattern: Parallel health check across independent domains.
        """
        import time as _time
        now = int(_time.time())
        six_months_ago = now - 180 * 24 * 3600

        return [
            Task(
                id="health_stores",
                description="Check all authorized stores are valid and active",
                method="query_stores",
                agent_role="leaf",
            ),
            Task(
                id="health_express",
                description="Check available express companies",
                method="query_express_companies",
                agent_role="leaf",
            ),
            Task(
                id="health_recent_orders",
                description="Check recent orders in the last 7 days",
                method="query_orders",
                kwargs={
                    "update_time": [now - 7 * 24 * 3600, now],
                    "page_size": 10,
                },
                agent_role="leaf",
            ),
            Task(
                id="health_recent_products",
                description="Check recently modified products",
                method="query_products",
                kwargs={
                    "update_time": [six_months_ago, now],
                    "page_size": 10,
                },
                agent_role="leaf",
            ),
        ]


# ============================================================
# CLI
# ============================================================

RECIPE_MAP: Dict[str, Callable[[], List[Task]]] = {
    "inventory-sync": Recipes.store_inventory_sync,
    "health-check": Recipes.daily_health_check,
}

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="闲管家 Multi-Agent Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available recipes:
  inventory-sync   Parallel store + product + order snapshot
  health-check     Daily health check across stores/express/orders/products
        """.strip(),
    )
    parser.add_argument("--app-key", help="AppKey")
    parser.add_argument("--app-secret", help="AppSecret")
    parser.add_argument("--recipe", choices=list(RECIPE_MAP.keys()),
                        help="Pre-defined recipe to run")
    parser.add_argument("--max-workers", type=int, default=5,
                        help="Max parallel workers (default: 5)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print task list without executing")

    args = parser.parse_args()

    if not args.recipe:
        parser.print_help()
        sys.exit(0)

    # Build tasks
    recipe_fn = RECIPE_MAP[args.recipe]
    tasks = recipe_fn()

    if args.dry_run:
        print(f"Recipe: {args.recipe}")
        print(f"Tasks ({len(tasks)}):")
        for task in tasks:
            deps = f" (depends: {', '.join(task.depends_on)})" if task.depends_on else ""
            print(f"  - {task.id}: {task.description}{deps}")
        sys.exit(0)

    # Execute
    try:
        client = GoofishClient(app_key=args.app_key, app_secret=args.app_secret)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    runner = TaskRunner(client, max_workers=args.max_workers)
    results = runner.run_parallel(tasks)
    runner.print_summary(results)

    # Exit code based on failures
    failed = sum(1 for t in results if t.status == TaskStatus.FAILED)
    sys.exit(1 if failed > 0 else 0)
