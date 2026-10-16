"""tinytown_tool.py の評価: オンデバイスモデルが扱える命令の複雑さを 5 段階で測る。

    python tinytown_eval.py              # 全レベル × 3 試行
    python tinytown_eval.py -l 4 -n 5    # レベル 4 だけ 5 試行

判定:
  PASS     描画に成功し、要件チェックをすべて満たした
  PARTIAL  描画には成功したが、要件を満たしていない
  FAIL     tinytowngen のエラーが 3 回に達した（4 回目以降は実行しない）
  NO_CALL  ツールを一度も呼ばずに応答した
  ERROR    生成そのものが例外で失敗した
"""

import argparse
import asyncio
import json
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import apple_fm_sdk as fm

import tinytown_tool
from tinytown_tool import INSTRUCTIONS, TinyTownTool

MAX_ERRORS = 3
EVAL_DIR = Path(__file__).parent / "output" / "eval"


@dataclass
class Level:
    level: int
    title: str
    prompt: str
    checks: dict[str, Callable[[dict], bool]]


def has(pattern: str) -> Callable[[dict], bool]:
    return lambda a: re.search(pattern, a["layout"].replace(" ", "")) is not None


def arg(name: str, value) -> Callable[[dict], bool]:
    return lambda a: a[name] == value


def f_avoids_park(road: int, park_cols: range) -> Callable[[dict], bool]:
    """F{road,...} があり、その範囲が park_cols の列を含まない（全幅 F{road} は不可）。"""
    def check(a: dict) -> bool:
        m = re.search(rf"F\{{{road}(?:,(\d+)-(\d+))?\}}", a["layout"].replace(" ", ""))
        if not m or m.group(1) is None:
            return False
        return not set(range(int(m.group(1)), int(m.group(2)) + 1)) & set(park_cols)
    return check


LEVELS = [
    Level(1, "単純な塗りつぶし",
          "8x5 の現代的な街を描いて。全部を商業地区で埋めて。",
          {"grid 8x5": arg("grid", "8x5"), "map sapporo": arg("map", "sapporo"),
           "全面が商業 (C* / C{0-7,0-4})": has(r"C\*|C\{0-7,0-4\}")}),
    Level(2, "要素 2 つ（交差なし）",
          "13x7 の平安京の街を描いて。中央に大路、左上に寺院。",
          {"grid 13x7": arg("grid", "13x7"), "map heiankyo11c": arg("map", "heiankyo11c"),
           "大路 F{3}": has(r"F\{3"), "左上の寺院 U?{0,0}": has(r"U[\dx]+\{0,0\}")}),
    Level(3, "座標指定・要素 3 つ（交差しない配置）",
          "10x6 の現代的な街。左上に 2x2 の公園、縦方向の道路 5 を水路に、"
          "横方向の道路 3 を大路にして。残りは商業地区。",
          {"grid 10x6": arg("grid", "10x6"), "map sapporo": arg("map", "sapporo"),
           "U2{0,0}": has(r"U2\{0,0\}"), "W{5}": has(r"W\{5"), "F{3}": has(r"F\{3"),
           "C*": has(r"C\*")}),
    Level(4, "交差の回避が 1 箇所必要",
          "12x8 の平安京。寺院を 3 つ: 左上 {0,0} に 3x3、右上 {10,0} に 2x2、"
          "左下 {0,6} に幅 1 x 高さ 2。横方向の道路 2 と 5 を大路に、縦方向の道路 6 を川に。"
          "大路と川は寺院を横切ってはいけない（寺院の縁に沿うのは可）。"
          "{7,6} は工事中、残りは屋敷。",
          {"grid 12x8": arg("grid", "12x8"), "map heiankyo11c": arg("map", "heiankyo11c"),
           "U3{0,0}": has(r"U3\{0,0\}"), "U2{10,0}": has(r"U2\{10,0\}"),
           "U1x2{0,6}": has(r"U1x2\{0,6\}"),
           "F{2} が寺院を避ける範囲指定": f_avoids_park(2, range(0, 3)),
           "F{5}": has(r"F\{5"), "W{6}": has(r"W\{6"), "B{7,6}": has(r"B\{7,6\}"),
           "C*": has(r"C\*")}),
    Level(5, "交差の回避が 3 箇所＋ハーフ・バリエーション・シード",
          "16x9 の現代的な街、シードは 7。公園: {0,0} に 3x3、{12,0} に 2x2、{6,6} に 3x3、"
          "{14,7} に幅 2 x 高さ 1。横方向の道路 1 と 6 を大路に、縦方向の道路 7 と 13 を水路に。"
          "大路と水路は公園を横切ってはいけないので、横切る部分は範囲を区切って避けること"
          "（公園の縁に沿うのは可）。{9,4} は左右のハーフに分けた商業地区で、右半分はバリエーション 3。"
          "{4,3} は商業地区のバリエーション 5。残りは商業地区。",
          {"grid 16x9": arg("grid", "16x9"), "map sapporo": arg("map", "sapporo"),
           "seed 7": arg("seed", 7),
           "U3{0,0}": has(r"U3\{0,0\}"), "U2{12,0}": has(r"U2\{12,0\}"),
           "U3{6,6}": has(r"U3\{6,6\}"), "U2x1{14,7}": has(r"U2x1\{14,7\}"),
           "F{1} が公園を避ける範囲指定": f_avoids_park(1, [0, 1, 2, 12, 13]),
           "F{6}": has(r"F\{6"), "W{7,…}": has(r"W\{7"), "W{13,…}": has(r"W\{13"),
           "CL{9,4}": has(r"CL\{9,4\}"), "CR{9,4}#3": has(r"CR\{9,4\}#3"),
           "C{4,3}#5": has(r"C\{4,3\}#5"), "C*": has(r"C\*")}),
]


