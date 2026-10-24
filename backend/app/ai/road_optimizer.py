"""Verified allowlisted-Valhalla time-matrix optimization of 2–6 database POIs.

Uses one fixed public HTTPS demo or explicitly configured localhost service.
No public routing endpoint or invented road distance is used.
"""
import json
import logging
import math
import os
import socket
import ssl
from itertools import permutations
from urllib.error import HTTPError, URLError
from urllib.request import Request

from .valhalla_config import valhalla_root, request_opener
from .itinerary_geo_service import fetch_candidates, valhalla_route

logger = logging.getLogger(__name__)

MATRIX_REQUEST_TIMEOUT_SECONDS = 35
MAX_MATRIX_RESPONSE_BYTES = 2_000_000


class MatrixRoutingError(RuntimeError):
    """Safe, actionable matrix failure suitable for an API message."""


def optimize_fixed_first(times):
    n = len(times)
    if not 2 <= n <= 6 or any(len(row) != n for row in times):
        raise ValueError("Invalid routing matrix dimensions")
    for i, row in enumerate(times):
        for j, cell in enumerate(row):
            if (not isinstance(cell, (int, float)) or isinstance(cell, bool)
                    or not math.isfinite(cell) or cell < 0
                    or (i != j and cell <= 0)):
                raise ValueError("Missing/unreachable road travel cost")

    def cost(seq):
        return sum(times[a][b] for a, b in zip(seq, seq[1:]))

    original = tuple(range(n))
    best = min(((0,) + tail for tail in permutations(range(1, n))),
               key=lambda seq: (cost(seq), seq))
    return best, cost(original), cost(best)


