#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
data/majors.json 검증 + index.html 시드 블록 재생성

왜 이 스크립트가 있나
  학과군이 42개로 늘면서 index.html 안에서 손대기 어려워졌다.
  이제 학과 추가·수정은 data/majors.json 한 곳에서만 한다.

  다만 index.html 에는 계열별 대표 6개짜리 '시드'가 남아 있다.
  file:// 로 열거나 학교망이 막아 fetch 가 실패할 때 셀렉트가 통째로
  비어버리는 것을 막기 위한 최소 안전장치다. 시드를 손으로 고치면
  JSON 과 어긋나므로, 이 스크립트가 JSON 에서 다시 찍어 준다.

쓰는 법 (Windows PowerShell)
  cd C:\\repos\\jinhak_total_analysis
  python scripts\\build_majors.py            # 검증 + 시드 갱신
  python scripts\\build_majors.py --check    # 검증만 (파일을 고치지 않는다)

끝나면 GitHub Desktop 에서 data/majors.json 과 index.html 을 함께 커밋한다.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "data" / "majors.json"
HTML_PATH = ROOT / "index.html"

# 계열마다 대표 1개. 시드에 들어갈 학과군 키.
SEED_KEYS = ["mechanical", "earth_env", "medical", "business", "korean_lit", "edu_general"]

START = "/* @majors-seed:start — 자동 생성. 직접 수정하지 마시오. */"
END = "/* @majors-seed:end */"

REQUIRED_KEYS = ["group", "name", "requiredCourses", "recommendedCourses",
                 "coreKeywords", "evaluationFocus", "interviewQuestions"]

# 앱의 COURSE_EQUIV 가 아는 표기로 맞춰 둔다. 여기 없는 과목명은 경고만 낸다.
KNOWN_COURSE_HINT = re.compile(r"^[가-힣A-Za-z0-9·\s]+$")


def fail(msg):
    print("  ✗ " + msg)
    return 1


def validate(data):
    """치명적 오류 수를 돌려준다. 경고는 세지 않는다."""
    errs = 0
    groups = data.get("groups") or []
    rows = data.get("rows") or {}

    if not groups:
        errs += fail("groups 가 비어 있습니다.")
    if not rows:
        errs += fail("rows 가 비어 있습니다.")

    seen_names = {}
    for key, v in rows.items():
        where = "rows." + key
        if not re.fullmatch(r"[a-z][a-z0-9_]*", key):
            errs += fail(where + " — 키는 영소문자·숫자·밑줄만 씁니다.")
        if not isinstance(v, dict):
            errs += fail(where + " — 객체가 아닙니다.")
            continue

        for k in REQUIRED_KEYS:
            if k not in v:
                errs += fail(where + " — '" + k + "' 항목이 없습니다.")

        if v.get("group") not in groups:
            errs += fail(where + " — group '" + str(v.get("group")) +
                         "' 은 groups 목록에 없습니다. " + " / ".join(groups) + " 중 하나여야 합니다.")

        name = (v.get("name") or "").strip()
        if not name:
            errs += fail(where + " — name 이 비어 있습니다.")
        elif name in seen_names:
            errs += fail(where + " — name 이 " + seen_names[name] + " 와 같습니다.")
        else:
            seen_names[name] = where

        for k in ("requiredCourses", "recommendedCourses", "coreKeywords", "interviewQuestions"):
            if k in v and not isinstance(v[k], list):
                errs += fail(where + "." + k + " — 배열이어야 합니다.")

        qs = v.get("interviewQuestions") or []
        if len(qs) < 3:
            print("  ! " + where + " — 확인 문항이 " + str(len(qs)) + "개뿐입니다. 4개를 권합니다.")
        if len(v.get("coreKeywords") or []) < 8:
            print("  ! " + where + " — 핵심 키워드가 적습니다(" +
                  str(len(v.get("coreKeywords") or [])) + "개). 기출 매칭이 약해집니다.")
        if not (v.get("requiredCourses") or []):
            print("  ! " + where + " — 필수 이수 과목이 비어 있어 이수 점검이 나오지 않습니다.")

        for c in (v.get("requiredCourses") or []) + (v.get("recommendedCourses") or []):
            if not KNOWN_COURSE_HINT.match(str(c)):
                print("  ! " + where + " — 과목명 '" + str(c) + "' 에 특수문자가 있습니다. "
                      "로마숫자(Ⅰ·Ⅱ) 대신 아라비아숫자(1·2)를 쓰십시오.")

    for k in SEED_KEYS:
        if k not in rows:
            errs += fail("시드 대상 '" + k + "' 이 rows 에 없습니다. "
                         "scripts/build_majors.py 의 SEED_KEYS 를 고치십시오.")

    seeded_groups = {rows[k]["group"] for k in SEED_KEYS if k in rows}
    missing = [g for g in groups if g not in seeded_groups]
    if missing:
        print("  ! 시드에 빠진 계열: " + ", ".join(missing) +
              " — 오프라인 축약본에서 이 계열이 보이지 않습니다.")

    return errs


def render_seed(rows):
    out = ["const MAJORS_SEED = {"]
    body = []
    for k in SEED_KEYS:
        block = json.dumps(rows[k], ensure_ascii=False, indent=2)
        block = block.replace("\n", "\n  ")
        body.append("  " + k + ": " + block)
    out.append(",\n".join(body))
    out.append("};")
    return "\n".join(out)


def main():
    check_only = "--check" in sys.argv

    if not JSON_PATH.exists():
        print("data/majors.json 이 없습니다: " + str(JSON_PATH))
        return 2
    try:
        data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print("data/majors.json 이 깨졌습니다 — " + str(e))
        return 2

    rows = data.get("rows") or {}
    print("검증 — 계열 " + str(len(data.get("groups") or [])) +
          "개 / 학과군 " + str(len(rows)) + "개")

    errs = validate(data)
    if errs:
        print("\n오류 " + str(errs) + "건. 고치기 전에는 배포하지 마십시오.")
        return 1

    by_group = {}
    for v in rows.values():
        by_group[v["group"]] = by_group.get(v["group"], 0) + 1
    for g in data.get("groups") or []:
        print("    " + g + " — " + str(by_group.get(g, 0)) + "개")
    print("  ✓ 검증 통과")

    if check_only:
        return 0

    html = HTML_PATH.read_text(encoding="utf-8")
    if START not in html or END not in html:
        print("index.html 에서 시드 표식을 찾지 못했습니다. "
              "'@majors-seed:start' / '@majors-seed:end' 주석이 있어야 합니다.")
        return 2

    head = html[: html.index(START) + len(START)]
    tail = html[html.index(END):]
    new = head + "\n" + render_seed(rows) + "\n" + tail

    if new == html:
        print("  · 시드가 이미 최신입니다. index.html 을 건드리지 않았습니다.")
        return 0

    HTML_PATH.write_text(new, encoding="utf-8")
    print("  ✓ index.html 시드 갱신 — " + ", ".join(SEED_KEYS))
    print("\n다음: GitHub Desktop 에서 data/majors.json 과 index.html 을 함께 커밋하십시오.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
