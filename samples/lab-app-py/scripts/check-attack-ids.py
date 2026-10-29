#!/usr/bin/env python3
"""공격 자리표시 ID 검사(설계 5.6, W5).

목적: 교재·대본·테스트·시험 문제·코드 속 ATTACK ID가 모두 attack-registry.yaml에 있는지,
      대괄호 자리표시는 콜론형 [ATTACK-<범주>-<NN>: 유형 이름]인지, 그 유형 이름이 등록부 이름과 같은지 본다
      (등록부 이름이 원본. 여러 턴의 앞 턴 -T1·-T2는 이름 검사에서 뺀다).
실행(lab-app-py 폴더에서): python3 -I scripts/check-attack-ids.py [검사할 경로 ...]
  경로를 주지 않으면 이 랩 폴더(lab-app-py)만 본다. 랩 폴더를 저장소 루트로 올린 수강생 저장소·CI에서도 남의 폴더를 읽지 않는다.
  저장소 루트 전체(랩의 두 단계 위: prompts·skills·samples/extras까지): python3 -I scripts/check-attack-ids.py --course
  다른 폴더·파일도 경로로 줄 수 있다. 없는 경로를 주면 "경로 없음"을 찍고 종료 코드 2로 멈춘다(0개 통과로 넘어가지 않음).
  (작성자용: 교재 원고가 있는 작성자 폴더에서만 ../../교재 같은 경로를 준다. 공개 저장소에는 교재 폴더가 없다)
  빼는 곳: 빌드 산출물(build/), node_modules, eval-kit/results, 이 등록부 자체,
           .gitignore 대상(.lab-run/, .pytest_cache/, long.json, .env). 그래서 숫자가 새 clone과 같다.
종료 코드: 0 = 문제 없음, 1 = 등록부에 없는 ID·콜론 없는 자리표시·등록부와 다른 유형 이름이 있음, 2 = 등록부를 읽지 못함·없는 경로
표준 라이브러리만 쓴다.
"""
import re
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
REGISTRY = LAB / "attack-registry.yaml"
COURSE = LAB.parents[1]   # 저장소 루트(llm-security-in-practice)
SKIP_DIRS = {"build", "node_modules", "results", "__pycache__", ".git", "_output", ".venv",
             ".lab-run", ".pytest_cache", ".cache", "reviews"}   # .venv: 랩 가상 환경. .lab-run 등은 .gitignore 대상(실행할 때마다 생김). reviews: 검토 기록(지적한 ID를 그대로 인용)
SKIP_FILES = {"long.json", ".env"}   # .gitignore 대상 파일. 빼야 새 clone과 숫자가 같다(3차 검토 B3-1)
EXTS = {".md", ".py", ".yaml", ".yml", ".json", ".sh", ".js", ".html", ".txt"}
ID_RE = re.compile(r"ATTACK-([A-Z]+)-([A-Z0-9]+)(?:-T\d+)?")
BRACKET_RE = re.compile(r"\[(ATTACK-[A-Z]+-[A-Z0-9]+(?:-T\d+)?)(:[^\]\n]*)?\]")
GENERIC = {"ATTACK-XX-NN", "ATTACK-CAT-NN"}   # 설명문 속 형식 예시


def load_registry(path):
    """{ID: 유형 이름}을 돌려준다."""
    ids = {}
    in_attacks = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("attacks:"):
            in_attacks = True
            continue
        if in_attacks:
            m = re.match(r"\s+(ATTACK-[A-Z]+-\d{2}):\s*\{type:\s*\"([^\"]*)\"", line) or \
                re.match(r"\s+(ATTACK-[A-Z]+-\d{2}):", line)
            if m:
                ids[m.group(1)] = m.group(2) if m.lastindex and m.lastindex >= 2 else None
            elif line and not line.startswith(" "):
                in_attacks = False
    return ids


def iter_files(roots):
    for root in roots:
        root = Path(root)
        if root.is_file():
            yield root
            continue
        for p in sorted(root.rglob("*")):
            rel = p.relative_to(root).parts
            if any(part in SKIP_DIRS for part in rel):
                continue
            if p.is_file() and p.suffix in EXTS and p.name not in SKIP_FILES and p.resolve() != REGISTRY.resolve():
                yield p


def main(argv):
    if not REGISTRY.exists():
        print(f"등록부 없음: {REGISTRY}")
        return 2
    known = load_registry(REGISTRY)
    if not known:
        print("등록부에서 ID를 하나도 읽지 못했습니다")
        return 2
    if "--course" in argv:
        argv = [a for a in argv if a != "--course"] + [str(COURSE)]
    roots = argv or [LAB]
    missing = [r for r in roots if not Path(r).exists()]
    if missing:
        for r in missing:
            print(f"경로 없음: {r}")
        return 2
    unknown, bad_form, bad_name, files, refs = [], [], [], 0, 0
    for f in iter_files(roots):
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        files += 1
        for n, line in enumerate(text.splitlines(), 1):
            for m in ID_RE.finditer(line):
                full = m.group(0)
                base = re.sub(r"-T\d+$", "", full)
                if base in GENERIC or base.endswith("-NN"):   # 형식 설명 속 번호 자리(ATTACK-RAG-NN 등)
                    continue
                refs += 1
                if base not in known:
                    unknown.append(f"{f}:{n}: {full}")
            for m in BRACKET_RE.finditer(line):
                if not m.group(2) and m.group(1) not in GENERIC and not m.group(1).endswith("-NN"):
                    bad_form.append(f"{f}:{n}: [{m.group(1)}] → [{m.group(1)}: 유형 이름]")
                elif m.group(2) and m.group(1) in known and known[m.group(1)]:
                    name = m.group(2)[1:].split(" — ")[0].strip()   # 뒤에 붙는 " — 실제 문구는 …" 설명은 뺀다
                    if name and name != "유형 이름" and "…" not in name and name != known[m.group(1)]:   # "…"는 일부러 줄인 표기, "유형 이름"은 형식 설명
                        bad_name.append(f"{f}:{n}: [{m.group(1)}: {name}] → 등록부 이름 '{known[m.group(1)]}'")
    print(f"등록부 {len(known)}개 · 파일 {files}개 · ID 참조 {refs}개")
    for u in unknown:
        print("등록부에 없음:", u)
    for b in bad_form:
        print("콜론형 아님:", b)
    for b in bad_name:
        print("이름 다름:", b)
    if unknown or bad_form or bad_name:
        print(f"실패: 등록부에 없는 ID {len(unknown)}건, 콜론형 아님 {len(bad_form)}건, 이름 다름 {len(bad_name)}건")
        return 1
    print("통과: 모든 ATTACK ID가 등록부에 있고 자리표시는 콜론형이며 유형 이름이 등록부와 같습니다")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
