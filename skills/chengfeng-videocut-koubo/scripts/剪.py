#!/usr/bin/env python3
"""第 5 步 剪：按删词结果真的剪，顺手把太长的停顿压短。原素材只读，剪出来的是新文件。

用法：python3 剪.py <工作目录> [--不压停顿] [--只出声音]
读：逐字.json、删词结果.json
出：剪后.wav（人声）；源是视频时再出 剪后.mp4；剪辑表.json（每段从原素材哪到哪、每个刀口在剪后第几秒）；接缝待听.md

刀口怎么定（不用猜毫秒）：
- 停顿按前一个字后面的标点分档，只缩不拉长：句中 0.13 秒、逗号 0.2 秒、句末 0.3 秒、换要点 0.5 秒。
- 删掉一段话，前后两边各留一点原来的静音（加起来不超过上面那一档），刀口挪到附近最安静的 10 毫秒上，再各做 5 毫秒淡入淡出，免得“咔”一声。
- 前后没有停顿、刀只能落在连着说话的地方，或者刀口附近不够安静，记进 接缝待听.md，要人耳听。
- 源是视频时刀口对齐到画面帧上，声音和画面一样长，不会越剪越错位。
"""
import argparse, array, concurrent.futures as cf, os, subprocess, sys, tempfile, wave
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import 共用 as g

档 = {"句中": 0.133, "逗号": 0.2, "句末": 0.3, "换要点": 0.5}
ap = argparse.ArgumentParser(); ap.add_argument("工作目录"); ap.add_argument("--不压停顿", action="store_true")
ap.add_argument("--只出声音", action="store_true"); a = ap.parse_args()
W = a.工作目录; 稿 = g.读(os.path.join(W, "逐字.json")); 结果 = g.读(os.path.join(W, "删词结果.json"))
源 = 稿["源"]
if not os.path.exists(源): g.出错(f"原素材不见了：{源}")
信息 = g.媒体信息(源); 时长 = 信息["时长"]; fps = None if a.只出声音 else 信息["帧率"]
词们 = 稿["词"]; 删 = set(结果["删"]); 换要点 = set(结果.get("换要点", []))
留 = [i for i, w in enumerate(词们) if w["id"] not in 删]
if not 留: g.出错("全删光了，没东西可剪")
FF = g.工具("ffmpeg")

