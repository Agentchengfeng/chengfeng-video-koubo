#!/usr/bin/env python3
"""第 2 步 修字：把听错的专名改对。只改文字，不改时间、不加字不减字、不改字号。

用法：python3 修字.py <工作目录> <修字.json>
修字.json 是一个列表，每条三种写法任选：
  {"id": "w0123", "改成": "Grok"}                          改一个字（英文词算一个字）
  {"从": "w0123", "到": "w0125", "改成": "Grok"}            几个字合成一个词（“格罗克”→“Grok”）：头一个字换成新写法，其余留空，时间不动
  {"句": "s002", "把": "其实", "改成": "提示"}               这一句里的这几个字换掉（一句里出现不止一次加 "第几处"）；字数一样就一字换一字
  {"把": "Gokul", "改成": "Grok"}                           稿里所有写成“Gokul”的那一个字都换
每条可加 "为什么"。产出：改好的 逐字.json / 逐字稿.txt，和 修字表.md（原词 → 改成 → 上下文）。
修字.json 每次写全部要改的（跟删词.json 一样）：脚本每次都从转录原样（逐字-转录.json）开始改，跑几遍结果都一样。
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import 共用 as g

ap = argparse.ArgumentParser(); ap.add_argument("工作目录"); ap.add_argument("修字"); a = ap.parse_args()
p = os.path.join(a.工作目录, "逐字.json"); 原样 = os.path.join(a.工作目录, "逐字-转录.json")
if not os.path.exists(原样): g.写(原样, g.读(p))
稿 = g.读(原样); 词们 = 稿["词"]; 位 = {w["id"]: i for i, w in enumerate(词们)}
表 = ["| # | 时间 | 原词 | 改成 | 上下文 | 为什么 |", "|---|---|---|---|---|---|"]
def 上下文(i, j):
    return g.连字(词们[max(0, i - 6):i]) + "【" + g.连字(词们[i:j + 1]) + "】" + g.连字(词们[j + 1:j + 7])
n = 0
for k, x in enumerate(g.读(a.修字)):
    新 = x.get("改成")
    if 新 is None: g.出错(f"第 {k + 1} 条没写“改成”")
    if "句" in x:
        段们 = [g.找字(稿, x["句"], x.get("把", ""), x.get("第几处"))]
    elif "把" in x:
        段们 = [(i, i) for i, w in enumerate(词们) if w.get("原字", w["字"]) == x["把"] or w["字"] == x["把"]]
        if not 段们: print(f"  第 {k + 1} 条：稿里没有“{x['把']}”，跳过", file=sys.stderr)
    else:
        i = 位.get(x.get("id") or x.get("从")); j = 位.get(x.get("到") or x.get("id") or x.get("从"))
        if i is None or j is None or j < i: g.出错(f"第 {k + 1} 条的字号不对：{x}")
        段们 = [(i, j)]
    for i, j in 段们:
        原 = g.连字([{"字": w.get("原字", w["字"])} for w in 词们[i:j + 1]])
        if 词们[i]["字"] == 新 and all(w["字"] == "" for w in 词们[i + 1:j + 1]): continue
        表.append(f"| {n + 1} | {g.秒(词们[i]['起'])} | {原} | {新} | {上下文(i, j)} | {x.get('为什么', '')} |")
        一字换一字 = len(新) == j - i + 1 and all(len(g.规整(词们[q]["字"])) == 1 for q in range(i, j + 1))
        for q in range(i, j + 1):
            词们[q].setdefault("原字", 词们[q]["字"]); 词们[q]["字"] = 新[q - i] if 一字换一字 else (新 if q == i else "")
        n += 1
for s in 稿["句"]:
    s["文"] = g.连字(词们[位[s["首"]]:位[s["尾"]] + 1])
g.写(p, 稿); g.写逐字稿(a.工作目录, 稿)
open(os.path.join(a.工作目录, "修字表.md"), "w", encoding="utf-8").write("\n".join(表) + "\n" if n else "（没有要改的字）\n")
print(f"改了 {n} 处 → {a.工作目录}/修字表.md")
