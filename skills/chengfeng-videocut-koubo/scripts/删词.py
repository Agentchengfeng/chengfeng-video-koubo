#!/usr/bin/env python3
"""第 4 步 汇总：把删词.json 落成准确的字号，出两张表和删后全文，给 AI 自读、给用户看。不动声音。

用法：python3 删词.py <工作目录> <删词.json>
删词.json（每次都写这一轮的全部结论，不是只写新找到的）：
{
  "删": [
    {"句": "s012", "删": "最近我就关心", "第几处": 1, "类": "句内重复", "风险": "低", "依据": "R2"},
    {"整句": ["s013", "s014"], "类": "重录", "风险": "高", "依据": "R1"},
    {"从": "w0120", "到": "w0124", "类": "残句", "风险": "低"}
  ],
  "重复句子": [
    {"句子": "因为今天有什么…", "说了几遍": 3, "保了哪遍": "第 3 遍 00:08", "删了哪几遍": "第 1、2 遍", "风险": "高——整句级删除"}
  ],
  "换要点": ["s015", "s030"]
}
- "删" 按原话照抄（标点、空格不用管），一句里出现不止一次时写 "第几处"；删的头尾必须是完整的字（英文词不能只删半个）。
- "换要点"：这一句说完，下一句开始讲新的要点，剪的时候这里多留一点停顿。
产出：删词结果.json（剪.py 读它）、两张表.md、删后全文.txt。
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import 共用 as g

ap = argparse.ArgumentParser(); ap.add_argument("工作目录"); ap.add_argument("删词"); a = ap.parse_args()
稿 = g.读(os.path.join(a.工作目录, "逐字.json")); 词们 = 稿["词"]; 位 = {w["id"]: i for i, w in enumerate(词们)}
句 = {s["id"]: s for s in 稿["句"]}; 单 = g.读(a.删词)


def 找(sid, 文, 第几):
    头, 尾 = g.找字(稿, sid, 文, 第几)
    while 尾 + 1 < len(词们) and 词们[尾 + 1]["字"] == "" and "原字" in 词们[尾 + 1]: 尾 += 1   # 修字合并留空的字一起带上
    return 头, 尾


删, 条们 = set(), []
for k, x in enumerate(单.get("删", [])):
    if "整句" in x:
        ss = x["整句"] if isinstance(x["整句"], list) else [x["整句"]]
        for sid in ss:
            if sid not in 句: g.出错(f"第 {k + 1} 条：没有这一句 {sid}")
        i, j = 位[句[ss[0]]["首"]], 位[句[ss[-1]]["尾"]]
    elif "从" in x:
        i, j = 位.get(x["从"]), 位.get(x.get("到", x["从"]))
        if i is None or j is None or j < i: g.出错(f"第 {k + 1} 条字号不对：{x}")
    else:
        i, j = 找(x.get("句"), x.get("删", ""), x.get("第几处"))
    ids = [词们[q]["id"] for q in range(i, j + 1)]
    重 = [q for q in ids if q in 删]
    if 重: print(f"  注意：第 {k + 1} 条跟前面的条目重叠了 {len(重)} 个字（{重[0]}…），合并处理", file=sys.stderr)
    删.update(ids)
    条们.append({"序": k + 1, "ids": ids, "起": 词们[i]["起"], "类": x.get("类", ""), "风险": x.get("风险", ""), "依据": x.get("依据", ""),
               "删除": g.连字(词们[i:j + 1])})
for sid in 单.get("换要点", []):
    if sid not in 句: g.出错(f"换要点里没有这一句：{sid}")

留 = [i for i, w in enumerate(词们) if w["id"] not in 删]
def 剩下读作(ids):
    i, j = 位[ids[0]], 位[ids[-1]]
    前 = [q for q in 留 if q < i][-8:]; 后 = [q for q in 留 if q > j][:8]
    return g.连字([词们[q] for q in 前]) + "‸" + g.连字([词们[q] for q in 后])
条们.sort(key=lambda c: c["起"])
for c in 条们: c["剩下读作"] = 剩下读作(c["ids"])
删秒 = sum(词们[位[q]]["止"] - 词们[位[q]]["起"] for q in 删)
g.写(os.path.join(a.工作目录, "删词结果.json"), {"删": sorted(删, key=位.get), "条": 条们, "换要点": 单.get("换要点", []),
                                           "重复句子": 单.get("重复句子", [])})
表 = ["## 删词汇总表", "", "| # | 时间 | 类型 | 删除 | 剩下读作 | 风险 | 依据 |", "|---|---|---|---|---|---|---|"]
for n, c in enumerate(条们, 1):
    表.append(f"| {n} | {g.秒(c['起'])} | {c['类']} | {c['删除']} | {c['剩下读作']} | {c['风险']} | {c['依据']} |")
表 += ["", "## 重复句子表", "", "| 句子（开头） | 说了几遍 | 保了哪遍 | 删了哪几遍 | 风险 |", "|---|---|---|---|---|"]
for r in 单.get("重复句子", []):
    表.append(f"| {r.get('句子', '')} | {r.get('说了几遍', '')} | {r.get('保了哪遍', '')} | {r.get('删了哪几遍', '')} | {r.get('风险', '')} |")
if not 单.get("重复句子"): 表.append("| （没有说了多遍的句子） | | | | |")
open(os.path.join(a.工作目录, "两张表.md"), "w", encoding="utf-8").write("\n".join(表) + "\n")
全文 = []
for s in 稿["句"]:
    t = g.连字([词们[q] for q in range(位[s["首"]], 位[s["尾"]] + 1) if 词们[q]["id"] not in 删])
    if t: 全文.append(f"{s['id']}  {t}")
open(os.path.join(a.工作目录, "删后全文.txt"), "w", encoding="utf-8").write("\n".join(全文) + "\n")
print(f"{len(条们)} 条、删 {len(删)} 字（说话约 {删秒:.1f} 秒）→ 两张表.md、删后全文.txt。先把删后全文从头读一遍，读不通的条目撤掉再剪。")
