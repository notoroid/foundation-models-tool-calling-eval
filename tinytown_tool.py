"""tinytowngen を Foundation Models の Tool として使うためのラッパーとデモ。

    python tinytown_tool.py "平安京っぽい街を描いて"
"""

import asyncio
import shutil
import sys
from pathlib import Path

import apple_fm_sdk as fm

OUTPUT_DIR = Path(__file__).parent / "output"

LAYOUT_GUIDE = """\
Layout tokens (space separated, tile coords are 0-based {x,y} from top-left):
  C{x,y}      commercial block (1 tile); x/y may be a range: C{0-3,0-1}
  B{x,y}      building under construction
  U1{x,y} U2{x,y} U3{x,y} U1x2{x,y} U2x1{x,y}  park/forest, top-left at {x,y}
  F{r}        boulevard on horizontal road r (1..H-1); F{r,x0-x1} for part of it
  W{c}        canal on vertical road c (1..W-1); W{c,y0-y1} for part of it
  C*  B*      fill all remaining tiles (put last)
Tokens must not overlap, and F/W must not cross a park.
Example (13x7): U3{0,0} U2{9,4} F{3} W{5} B{7,1} C*"""


@fm.generable("tinytowngen arguments")
class TinyTownArgs:
    layout: str = fm.guide("Layout tokens, e.g. 'U3{0,0} F{3} W{5} C*'")
    # regex ガイドは apple_fm_sdk 0.2.1 で GenerationError (status 255) になるため使わない
    grid: str = fm.guide("Grid size WxH in tiles, e.g. 13x7")
    map: str = fm.guide("Map style: sapporo = modern city, heiankyo11c = ancient Kyoto",
                        anyOf=["sapporo", "heiankyo11c"])
    seed: int = fm.guide("Seed for building variations", range=(1, 999))
    filename: str = fm.guide("Output file name ending in .png, e.g. town.png")


class TinyTownTool(fm.Tool):
    name = "render_town"
    description = "Renders an aerial PNG image of a grid city from a layout string.\n" + LAYOUT_GUIDE

    def __init__(self, executable: str | None = None, scale: int = 2):
        self.executable = executable or shutil.which("tinytowngen")
        if self.executable is None:
            raise FileNotFoundError("tinytowngen が PATH に見つかりません (.venv を有効化してください)")
        self.scale = scale
        super().__init__()

    @property
    def arguments_schema(self) -> fm.GenerationSchema:
        return TinyTownArgs.generation_schema()

    async def call(self, args: fm.GeneratedContent) -> str:
        # モデルが決めたファイル名はベース名だけ使い、出力先を output/ に限定する
        name = Path(args.value(str, for_property="filename")).name or "town.png"
        if not name.endswith(".png"):
            name += ".png"
        OUTPUT_DIR.mkdir(exist_ok=True)
        output = OUTPUT_DIR / name

        proc = await asyncio.create_subprocess_exec(
            self.executable,
            "-l", args.value(str, for_property="layout"),
            "-g", args.value(str, for_property="grid"),
            "-m", args.value(str, for_property="map"),
            "-s", str(args.value(int, for_property="seed")),
            "--scale", str(self.scale),
            "-o", str(output),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            # エラー内容をモデルに返し、レイアウトを直して再試行させる
            return f"Failed (exit {proc.returncode}). Fix the layout and call again.\n{stderr.decode()}"
        return stdout.decode().strip()


INSTRUCTIONS = (
    "You design small grid cities and draw them with the render_town tool. "
    "Always call render_town, then tell the user the output file path in Japanese."
)


async def main(prompt: str) -> None:
    model = fm.SystemLanguageModel()
    is_available, reason = model.is_available()
    if not is_available:
        print(f"Foundation Model is not available: {reason}")
        return

    session = fm.LanguageModelSession(instructions=INSTRUCTIONS, tools=[TinyTownTool()])
    print(await session.respond(prompt))


if __name__ == "__main__":
    asyncio.run(main(" ".join(sys.argv[1:]) or "13x7 の平安京の街を描いて。中央に大路、左上に寺院。"))
