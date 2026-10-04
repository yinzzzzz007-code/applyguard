"""Build a captioned walkthrough from browser screenshots of fictional demo data."""

from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps


HERE = Path(__file__).resolve().parent
FRAMES = HERE / "frames"
OUTPUT = HERE / "applyguard-demo.mp4"
FONT = Path("C:/Windows/Fonts/msyh.ttc")
SIZE = (1280, 720)
FPS = 8

SCENES = [
    ("01-vault.png", "01  职业经历库", "查看虚构经历、陈述与证据来源。", "浏览器会话编辑；后端经历库仍为只读种子"),
    ("02-jd.png", "02  输入目标岗位", "粘贴 JD，选择离线规则工作流。", "默认不调用付费模型"),
    ("03-jd-result.png", "03  工作流返回", "本机后端解析岗位要求并给出步骤轨迹。", "Live 请求，非预录结果"),
    ("04-match.png", "04  证据匹配", "高亮原文要求，展示匹配强弱。", "可以回查相关经历与证据"),
    ("05-resume.png", "05  简历审查", "查看选入和排除理由。", "手动加入仍需再次核验"),
    ("06-claims.png", "06  陈述核验", "核对每条简历表述的来源与状态。", "已核验仅相对于虚构经历库"),
    ("07-ats.png", "07  网申模拟", "查看拟填字段、风险与本人确认要求。", "固定映射模拟器，不扫描真实网站"),
    ("08-confirm.png", "08  人工确认", "确认可复制内容，最终投递由用户完成。", "本页不会提交真实申请"),
    ("09-history.png", "09  申请历史", "本浏览器保存模拟确认摘要。", "不保存个人资料或 JD 原文"),
    ("10-blocked-claims.png", "10  阻断不实陈述", "不受支持的 CUDA 内容被标为 BLOCKED。", "预录演示数据，不能点击确认绕过"),
    ("11-blocked-confirm.png", "11  阻断复制", "整单阻断时不生成可复制填写稿。", "复制按钮禁用；无真实投递"),
]


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT), size)


def scene_frame(title: str, description: str, note: str, screenshot: Path, number: int) -> Image.Image:
    image = Image.new("RGB", SIZE, "#f7f8f3")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, 1280, 720), radius=0, fill="#f7f8f3")
    draw.rounded_rectangle((32, 32, 1225, 680), radius=28, fill="#ffffff", outline="#dfe5df", width=2)
    draw.rounded_rectangle((60, 62, 200, 99), radius=18, fill="#dcf9ee")
    draw.text((78, 66), "ApplyGuard", font=font(19), fill="#075744")
    draw.text((62, 155), title, font=font(38), fill="#15342c")
    draw.text((64, 240), description, font=font(23), fill="#29483f")
    draw.text((64, 311), note, font=font(17), fill="#5a716a")
    draw.rounded_rectangle((60, 494, 552, 600), radius=18, fill="#e7f3ef")
    draw.text((80, 514), "证据 → 核验 → 人工确认", font=font(23), fill="#15342c")
    draw.text((80, 555), "课程项目 · 虚构演示数据", font=font(17), fill="#5a716a")
    draw.text((64, 635), f"{number:02d} / {len(SCENES):02d}", font=font(18), fill="#82958d")
    shot = Image.open(screenshot).convert("RGB")
    shot = ImageOps.contain(shot, (575, 630), Image.Resampling.LANCZOS)
    x, y = 613 + (575 - shot.width) // 2, 45 + (630 - shot.height) // 2
    draw.rounded_rectangle((x - 8, y - 8, x + shot.width + 8, y + shot.height + 8), radius=15, fill="#e5eae6")
    image.paste(shot, (x, y))
    return image


def main() -> None:
    missing = [name for name, *_ in SCENES if not (FRAMES / name).exists()]
    if missing:
        raise SystemExit(f"Missing browser screenshots: {', '.join(missing)}")
    with imageio.get_writer(OUTPUT, format="FFMPEG", mode="I", fps=FPS,
                            codec="libx264", quality=7, macro_block_size=16,
                            ffmpeg_log_level="error") as writer:
        for index, (name, title, description, note) in enumerate(SCENES, 1):
            frame = np.asarray(scene_frame(title, description, note, FRAMES / name, index))
            for _ in range(FPS * 3):
                writer.append_data(frame)
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
