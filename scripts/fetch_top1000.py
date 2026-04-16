#!/usr/bin/env python3
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib import error, parse, request


API_BASE = "https://matrix.sbapis.com/b/tiktok/top"


class ApiRequestError(RuntimeError):
    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_url(query: str, page: int) -> str:
    encoded = parse.urlencode({"query": query, "page": page})
    return f"{API_BASE}?{encoded}"


def request_page(
    *,
    query: str,
    page: int,
    client_id: str,
    token: str,
    timeout_seconds: int,
    max_retries: int,
) -> Dict[str, Any]:
    url = build_url(query, page)
    headers = {
        "clientid": client_id,
        "token": token,
        "accept": "application/json",
    }

    for attempt in range(1, max_retries + 1):
        req = request.Request(url, headers=headers, method="GET")
        try:
            with request.urlopen(req, timeout=timeout_seconds) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except error.HTTPError as exc:
            if attempt == max_retries:
                raise ApiRequestError(
                    f"请求失败 page={page}, attempt={attempt}, status={exc.code}, error={exc}",
                    status_code=exc.code,
                ) from exc
            sleep_seconds = min(2 ** (attempt - 1), 8)
            time.sleep(sleep_seconds)
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt == max_retries:
                raise ApiRequestError(
                    f"请求失败 page={page}, attempt={attempt}, error={exc}"
                ) from exc
            sleep_seconds = min(2 ** (attempt - 1), 8)
            time.sleep(sleep_seconds)

    raise RuntimeError(f"请求失败 page={page}")


def deep_get(data: Dict[str, Any], path: List[str], default: Any = None) -> Any:
    node: Any = data
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    return node


def normalize_record(item: Dict[str, Any], page: int, captured_at: str) -> Dict[str, Any]:
    user_id = deep_get(item, ["id", "id"])
    username = deep_get(item, ["id", "username"])

    return {
        "uid": user_id,
        "username": username,
        "display_name": deep_get(item, ["id", "display_name"]),
        "avatar_url": deep_get(item, ["general", "branding", "avatar"]),
        "followers": deep_get(item, ["statistics", "total", "followers"], 0),
        "following": deep_get(item, ["statistics", "total", "following"], 0),
        "likes": deep_get(item, ["statistics", "total", "likes"], 0),
        "uploads": deep_get(item, ["statistics", "total", "uploads"], 0),
        "rank_followers": deep_get(item, ["ranks", "followers"]),
        "rank_likes": deep_get(item, ["ranks", "likes"]),
        "rank_uploads": deep_get(item, ["ranks", "uploads"]),
        "source_page": page,
        "captured_at": captured_at,
    }


def unique_key(record: Dict[str, Any]) -> Optional[str]:
    uid = record.get("uid")
    username = record.get("username")
    if uid:
        return str(uid)
    if username:
        return f"username:{username}"
    return None


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def sort_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def sort_key(rec: Dict[str, Any]) -> Tuple[int, int]:
        rank = rec.get("rank_followers")
        if isinstance(rank, int):
            return (0, rank)
        followers = rec.get("followers") or 0
        return (1, -int(followers))

    return sorted(records, key=sort_key)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="抓取 TikTok Top1000 达人数据并生成 JSON")
    parser.add_argument("--query", default="followers", help="排序字段，默认 followers")
    parser.add_argument("--limit", type=int, default=1000, help="目标条数，默认 1000")
    parser.add_argument("--start-page", type=int, default=0, help="起始页，默认 0")
    parser.add_argument("--max-pages", type=int, default=1000, help="最多拉取页数，默认 1000")
    parser.add_argument("--timeout", type=int, default=20, help="单请求超时秒数")
    parser.add_argument("--retries", type=int, default=3, help="失败重试次数")
    parser.add_argument("--raw-dir", default="data/raw", help="raw 数据目录")
    parser.add_argument("--output", default="data/top1000.json", help="汇总 JSON 路径")
    parser.add_argument(
        "--clientid",
        default=os.getenv("CLIENT_ID", ""),
        help="API clientid，默认读取环境变量 CLIENT_ID",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("TOKEN", ""),
        help="API token，默认读取环境变量 TOKEN",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.clientid or not args.token:
        print("缺少凭证：请设置 CLIENT_ID / TOKEN 或通过 --clientid --token 传入", file=sys.stderr)
        return 1

    raw_dir = Path(args.raw_dir)
    output_path = Path(args.output)
    captured_at = utc_now()

    unique_records: List[Dict[str, Any]] = []
    seen = set()
    duplicates = 0
    pages_fetched = 0

    stop_reason = "completed"

    for page in range(args.start_page, args.start_page + args.max_pages):
        try:
            payload = request_page(
                query=args.query,
                page=page,
                client_id=args.clientid,
                token=args.token,
                timeout_seconds=args.timeout,
                max_retries=args.retries,
            )
        except ApiRequestError as exc:
            if exc.status_code == 402:
                stop_reason = "api_quota_or_payment_required"
                print(f"停止抓取：page={page} 返回 402（额度或计费限制）")
                break
            if unique_records:
                stop_reason = f"request_error_after_partial_data:{exc}"
                print(f"停止抓取：{exc}")
                break
            raise
        pages_fetched += 1

        page_file = raw_dir / f"page-{page:04d}.json"
        write_json(
            page_file,
            {
                "captured_at": captured_at,
                "query": args.query,
                "page": page,
                "response": payload,
            },
        )

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list) or len(data) == 0:
            stop_reason = "no_more_data"
            print(f"停止抓取：page={page} 无数据")
            break

        for item in data:
            if not isinstance(item, dict):
                continue
            rec = normalize_record(item, page, captured_at)
            key = unique_key(rec)
            if key is None:
                continue
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            unique_records.append(rec)

            if len(unique_records) >= args.limit:
                break

        print(f"page={page} 完成，累计唯一记录={len(unique_records)}")
        if len(unique_records) >= args.limit:
            stop_reason = "limit_reached"
            break

    ordered = sort_records(unique_records)[: args.limit]
    followers_missing = sum(1 for r in ordered if r.get("followers") in (None, ""))
    likes_missing = sum(1 for r in ordered if r.get("likes") in (None, ""))

    result = {
        "meta": {
            "generated_at": captured_at,
            "query": args.query,
            "target_limit": args.limit,
            "record_count": len(ordered),
            "pages_fetched": pages_fetched,
            "duplicate_count": duplicates,
            "stop_reason": stop_reason,
            "missing_rate": {
                "followers": round(followers_missing / len(ordered), 4) if ordered else 0,
                "likes": round(likes_missing / len(ordered), 4) if ordered else 0,
            },
        },
        "records": ordered,
    }
    write_json(output_path, result)

    print("写入完成：")
    print(f"- 汇总文件: {output_path}")
    print(f"- 记录条数: {len(ordered)}")
    print(f"- 抓取页数: {pages_fetched}")
    print(f"- 去重数量: {duplicates}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
