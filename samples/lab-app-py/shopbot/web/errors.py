"""방어가 막은 요청을 정해진 응답으로. 내부 사유는 짧은 코드로만 알린다."""
from fastapi import Request
from fastapi.responses import JSONResponse


class InputRejected(Exception):
    """입력 검사 실패 → 400."""

    def __init__(self, reason: str):
        super().__init__(f"input rejected: {reason}")
        self.reason = reason


class BudgetExceeded(Exception):
    """토큰 한도 초과 → 429."""

    def __init__(self, reason: str, remaining: int):
        super().__init__(f"budget exceeded: {reason}")
        self.reason = reason
        self.remaining = remaining


async def input_rejected_handler(request: Request, e: InputRejected):
    return JSONResponse(status_code=400, content={"error": "INPUT_REJECTED", "reason": e.reason,
                                                  "answer": "입력을 처리할 수 없습니다. 1,000자 이내로 다시 적어 주세요."})


async def budget_exceeded_handler(request: Request, e: BudgetExceeded):
    answer = ("질문과 대화 기록이 너무 깁니다. 새 대화로 짧게 다시 물어봐 주세요." if e.reason == "REQUEST_TOO_LARGE"
              else "오늘 사용 한도에 닿았습니다. 내일 다시 이용해 주세요.")
    return JSONResponse(status_code=429, content={"error": "TOKEN_BUDGET", "reason": e.reason,
                                                  "remainingTokens": e.remaining, "answer": answer})


async def internal_error_handler(request: Request, e: Exception):
    # 내부 예외의 글(스택·프롬프트 조각)을 밖으로 내보내지 않는다
    return JSONResponse(status_code=500, content={"error": "INTERNAL_ERROR", "status": 500, "path": request.url.path})
