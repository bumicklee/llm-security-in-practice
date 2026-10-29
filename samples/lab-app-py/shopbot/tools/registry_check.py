"""모델에 넘기는 도구 이름이 모두 허용 목록(ToolAllowlist)에 있는지 시작할 때 확인한다(9장 9.5).

목록 밖 도구가 있으면 앱이 뜨지 않는다. 새 도구를 붙이려면 허용 목록과 권한 등급을 먼저 적어야 한다.
tools_allowlist_exclude(랩 시연용, 기본 비어 있음): 허용 목록에서 이름을 뺀 것처럼 검사한다(14-2 1단계). 실서비스에 쓰지 않는다.
"""
from labcore.tools import ToolAllowlist


class UnknownToolError(RuntimeError):
    pass


def unknown_tools(allowlist: ToolAllowlist, excluded, tools) -> list[str]:
    return [t.name for t in tools if not allowlist.allowed(t.name) or t.name in set(excluded)]


def verify_tool_allowlist(tools, excluded=()) -> None:
    unknown = unknown_tools(ToolAllowlist.lab(), excluded, tools)
    if unknown:
        raise UnknownToolError(f"허용 목록에 없는 도구: {unknown}")
