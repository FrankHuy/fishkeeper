#!/usr/bin/env python3
"""
闲管家 Open Platform — Signer Utility

Implements the MD5-based request signing algorithm for the Goofish API.

Algorithm:
    body_md5 = md5(json_body_string)
    sign = md5(f"{app_key},{body_md5},{timestamp},{app_secret}")

For business partner integrations (with seller_id):
    sign = md5(f"{app_key},{body_md5},{timestamp},{seller_id},{app_secret}")

Usage:
    from signer import GoofishSigner
    signer = GoofishSigner(app_key="...", app_secret="...")
    params = signer.sign(body={"product_id": 123})
    # params = {"appid": "...", "timestamp": 1690366883, "sign": "..."}
"""

import hashlib
import json
import time
from typing import Any, Dict, Optional


class GoofishSigner:
    """Generate signed query parameters for Goofish API requests."""

    def __init__(self, app_key: str, app_secret: str):
        """
        Args:
            app_key: 开放平台的AppKey
            app_secret: 开放平台的AppSecret
        """
        if not app_key or not app_secret:
            raise ValueError("app_key and app_secret are required")
        self.app_key = app_key
        # Strip common prefix if the secret value was copied with the field name
        # e.g. "AppSecretRreMzuz..." -> "RreMzuz..."
        if app_secret.startswith("AppSecret") and len(app_secret) > len("AppSecret"):
            app_secret = app_secret[len("AppSecret"):]
        self.app_secret = app_secret

    def _compute_body_md5(self, body: Optional[Dict[str, Any]] = None) -> str:
        """Compute MD5 of the JSON request body.

        For requests without a body, use md5("{}") per the API spec.
        """
        if body is None or len(body) == 0:
            body_str = "{}"
        else:
            body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        return hashlib.md5(body_str.encode("utf-8")).hexdigest()

    def sign(
        self,
        body: Optional[Dict[str, Any]] = None,
        timestamp: Optional[int] = None,
        seller_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate signed query parameters.

        Args:
            body: JSON request body dict. None or {} for empty body.
            timestamp: Unix timestamp in seconds. Auto-generated if None.
            seller_id: 商家ID, only for business partner integrations.

        Returns:
            Dict with 'appid', 'timestamp', 'sign', and optionally 'seller_id'.
        """
        if timestamp is None:
            timestamp = int(time.time())

        body_md5 = self._compute_body_md5(body)

        if seller_id:
            sign_str = f"{self.app_key},{body_md5},{timestamp},{seller_id},{self.app_secret}"
        else:
            sign_str = f"{self.app_key},{body_md5},{timestamp},{self.app_secret}"

        sign = hashlib.md5(sign_str.encode("utf-8")).hexdigest()

        params: Dict[str, Any] = {
            "appid": self.app_key,
            "timestamp": timestamp,
            "sign": sign,
        }
        if seller_id:
            params["seller_id"] = seller_id

        return params

    def sign_headers(
        self,
        body: Optional[Dict[str, Any]] = None,
        timestamp: Optional[int] = None,
        seller_id: Optional[str] = None,
    ) -> Dict[str, str]:
        """Generate signed query parameters as string dict (for requests library)."""
        params = self.sign(body=body, timestamp=timestamp, seller_id=seller_id)
        return {k: str(v) for k, v in params.items()}


# Standalone CLI
if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Goofish API Signer")
    parser.add_argument("--app-key", help="AppKey (or set GOOFISH_APP_KEY env)")
    parser.add_argument("--app-secret", help="AppSecret (or set GOOFISH_APP_SECRET env)")
    parser.add_argument("--body", default="{}", help="JSON body string (default: '{}')")
    parser.add_argument("--timestamp", type=int, help="Unix timestamp in seconds")
    parser.add_argument("--seller-id", help="Seller ID for business partner integrations")

    args = parser.parse_args()

    app_key = args.app_key or os.environ.get("GOOFISH_APP_KEY", "")
    app_secret = args.app_secret or os.environ.get("GOOFISH_APP_SECRET", "")

    if not app_key or not app_secret:
        parser.error("app_key and app_secret are required (--app-key/--app-secret or env vars)")

    body = json.loads(args.body) if args.body else None
    signer = GoofishSigner(app_key=app_key, app_secret=app_secret)
    params = signer.sign(body=body, timestamp=args.timestamp, seller_id=args.seller_id)

    print(json.dumps(params, indent=2))
