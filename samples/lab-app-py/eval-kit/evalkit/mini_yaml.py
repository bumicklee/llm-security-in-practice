"""작은 YAML 부분 집합 읽기·쓰기 (외부 패키지 없이).

목적: PyYAML 없이도 시험 문제·설정 YAML을 읽는다. PyYAML이 깔려 있으면 그쪽을 쓴다.
대응 장: 3장(3.2 YAML 형식과 스키마 검사), 부록 A
지원하는 문법(시험 문제 파일은 이 안에서만 쓴다):
  - 들여쓰기 매핑 `key: value`, 목록 `- value`, 목록 안 매핑 `- key: value`
  - 스칼라: "큰따옴표"(JSON식 이스케이프), '작은따옴표', 정수, 실수, true/false, null/~
  - 흐름 목록 `[a, "b", 1]`, 흐름 매핑 `{a: 1}`(한 줄, 중첩 없음), 빈 `[]` `{}`
  - 블록 문자열 `|`, `|-`, `>`, `>-`
  - `#` 주석
지원하지 않는 것: 앵커·별칭(&, *), 태그(!!), 여러 문서(---), 여러 줄 흐름 표기.
값 안에 ': ' 나 ' #' 가 있으면 반드시 따옴표로 감싼다.
"""
import json
import re

try:  # PyYAML이 있으면 그쪽을 쓴다(결과는 같은 dict/list)
    import yaml as _pyyaml  # type: ignore
except ImportError:  # pragma: no cover - 환경에 따라 다름
    _pyyaml = None


class YamlError(ValueError):
    pass


_KEY = re.compile(r'^(?P<key>"(?:[^"\\]|\\.)*"|\'(?:[^\']|\'\')*\'|[^\s"\'#\-\[\]{}][^:#]*?|-[^\s:#][^:#]*?)\s*:(?:\s+|$)(?P<rest>.*)$')
_INT = re.compile(r"^[-+]?\d+$")
_FLOAT = re.compile(r"^[-+]?(\d+\.\d*|\.\d+|\d+)([eE][-+]?\d+)?$")


def _strip_comment(text):
    """따옴표 밖의 ' #' 뒤를 지운다."""
    out, quote, i = [], None, 0
    while i < len(text):
        ch = text[i]
        if quote:
            out.append(ch)
            if quote == '"' and ch == "\\" and i + 1 < len(text):
                out.append(text[i + 1])
                i += 1
            elif ch == quote:
                quote = None
        else:
            if ch in "\"'" and (not out or out[-1] in " [{,:"):
                quote = ch
            elif ch == "#" and (not out or out[-1] in " \t"):
                break
            out.append(ch)
        i += 1
    return "".join(out).rstrip()


def _split_flow(inner):
    items, buf, quote, depth = [], [], None, 0
    i = 0
    while i < len(inner):
        ch = inner[i]
        if quote:
            buf.append(ch)
            if quote == '"' and ch == "\\" and i + 1 < len(inner):
                buf.append(inner[i + 1])
                i += 1
            elif ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch in "[{":
            depth += 1
            buf.append(ch)
        elif ch in "]}":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            items.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        items.append(tail)
    return items


def _scalar(text, lineno):
    t = text.strip()
    if t == "":
        return None
    if t.startswith('"'):
        if not t.endswith('"') or len(t) < 2:
            raise YamlError(f"{lineno}행: 큰따옴표가 닫히지 않았습니다")
        try:
            return json.loads(t)
        except json.JSONDecodeError as exc:
            raise YamlError(f"{lineno}행: 큰따옴표 문자열 오류 ({exc.msg})") from None
    if t.startswith("'"):
        if not t.endswith("'") or len(t) < 2:
            raise YamlError(f"{lineno}행: 작은따옴표가 닫히지 않았습니다")
        return t[1:-1].replace("''", "'")
    if t.startswith("["):
        if not t.endswith("]"):
            raise YamlError(f"{lineno}행: 흐름 목록은 한 줄로 닫아야 합니다")
        return [_scalar(x, lineno) for x in _split_flow(t[1:-1])]
    if t.startswith("{"):
        if not t.endswith("}"):
            raise YamlError(f"{lineno}행: 흐름 매핑은 한 줄로 닫아야 합니다")
        out = {}
        for part in _split_flow(t[1:-1]):
            m = _KEY.match(part)
            if not m:
                raise YamlError(f"{lineno}행: 흐름 매핑 항목 오류: {part}")
            out[_scalar(m.group("key"), lineno)] = _scalar(m.group("rest"), lineno)
        return out
    if t in ("~", "null", "Null", "NULL"):
        return None
    if t in ("true", "True", "TRUE"):
        return True
    if t in ("false", "False", "FALSE"):
        return False
    if t[0] in "&*!|>@`%":
        raise YamlError(f"{lineno}행: 지원하지 않는 문법입니다: {t[:20]}")
    if _INT.match(t):
        return int(t)
    if _FLOAT.match(t):
        return float(t)
    return t


