#!/usr/bin/env python3
"""第 6 步 剪后核对：让豆包把剪好的人声再听一遍，跟“剪后应该剩下的字”逐字对，再找连着重复的词。会再付一次识别费。

为什么要有：删词结果只说明删了哪些字，不说明刀落得对不对。刀落在重念那遍的尾音上、该删的一遍没删干净、
刀切进了留下的字，表上都看不出来，再听一遍能看出来。

用法：python3 核对.py <工作目录> [--热词 'A,B'] [--不复核] [--接着查 <任务号>] [--近 0.5]
读：逐字.json、删词结果.json、剪辑表.json、剪后.wav；出：剪后识别.json、核对.json，屏幕上一张问题表。
判读：
  ▲ 要回去听、多半要改：所有“重复”；删词刀口上或离它不到 0.5 秒的“多出来/少了/变了”；离压停顿刀口不到 0.3 秒还“少了”的
  · 离刀口远的差异，多半是同一句话两次识别写法不一样（Codec/Codex）或同音字，扫一眼，不改
  刀口上“多出来/变了”的字，会把原素材刀口两边各 3 秒单独再识别一次：原声本来就有，就降成 ·（加 --不复核 跳过，省钱）
退出码：0 = 没有要回去听的；1 = 有 ▲ 条。
"""
import argparse, os, re, subprocess, sys, tempfile
from difflib import SequenceMatcher
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import 共用 as g

ap = argparse.ArgumentParser(); ap.add_argument("工作目录"); ap.add_argument("--热词", default="")
ap.add_argument("--不复核", action="store_true"); ap.add_argument("--接着查"); ap.add_argument("--近", type=float, default=0.5)
a = ap.parse_args(); W = a.工作目录
稿 = g.读(os.path.join(W, "逐字.json")); 结果 = g.读(os.path.join(W, "删词结果.json")); 表 = g.读(os.path.join(W, "剪辑表.json"))
词们 = 稿["词"]; 删 = set(结果["删"]); 热 = a.热词.split(",")
def 拆(t): return [t] if re.fullmatch(r"[a-z0-9]+", t) else list(t)

# 1. 应该剩下的字；删词刀口在第几个字前面
期, 刀前, 期原 = [], {}, []        # 期原：每个期望的字修字前是什么（修过的字第二次识别多半还听成原样）
删词刀 = {c["后字"]: c for c in 表["刀口"] if c["类"] == "删词"}
for w in 词们:
    if w["id"] in 删: continue
    if w["id"] in 删词刀: 刀前[len(期)] = 删词刀[w["id"]]
    n = g.规整(w["字"])
    if n: 期 += 拆(n); 期原 += [g.规整(w.get("原字", ""))] * len(拆(n))
    elif w.get("原字") and 期原: 期原[-1] += g.规整(w["原字"])
拼接 = [s["剪后起"] for s in 表["段"][1:]]
删词秒 = [c["剪后秒"] for c in 表["刀口"] if c["类"] == "删词"]

# 2. 剪后实际听到的字
已识别 = os.path.join(W, "剪后识别.json"); 剪后 = os.path.join(W, "剪后.wav")
if not a.接着查 and os.path.exists(已识别) and os.path.getmtime(已识别) > os.path.getmtime(剪后):
    d = g.读(已识别); print("剪后.wav 没重剪过，用上次的识别结果（不再扣费）")   # 只改了判定规则时重跑不花钱
else:
    d = g.识别(剪后, os.path.join(W, "剪后识别"), 热, a.接着查)
听 = []
for u in d.get("result", {}).get("utterances", []):
    for w in u.get("words", []):
        n = g.规整(w["text"])
        for c in (拆(n) if n else []): 听.append((c, w["start_time"] / 1000))
es, rs = 期, [c for c, _ in 听]
def 前后(j1, j2, n=8): return "".join(rs[max(0, j1 - n):j1]) + "【" + "".join(rs[j1:j2]) + "】" + "".join(rs[j2:j2 + n])
def rt(j): return 听[min(max(j, 0), len(听) - 1)][1] if 听 else 0.0
ops = SequenceMatcher(None, es, rs, autojunk=False).get_opcodes()
对上 = {}
for op, i1, i2, j1, j2 in ops:
    if op == "equal": 对上.update({i1 + q: j1 + q for q in range(i2 - i1)})
def 期时(i):
    for q in range(len(es)):
        for k in (i + q, i - q):
            if k in 对上: return rt(对上[k])
    return 0.0
中数 = dict(zip("零一二两三四五六七八九", "01223456789"))
def 数(t):                                      # 只用来比：“十四”和“14”、“四”和“4”算同一个
    def 换(m):
        x = m.group(0)
        if x.count("十") == 1:
            a_, _, b_ = x.partition("十")
            if len(a_) <= 1 and len(b_) <= 1: return str((int(中数[a_]) if a_ else 1) * 10 + (int(中数[b_]) if b_ else 0))
        return "".join(中数.get(c, c) for c in x)
    return re.sub(r"[零一二两三四五六七八九十]+", 换, t)