@dataclass
class Call:
    args: dict
    ok: bool
    result: str


class RecordingTool(TinyTownTool):
    """呼び出しを記録し、エラーが MAX_ERRORS 回に達したら以降の実行を拒否する。"""

    def __init__(self, tag: str):
        self.tag = tag
        self.calls: list[Call] = []
        super().__init__()

    @property
    def errors(self) -> int:
        return sum(not c.ok for c in self.calls)

    async def call(self, args: fm.GeneratedContent) -> str:
        if self.errors >= MAX_ERRORS:
            return "Error limit reached. Do not call render_town again; tell the user it failed."
        try:
            a = {k: args.value(t, for_property=k)
                 for k, t in [("layout", str), ("grid", str), ("map", str), ("seed", int), ("filename", str)]}
        except Exception as e:
            self.calls.append(Call({}, False, f"argument error: {e}"))
            raise
        result = await super().call(args)
        ok = result.startswith("wrote ")
        if ok:
            # ファイル名の重複を避けるため、試行ごとの名前に付け替える
            src = Path(result.split()[1])
            dst = EVAL_DIR / f"{self.tag}_c{len(self.calls) + 1}.png"
            shutil.move(src, dst)
            result = result.replace(str(src), str(dst))
        self.calls.append(Call(a, ok, result))
        return result


@dataclass
class Trial:
    level: int
    trial: int
    verdict: str
    calls: int
    errors: int
    seconds: float
    failed_checks: list[str] = field(default_factory=list)
    final_layout: str | None = None
    error_messages: list[str] = field(default_factory=list)
    response: str = ""


async def run_trial(level: Level, n: int) -> Trial:
    tool = RecordingTool(f"L{level.level}_t{n}")
    session = fm.LanguageModelSession(instructions=INSTRUCTIONS, tools=[tool])
    start = time.monotonic()
    response, exc = "", None
    try:
        response = str(await session.respond(level.prompt))
    except Exception as e:
        exc = e
    t = Trial(level.level, n, "", len(tool.calls), tool.errors, round(time.monotonic() - start, 1),
              error_messages=[c.result.strip().splitlines()[-1] for c in tool.calls if not c.ok],
              response=response or f"{type(exc).__name__}: {exc}" if exc else response)

    successes = [c for c in tool.calls if c.ok]
    if tool.errors >= MAX_ERRORS:
        t.verdict = "FAIL"
    elif successes:
        final = successes[-1].args
        t.final_layout = f"-g {final['grid']} -m {final['map']} -s {final['seed']} -l \"{final['layout']}\""
        t.failed_checks = [name for name, check in level.checks.items() if not check(final)]
        t.verdict = "PARTIAL" if t.failed_checks else "PASS"
    elif exc is not None:
        t.verdict = "ERROR"
    else:
        t.verdict = "NO_CALL" if not tool.calls else "FAIL"
    return t


async def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("-l", "--level", type=int, action="append", help="実行するレベル（複数可）")
    p.add_argument("-n", "--trials", type=int, default=3)
    opts = p.parse_args()

    if not fm.SystemLanguageModel().is_available()[0]:
        raise SystemExit("Foundation Model is not available")
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    tinytown_tool.OUTPUT_DIR = EVAL_DIR / "tmp"

    results: list[Trial] = []
    for level in LEVELS:
        if opts.level and level.level not in opts.level:
            continue
        for n in range(1, opts.trials + 1):
            t = await run_trial(level, n)
            results.append(t)
            print(f"L{t.level} #{t.trial}: {t.verdict:8} calls={t.calls} errors={t.errors} {t.seconds}s"
                  + (f"  未達: {', '.join(t.failed_checks)}" if t.failed_checks else ""))
            for msg in t.error_messages:
                print(f"    └ {msg}")
            if t.final_layout:
                print(f"    layout: {t.final_layout}")

    print("\n== Summary ==")
    for level in LEVELS:
        rs = [r for r in results if r.level == level.level]
        if rs:
            counts = {v: sum(r.verdict == v for r in rs) for v in ["PASS", "PARTIAL", "FAIL", "NO_CALL", "ERROR"]}
            print(f"L{level.level} {level.title}: " + " ".join(f"{k}={v}" for k, v in counts.items() if v))

    out = EVAL_DIR / "results.json"
    out.write_text(json.dumps([r.__dict__ for r in results], ensure_ascii=False, indent=2))
    print(f"\n詳細: {out}")


if __name__ == "__main__":
    asyncio.run(main())