class _Parser:
    def __init__(self, text):
        self.lines = text.replace("\t", "    ").split("\n")
        self.i = 0

    def _next_content(self):
        """다음 내용 줄로 이동하고 (들여쓰기, 내용)을 돌려준다. 없으면 None."""
        while self.i < len(self.lines):
            raw = self.lines[self.i]
            stripped = raw.strip()
            if stripped == "" or stripped.startswith("#"):
                self.i += 1
                continue
            if stripped == "---" and self.i == 0:
                self.i += 1
                continue
            return len(raw) - len(raw.lstrip(" ")), stripped
        return None

    def parse(self):
        nxt = self._next_content()
        if nxt is None:
            return None
        value = self._block(nxt[0])
        if self._next_content() is not None:
            raise YamlError(f"{self.i + 1}행: 들여쓰기가 맞지 않습니다")
        return value

    def _block(self, indent):
        nxt = self._next_content()
        if nxt is None:
            return None
        ind, content = nxt
        if content == "-" or content.startswith("- "):
            return self._seq(ind)
        return self._map(ind)

    def _block_scalar(self, style, parent_indent):
        self.i += 1
        lines, block_indent = [], None
        while self.i < len(self.lines):
            raw = self.lines[self.i]
            if raw.strip() == "":
                lines.append("")
                self.i += 1
                continue
            ind = len(raw) - len(raw.lstrip(" "))
            if ind <= parent_indent:
                break
            if block_indent is None:
                block_indent = ind
            lines.append(raw[block_indent:])
            self.i += 1
        while lines and lines[-1] == "":
            lines.pop()
        if style.startswith(">"):
            text = " ".join(l for l in lines if l != "")
        else:
            text = "\n".join(lines)
        return text if style.endswith("-") else text + "\n"

    def _value_after_key(self, rest, indent, lineno):
        rest = _strip_comment(rest)
        if rest in ("|", "|-", ">", ">-"):
            return self._block_scalar(rest, indent)
        self.i += 1
        if rest == "":
            nxt = self._next_content()
            if nxt is None:
                return None
            ind, content = nxt
            if ind > indent:
                return self._block(ind)
            if ind == indent and (content == "-" or content.startswith("- ")):
                return self._seq(ind)
            return None
        return _scalar(rest, lineno)

    def _map(self, indent):
        out = {}
        while True:
            nxt = self._next_content()
            if nxt is None:
                break
            ind, content = nxt
            if ind < indent:
                break
            if ind > indent:
                raise YamlError(f"{self.i + 1}행: 들여쓰기가 맞지 않습니다")
            if content == "-" or content.startswith("- "):
                break
            m = _KEY.match(content)
            if not m:
                raise YamlError(f"{self.i + 1}행: 'key: value' 형식이 아닙니다: {content[:40]}")
            lineno = self.i + 1
            key = _scalar(m.group("key"), lineno)
            if key in out:
                raise YamlError(f"{lineno}행: 같은 키가 두 번 나옵니다: {key}")
            out[key] = self._value_after_key(m.group("rest"), indent, lineno)
        return out

    def _seq(self, indent):
        out = []
        while True:
            nxt = self._next_content()
            if nxt is None:
                break
            ind, content = nxt
            if ind < indent or not (content == "-" or content.startswith("- ")):
                if ind > indent:
                    raise YamlError(f"{self.i + 1}행: 들여쓰기가 맞지 않습니다")
                break
            if ind > indent:
                raise YamlError(f"{self.i + 1}행: 들여쓰기가 맞지 않습니다")
            lineno = self.i + 1
            item = content[1:].lstrip(" ")
            if item == "":
                self.i += 1
                nxt2 = self._next_content()
                out.append(self._block(nxt2[0]) if nxt2 and nxt2[0] > indent else None)
                continue
            body = _strip_comment(item)
            if _KEY.match(body):
                # '- key: value' → 같은 줄을 매핑의 첫 줄로 바꿔 읽는다
                child_indent = ind + (len(content) - len(item))
                self.lines[self.i] = " " * child_indent + item
                out.append(self._map(child_indent))
            else:
                self.i += 1
                out.append(_scalar(body, lineno))
        return out


def loads(text, force_builtin=False):
    if _pyyaml is not None and not force_builtin:
        return _pyyaml.safe_load(text)
    return _Parser(text).parse()


def load_file(path, force_builtin=False):
    with open(path, encoding="utf-8") as fh:
        return loads(fh.read(), force_builtin=force_builtin)


# ---------- 쓰기(promptfoo 설정 생성 등에 씀) ----------

def _dump_scalar(v):
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, (int, float)):
        return repr(v)
    return json.dumps(str(v), ensure_ascii=False)


def dumps(value, indent=0):
    pad = " " * indent
    lines = []
    if isinstance(value, dict):
        if not value:
            return pad + "{}"
        for k, v in value.items():
            key = k if re.match(r"^[A-Za-z_][A-Za-z0-9_\-]*$", str(k)) else json.dumps(str(k), ensure_ascii=False)
            if isinstance(v, (dict, list)) and v:
                lines.append(f"{pad}{key}:")
                lines.append(dumps(v, indent + 2))
            else:
                lines.append(f"{pad}{key}: {dumps_inline(v)}")
    elif isinstance(value, list):
        if not value:
            return pad + "[]"
        for v in value:
            if isinstance(v, dict) and v:
                inner = dumps(v, indent + 2).split("\n")
                inner[0] = pad + "- " + inner[0].lstrip()
                lines.extend(inner)
            elif isinstance(v, list) and v:
                lines.append(pad + "-")
                lines.append(dumps(v, indent + 2))
            else:
                lines.append(f"{pad}- {dumps_inline(v)}")
    else:
        return pad + _dump_scalar(value)
    return "\n".join(lines)


def dumps_inline(v):
    if isinstance(v, dict):
        return "{}"
    if isinstance(v, list):
        return "[]"
    return _dump_scalar(v)