问题 = []
for op, i1, i2, j1, j2 in ops:
    if op == "equal": continue
    在刀口 = next((刀前[k] for k in range(i1, max(i2, i1) + 1) if k in 刀前), None)
    t = rt(j1) if j2 > j1 else 期时(i1)
    类 = {"insert": "多出来", "delete": "少了", "replace": "变了"}[op]
    h, e = "".join(rs[j1:j2]), "".join(es[i1:i2])
    if op == "replace" and (SequenceMatcher(None, h, e).ratio() >= 0.6 or 数(h) == 数(e)): 类 = "写法不同"
    原 = "".join(dict.fromkeys(x for x in 期原[i1:i2] if x))
    if op == "replace" and 原 and 原 in h:      # 第二次识别跟第一次听成的一样（修字前的写法），不是刀口的事
        if 数(h.replace(原, "", 1)) == 数("".join(es[k] for k in range(i1, i2) if not 期原[k])): 类 = "修过的字"
    问题.append({"类": 类, "剪后秒": round(t, 2), "刀口": 在刀口, "离删词刀口": 0.0 if 在刀口 else round(min([abs(t - c) for c in 删词秒] or [99]), 2),
               "离拼接": round(min([abs(t - s) for s in 拼接] or [99]), 2), "听到": h, "应是": e, "上下文": 前后(j1, j2)})
见 = set()
def 形(xs): return "".join("#" if re.fullmatch(r"[a-z0-9]+", x) else x for x in xs)   # 英文、数字两次识别写法常不一样，按占位比
for n in (6, 5, 4, 3, 2):                       # 连着重复：同一串（≥2 字）隔 0–3 个字又出现，如“它自己它自己”
    for j in range(len(rs) - n):
        for 隔 in range(4):
            k = j + n + 隔
            if rs[k:k + n] == rs[j:j + n] and not any(j <= x < k + n for x in 见):
                原有 = 形(rs[j:k + n]) in 形(es)   # 稿里本来就这么说（“一个一个”“前半段是 X 后半段是”），不算
                见.update(range(j, k + n))
                if not 原有:
                    问题.append({"类": "重复", "剪后秒": round(rt(j), 2), "刀口": None, "离删词刀口": None, "离拼接": None,
                               "听到": "".join(rs[j:k + n]), "应是": "".join(rs[j:j + n]) + "".join(rs[j + n:k]), "上下文": 前后(j, k + n)})
                break
问题.sort(key=lambda f: f["剪后秒"])
要听 = [f for f in 问题 if f["类"] == "重复" or (f["类"] in ("多出来", "少了", "变了") and f["离删词刀口"] <= a.近)
        or (f["类"] == "少了" and f["离拼接"] <= 0.3)]

# 3. 复核：刀口上多出来/变了的字，原素材那一侧本来有没有
if not a.不复核:
    tmp = tempfile.mkdtemp(prefix="chengfeng-video-koubo-")
    def 听原声(lo, hi, 名):
        if hi - lo < 0.3: return ""
        p = os.path.join(tmp, 名 + ".wav")
        subprocess.run([g.工具("ffmpeg"), "-nostdin", "-v", "error", "-y", "-ss", f"{lo:.3f}", "-to", f"{hi:.3f}", "-i", 稿["源"], "-vn", p], check=True)
        return g.规整(g.识别(p, p[:-4], 热).get("result", {}).get("text", ""))
    for n_, f in enumerate([f for f in 要听 if f["类"] in ("多出来", "变了") and f["刀口"]]):
        c = f["刀口"]; 前 = 听原声(c["出刀"] - 3, c["出刀"], f"{n_}前"); 后 = 听原声(c["入刀"], c["入刀"] + 3, f"{n_}后")
        p2, n2 = f["上下文"].split("【")[0][-2:], f["上下文"].split("】")[1][:2]
        f["复核"] = {"刀口前原声": 前, "刀口后原声": 后}
        if (p2 + f["听到"]) in 前 or (f["听到"] + n2) in 后: f["类"] += "（原声本来就有）"
    要听 = [f for f in 要听 if "原声本来就有" not in f["类"]]
其余 = [f for f in 问题 if f not in 要听]
for f in 问题:
    if f["刀口"]: f["刀口"] = f["刀口"]["剪后秒"]
print(f"删词刀口 {len(删词秒)} 处、压停顿刀口 {len(拼接) - len(删词秒)} 处；要回去听的 {len(要听)} 条，离刀口远的识别差异 {len(其余)} 条")
for f in 要听:
    在 = "重复" if f["类"] == "重复" else ("删词刀口上" if f["刀口"] is not None else f"离删词刀口 {f['离删词刀口']} 秒")
    print(f"  ▲ {g.秒(f['剪后秒'])}  {f['类']}  {在}  听到「{f['听到']}」应是「{f['应是']}」  {f['上下文']}")
for f in 其余:
    print(f"  · {g.秒(f['剪后秒'])}  {f['类']}  听到「{f['听到']}」应是「{f['应是']}」  {f['上下文']}")
g.写(os.path.join(W, "核对.json"), {"要回去听": 要听, "识别差异": 其余})
sys.exit(1 if 要听 else 0)
