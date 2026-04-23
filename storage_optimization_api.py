"""
储能优化 HTTP 入口：装配 FastAPI 应用、异常处理与路由。

业务逻辑位于 `storage_optimization` 包内；本模块保持与历史一致的对外符号导出。
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api_common import AlgorithmAPIError, build_error_response

from storage_optimization.constants import API_HOST, API_PORT
from storage_optimization.core import make_json_safe
from storage_optimization.dayahead import run_optimization
from storage_optimization.legacy_window import window_app
from storage_optimization.models import OptimizeRequest, RollingOptimizeRequest
from storage_optimization.rolling_pipeline import run_rolling_optimization
from storage_optimization.se_client import (
    QUERY_MARKET_PRICE_URL,
    load_price_from_api,
    merge_rolling_prices_15m,
)
from storage_optimization.query_time import query_time_to_start_hour, rolling_start_hour_to_query_time

# 兼容旧代码：从本模块导入的符号
__all__ = [
    "app",
    "window_app",
    "AlgorithmAPIError",
    "build_error_response",
    "run_optimization",
    "run_rolling_optimization",
    "OptimizeRequest",
    "RollingOptimizeRequest",
    "load_price_from_api",
    "merge_rolling_prices_15m",
    "query_time_to_start_hour",
    "rolling_start_hour_to_query_time",
    "QUERY_MARKET_PRICE_URL",
    "API_HOST",
    "API_PORT",
    "make_json_safe",
]


app = FastAPI(
    title="Storage Optimization API",
    version="V1.3",
    description="日前全时段优化（连续块重排）；可选基线 SOC 修正，并返回 effective 基线与变更标记。默认端口 8001。",
    servers=[{"url": f"http://{API_HOST}:{API_PORT}", "description": "本地默认"}],
)


@app.exception_handler(AlgorithmAPIError)
async def algorithm_api_error_handler(_: Request, exc: AlgorithmAPIError):
    return JSONResponse(
        status_code=exc.status_code,
        content=build_error_response(exc.code, exc.message, exc.details),
    )


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=build_error_response(
            "REQUEST_VALIDATION_ERROR",
            "请求参数校验失败",
            {"errors": make_json_safe(jsonable_encoder(exc.errors(), custom_encoder={ValueError: str}))},
        ),
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(_: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content=build_error_response("INTERNAL_SERVER_ERROR", "服务内部错误", {"reason": str(exc)}),
    )


@app.get("/health")
async def health_check():
    return {"success": True, "code": "OK", "message": "service is healthy"}


@app.post("/storage-optimization/optimize")
async def optimize_endpoint(payload: OptimizeRequest):
    return run_optimization(payload)


@app.post("/storage-optimization/rolling-optimize")
async def rolling_optimize_endpoint(payload: RollingOptimizeRequest):
    return run_rolling_optimization(payload)


app.mount("", window_app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=API_HOST, port=API_PORT, reload=False)
