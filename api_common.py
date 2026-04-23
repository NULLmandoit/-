"""共享 API 异常与错误响应结构，供日前优化与窗口优化模块共用。"""


class AlgorithmAPIError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, details: dict | None = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


def build_error_response(code: str, message: str, details: dict | None = None):
    return {"success": False, "error": {"code": code, "message": message, "details": details or {}}}