# 1. 响度：每 10 毫秒一格
raw = subprocess.run([FF, "-nostdin", "-v", "error", "-i", 源, "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                     capture_output=True, check=True).stdout
样 = array.array("h"); 样.frombytes(raw[:len(raw) // 2 * 2])
import math
响 = []
for k in range(0, len(样), 160):
    块 = 样[k:k + 160]; e = sum(x * x for x in 块) / max(len(块), 1)
    响.append(10 * math.log10(e / 32768 ** 2 + 1e-12))
底 = sorted(响)[len(响) // 10] if 响 else -90       # 底噪：最安静的一成
def 格(t): return min(max(int(t * 100), 0), len(响) - 1)
def 最静(lo, hi, 理想):
    """lo–hi 之间找最安静的格，一样静就挑离理想位置近的。"""
    if hi <= lo: return (lo + hi) / 2
    候 = [k / 100 for k in range(格(lo), 格(hi) + 1)] or [理想]
    候 = [t for t in 候 if lo <= t <= hi] or [理想]
    return min(候, key=lambda t: (round(响[格(t)], 0), abs(t - 理想)))
def 吵(t): return 响[格(t)] > 底 + 15
静阈 = 底 + 12
def 静段(lo, hi):
    """lo–hi 之间最长的一段安静（每格都比底噪响不到 12 分贝），返回（起, 止）；没有就 None。"""
    best, 头 = (0, None, None), None
    for k in range(格(lo), 格(hi) + 1):
        if 响[k] < 静阈:
            头 = k if 头 is None else 头
            if k - 头 + 1 > best[0]: best = (k - 头 + 1, 头, k)
        else: 头 = None
    return None if best[1] is None else (max(best[1] / 100, lo), min((best[2] + 1) / 100, hi))


def 档位(i, j):
    w = 词们[i]
    if w["句"] in 换要点 and 词们[j]["句"] != w["句"]: return "换要点"
    if set(w["标点"]) & g.标点句末 or w.get("句末"): return "句末"
    if set(w["标点"]) & g.标点逗号: return "逗号"
    return "句中"


# 2. 刀口
段, 缝 = [], []
起 = 词们[留[0]]["起"] - min(0.12, 词们[留[0]]["起"] - (词们[留[0] - 1]["止"] if 留[0] else 0))
for x, y in zip(留, 留[1:]):
    wa, wb = 词们[x], 词们[y]; 连着 = y == x + 1; 名 = 档位(x, y); 目 = 档[名]
    后静 = max(0.0, (词们[x + 1]["起"] if x + 1 < len(词们) else 时长) - wa["止"])
    前静 = max(0.0, wb["起"] - 词们[y - 1]["止"])
    疑 = []
    if 连着:
        # 只压真安静的那段：识别给的字间空隙不一定是静音（连着念的“长程”中间也可能有空）
        if a.不压停顿 or 后静 <= 目 + 0.02: continue
        r = 静段(wa["止"], wb["起"])
        if not r or r[1] - r[0] <= 目 + 0.03: continue
        有声 = (r[0] - wa["止"]) + (wb["起"] - r[1])          # 空隙里不安静的部分（尾音、换气）照留
        预算 = max(目 - 有声, 0.06)
        if (r[1] - r[0]) - 预算 < 0.05: continue
        A, B = r[0] + 预算 * 0.45, r[1] - 预算 * 0.55
        类 = "压停顿"
    else:
        留前 = min(后静, max(0.06, 目 * 0.4)); 留后 = min(前静, 目 - 留前)
        ra = 静段(wa["止"], wa["止"] + 后静 - 0.01) if 后静 >= 0.03 else None
        rb = 静段(wb["起"] - 前静 + 0.01, wb["起"]) if 前静 >= 0.03 else None
        if ra: A = min(ra[0] + min(留前, (ra[1] - ra[0]) / 2), ra[1])
        else:
            疑.append("前一句后面没有安静的地方，刀落在连着说话的地方")
            A = 最静(wa["止"] + min(0.02, 后静 / 2), wa["止"] + 后静 - 0.01, wa["止"] + 留前) if 后静 >= 0.03 else wa["止"] + 后静 / 2
        if rb: B = max(rb[1] - min(留后, (rb[1] - rb[0]) / 2), rb[0])
        else:
            疑.append("后一句前面没有安静的地方，刀落在连着说话的地方")
            B = 最静(wb["起"] - 前静 + 0.01, wb["起"] - min(0.02, 前静 / 2), wb["起"] - 留后) if 前静 >= 0.03 else wb["起"] - 前静 / 2
        类 = "删词"
    if fps:
        A = round(A * fps) / fps; B = round(B * fps) / fps
        if B <= A: continue
    if 吵(A): 疑.append(f"出刀处不够安静（比底噪响 {响[格(A)] - 底:.0f} 分贝）")
    if 吵(B): 疑.append(f"入刀处不够安静（比底噪响 {响[格(B)] - 底:.0f} 分贝）")
    if A - 起 <= 0.001 and not 缝:            # 片头那一段什么都没留：直接从入刀处开始
        起 = B; continue
    if A - 起 <= 0.001 and 缝:                 # 前一刀和这一刀之间什么都没留：两刀并成一刀
        前 = 缝[-1]; 前.update({"后字": wb["id"], "入刀": round(B, 3), "可疑": 前["可疑"] + 疑, "类": "删词",
                               "删掉的话": (前["删掉的话"] + " " + g.连字(词们[x + 1:y])).strip(),
                               "上下文": 前["上下文"].split("‸")[0] + "‸" + g.连字(词们[y:y + 7])})
        起 = B; continue
    段.append([起, A]); 起 = B
    缝.append({"类": 类, "档": 名, "前字": wa["id"], "后字": wb["id"], "出刀": round(A, 3), "入刀": round(B, 3),
              "删掉的话": g.连字(词们[x + 1:y]) if not 连着 else "", "可疑": 疑,
              "上下文": g.连字(词们[max(0, x - 7):x + 1]) + "‸" + g.连字(词们[y:y + 7])})
末 = 词们[留[-1]]["止"]
尾静 = (词们[留[-1] + 1]["起"] - 0.02 if 留[-1] + 1 < len(词们) else 时长) - 末
段.append([起, min(时长, 末 + max(0.0, min(0.25, 尾静)))])
if fps: 段 = [[round(s * fps) / fps, round(e * fps) / fps] for s, e in 段]
if len(段) != len(缝) + 1 or any(e - s <= 0.001 for s, e in 段): g.出错("内部错误：段和刀口对不上，请把工作目录发给作者")
t = 0.0; 表 = []
for k, (s, e) in enumerate(段):
    表.append({"源起": round(s, 4), "源止": round(e, 4), "剪后起": round(t, 4)})
    if k: 缝[k - 1]["剪后秒"] = round(t, 3)
    t += e - s
剪后长 = t

# 3. 出声音：整段解码成 wav，按段切、接缝两边各 5 毫秒淡入淡出
tmp = tempfile.mkdtemp(prefix="chengfeng-videocut-koubo-")
全 = os.path.join(tmp, "全.wav")
subprocess.run([FF, "-nostdin", "-v", "error", "-y", "-i", 源, "-vn", "-c:a", "pcm_s16le", "-ar", str(信息["采样率"]), 全], check=True)
with wave.open(全, "rb") as r:
    ch, sw, sr = r.getnchannels(), r.getsampwidth(), r.getframerate(); 帧 = r.readframes(r.getnframes())
淡 = int(sr * 0.005)
def 片(s, e):
    b = array.array("h"); b.frombytes(帧[int(round(s * sr)) * ch * sw:int(round(e * sr)) * ch * sw])
    n = len(b) // ch
    for q in range(min(淡, n // 2)):
        f = q / 淡
        for c in range(ch):
            b[q * ch + c] = int(b[q * ch + c] * f); b[(n - 1 - q) * ch + c] = int(b[(n - 1 - q) * ch + c] * f)
    return b.tobytes()
出声 = os.path.join(W, "剪后.wav")
with wave.open(出声, "wb") as o:
    o.setnchannels(ch); o.setsampwidth(sw); o.setframerate(sr)
    for s, e in 段: o.writeframes(片(s, e))

# 4. 出画面：每段单独精确截出来再拼，最后配上剪好的声音
出片 = None
if fps:
    def 截(k):
        s, e = 段[k]; p = os.path.join(tmp, f"v{k:05d}.mp4")
        subprocess.run([FF, "-nostdin", "-v", "error", "-y", "-ss", f"{s:.4f}", "-i", 源, "-frames:v", str(round((e - s) * fps)), "-an",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", f"{fps:g}", p], check=True)
        return p
    with cf.ThreadPoolExecutor(4) as ex: 片们 = list(ex.map(截, range(len(段))))
    单 = os.path.join(tmp, "单.txt"); open(单, "w").write("".join(f"file '{p}'\n" for p in 片们))
    画 = os.path.join(tmp, "画.mp4")
    subprocess.run([FF, "-nostdin", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", 单, "-c", "copy", 画], check=True)
    出片 = os.path.join(W, "剪后.mp4")
    subprocess.run([FF, "-nostdin", "-v", "error", "-y", "-i", 画, "-i", 出声, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", 出片], check=True)
    画长 = g.媒体信息(出片)["时长"]
    if abs(画长 - 剪后长) > 0.2: print(f"注意：画面 {画长:.2f} 秒、声音 {剪后长:.2f} 秒，对不齐", file=sys.stderr)

g.写(os.path.join(W, "剪辑表.json"), {"源": 源, "原长": round(时长, 3), "剪后长": round(剪后长, 3), "段": 表, "刀口": 缝,
                                    "停顿档": 档, "压停顿": not a.不压停顿})
待 = [c for c in 缝 if c["可疑"]]
行 = [f"# 接缝待听（{len(待)} 处）", "", "机器只看了响度和停顿，没人听过。每处在剪后音频里前后各听 2 秒。", ""]
for c in 待:
    行.append(f"- 剪后 {g.秒(c['剪后秒'])}｜{c['类']}｜{c['上下文']}｜删掉：{c['删掉的话'] or '（压停顿）'}｜{'；'.join(c['可疑'])}")
open(os.path.join(W, "接缝待听.md"), "w", encoding="utf-8").write("\n".join(行) + "\n")
n删 = sum(1 for c in 缝 if c["类"] == "删词")
print(f"剪好了：{g.秒(时长)} → {g.秒(剪后长)}；删词刀口 {n删} 处，压停顿 {len(缝) - n删} 处，接缝待听 {len(待)} 处 → {出声}" + (f"、{出片}" if 出片 else ""))
