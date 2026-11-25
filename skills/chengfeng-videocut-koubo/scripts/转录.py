#!/usr/bin/env python3
"""第 1 步 转录：录音或视频 → 逐字稿（每个字带时间、标点、句号）。会调用豆包录音文件识别，按时长付费。

用法：python3 转录.py <录音或视频> <工作目录> [--热词 'Codex,Claude'] [--接着查 <任务号>]
产出（都在工作目录里）：
  逐字.json    每个字：id、字、起、止（秒）、后面跟的标点、属于哪一句；以后各步都读它（修字会改它）
  逐字-转录.json  转录原样，修字每次从它开始改
  逐字稿.txt   给人和 AI 读的稿：一句一行，带句号、字号范围和时间；停顿 ≥0.8 秒、拖长的字另起一行标出
  识别原始.json  豆包原样返回的结果
原素材只读，不改。
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import 共用 as g

ap = argparse.ArgumentParser()
ap.add_argument("源"); ap.add_argument("工作目录")
ap.add_argument("--热词", default=""); ap.add_argument("--接着查")
a = ap.parse_args()
源 = os.path.abspath(a.源)
if not os.path.exists(源): g.出错(f"找不到：{源}")
os.makedirs(a.工作目录, exist_ok=True)
已有 = os.path.join(a.工作目录, "逐字.json")
if os.path.exists(已有) and not a.接着查:
    g.出错(f"{已有} 已经有了：转过就别再转（会再扣钱）。真要重转，先把它挪走。")
信息 = g.媒体信息(源)
d = g.识别(源, os.path.join(a.工作目录, "识别原始"), a.热词.split(","), a.接着查)
词们 = g.拆词(d)
if not 词们: g.出错("识别结果里一个字都没有：检查录音是不是有人声")
句们 = g.分句(词们)
稿 = {"源": 源, "时长": 信息["时长"], "帧率": 信息["帧率"], "词": 词们, "句": 句们}
g.写(已有, 稿); g.写(os.path.join(a.工作目录, "逐字-转录.json"), 稿); g.写逐字稿(a.工作目录, 稿)
print(f"转好了：{len(句们)} 句、{len(词们)} 字，录音 {g.秒(信息['时长'])}{'，有画面' if 信息['帧率'] else ''} → {a.工作目录}/逐字稿.txt")