def _get_matrix(places, mode, root):
    """Fetch and validate a Valhalla time matrix with actionable failures."""
    positions = [{"lat": p["lat"], "lon": p["lng"]} for p in places]
    payload = {
        "sources": positions,
        "targets": positions,
        "costing": mode,
        "units": "kilometers",
    }
    req = Request(
        root + "/sources_to_targets",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with request_opener().open(
            req, timeout=MATRIX_REQUEST_TIMEOUT_SECONDS
        ) as resp:
            raw = resp.read(MAX_MATRIX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        logger.warning("Valhalla matrix HTTP error: status=%s", exc.code)
        raise MatrixRoutingError(
            f"Valhalla 时间矩阵服务返回 HTTP {exc.code}"
        ) from exc
    except URLError as exc:
        reason = exc.reason
        if isinstance(reason, (TimeoutError, socket.timeout)):
            logger.warning("Valhalla matrix request timed out")
            raise MatrixRoutingError(
                "Valhalla 时间矩阵请求超时；请稍后重试"
            ) from exc
        if isinstance(reason, ssl.SSLError):
            logger.warning(
                "Valhalla matrix TLS failure: %s", type(reason).__name__
            )
            raise MatrixRoutingError(
                "Valhalla 时间矩阵 TLS/证书连接失败；请检查后端网络环境"
            ) from exc
        logger.warning(
            "Valhalla matrix connection failure: reason_type=%s",
            type(reason).__name__,
        )
        raise MatrixRoutingError(
            "Valhalla 时间矩阵网络连接失败；请检查后端网络并查看服务日志"
        ) from exc
    except (TimeoutError, socket.timeout):
        logger.warning("Valhalla matrix request timed out")
        raise MatrixRoutingError(
            "Valhalla 时间矩阵请求超时；请稍后重试"
        ) from None
    except ssl.SSLError as exc:
        logger.warning(
            "Valhalla matrix TLS failure: %s", type(exc).__name__
        )
        raise MatrixRoutingError(
            "Valhalla 时间矩阵 TLS/证书连接失败；请检查后端网络环境"
        ) from exc
    except OSError as exc:
        logger.warning(
            "Valhalla matrix I/O failure: %s", type(exc).__name__
        )
        raise MatrixRoutingError(
            "Valhalla 时间矩阵网络连接失败；请检查后端网络并查看服务日志"
        ) from exc

    if len(raw) > MAX_MATRIX_RESPONSE_BYTES:
        raise MatrixRoutingError("Valhalla 时间矩阵响应超过大小限制")

    try:
        document = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("Valhalla matrix returned invalid JSON")
        raise MatrixRoutingError("Valhalla 时间矩阵返回了无效 JSON") from exc

    rows = document.get("sources_to_targets") if isinstance(document, dict) else None
    n = len(places)
    if not isinstance(rows, list) or len(rows) != n:
        raise MatrixRoutingError("Valhalla 时间矩阵缺失或行数不正确")

    times = []
    for i, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != n:
            raise MatrixRoutingError("Valhalla 时间矩阵列数不正确")
        time_row = []
        for j, cell in enumerate(row):
            value = cell.get("time") if isinstance(cell, dict) else None
            if (not isinstance(value, (int, float)) or isinstance(value, bool)
                    or not math.isfinite(value) or value < 0
                    or (i != j and value <= 0)):
                logger.warning(
                    "Valhalla matrix has missing/unreachable time cell: from=%s to=%s",
                    i, j,
                )
                raise MatrixRoutingError(
                    "道路时间矩阵包含不可达或缺少有效时间的景点组合"
                )
            time_row.append(value)
        times.append(time_row)

    return times


def plan_verified_route(place_ids, mode="pedestrian", optimize=False):
    if mode not in ("pedestrian", "bicycle", "auto"):
        raise ValueError("Invalid travel mode")
    if not 2 <= len(place_ids) <= 6 or any(type(i) is not int or i <= 0 for i in place_ids):
        raise ValueError("Select 2–6 valid POI IDs")
    if len(set(place_ids)) != len(place_ids):
        raise ValueError("Duplicate POI ID")

    candidates = {p["id"]: p for p in fetch_candidates()}
    if any(i not in candidates for i in place_ids):
        raise LookupError("POI ID not found in current database")
    places = [candidates[i] for i in place_ids]
    root = valhalla_root()
    if not root:
        return {
            "status": "unavailable",
            "message": "VALHALLA_URL 不在允许的地址列表中；保留直线预览",
        }

    original_seconds = optimized_seconds = None
    if optimize and len(places) >= 3:
        try:
            matrix = _get_matrix(places, mode, root)
            order, original_seconds, optimized_seconds = optimize_fixed_first(matrix)
            places = [places[i] for i in order]
        except MatrixRoutingError as exc:
            logger.warning("Road route optimization unavailable: %s", exc)
            return {
                "status": "unavailable",
                "message": f"{exc}；未更改原路线",
            }
        except ValueError as exc:
            logger.warning("Invalid Valhalla matrix: %s", exc)
            return {
                "status": "unavailable",
                "message": "道路时间矩阵包含无效或不可达的景点组合；未更改原路线",
            }
        except Exception:
            logger.exception("Unexpected error during Valhalla matrix optimization")
            return {
                "status": "unavailable",
                "message": "道路时间矩阵计算发生未预期错误；请检查后端日志，原路线未更改",
            }

    route = valhalla_route(places, mode=mode, endpoint=root)
    if route.get("status") != "verified_by_routing_service":
        return {
            "status": "unavailable",
            "message": "道路服务未返回有效路线；保留直线预览",
        }

    route["ordered_place_ids"] = [p["id"] for p in places]
    route["optimized"] = original_seconds is not None
    if original_seconds is not None:
        route["original_matrix_minutes"] = round(original_seconds / 60, 1)
        route["optimized_matrix_minutes"] = round(optimized_seconds / 60, 1)
        route["matrix_minutes_saved_estimate"] = round(
            max(0, original_seconds - optimized_seconds) / 60, 1
        )
    route["limitations"] = (
        "道路时间为Valhalla路网估算，非实时导航；"
        "矩阵时间与路线分段估算可能不同"
    )
    return route
