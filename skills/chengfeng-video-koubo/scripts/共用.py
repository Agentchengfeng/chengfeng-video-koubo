"""剪口播各脚本共用：配置、ffmpeg、豆包录音文件识别、读写工作目录。只用 Python 标准库。"""
import base64, json, os, re, shutil, subprocess, sys, tempfile, time, urllib.error, urllib.request, uuid

配置目录 = os.path.expanduser("~/.chengfeng-video-koubo")
if not os.path.isdir(配置目录) and os.path.isdir(os.path.expanduser("~/.chengfeng-videocut-koubo")):
    配置目录 = os.path.expanduser("~/.chengfeng-videocut-koubo")  # 改名前（chengfeng-videocut-koubo）的设置；装新版时会拷到新位置
标点句末 = set("。？！?!…")
标点逗号 = set("，、；：,;:—")
标点全部 = 标点句末 | 标点逗号 | set("“”‘’\"'（）()《》〈〉「」『』[]【】·-.")


def 出错(话, 码=1):
    print(话, file=sys.stderr); sys.exit(码)


def 工具(名):
    p = shutil.which(名)
    if p: return p
    for d in ("/opt/homebrew/bin", "/usr/local/bin"):
        if os.path.exists(os.path.join(d, 名)): return os.path.join(d, 名)
    出错(f"找不到 {名}：先装 ffmpeg（macOS：brew install ffmpeg）")


def 读(p):
    with open(p, encoding="utf-8") as f: return json.load(f)


def 写(p, d):
    with open(p, "w", encoding="utf-8") as f: json.dump(d, f, ensure_ascii=False, indent=1)


def 规整(s):
    return re.sub(r"[\s\W_]+", "", s or "").lower()


def 秒(t):
    m, s = divmod(max(t, 0), 60)
    return f"{int(m):02d}:{s:04.1f}"


def 媒体信息(p):
    r = subprocess.run([工具("ffprobe"), "-v", "error", "-show_entries", "format=duration:stream=codec_type,r_frame_rate,sample_rate,channels",
                        "-of", "json", p], capture_output=True, text=True)
    if r.returncode: 出错(f"读不了这个文件：{p}\n{r.stderr}")
    d = json.loads(r.stdout); 视 = [s for s in d.get("streams", []) if s.get("codec_type") == "video"]
    音 = [s for s in d.get("streams", []) if s.get("codec_type") == "audio"]
    if not 音: 出错("这个文件里没有声音")
    fps = None
    if 视:
        a, b = 视[0].get("r_frame_rate", "0/1").split("/"); fps = float(a) / float(b) if float(b) else None
    return {"时长": float(d["format"]["duration"]), "帧率": fps, "采样率": int(音[0].get("sample_rate", 48000)),
            "声道": int(音[0].get("channels", 1))}


def 配置(键环境, 键文件):
    if os.environ.get(键环境): return os.environ[键环境].strip()
    p = os.path.join(配置目录, "config.json")
    try: v = 读(p).get(键文件)
    except (OSError, ValueError): v = None
    return str(v).strip() if v else None


def 识别(音频, 输出前缀, 热词=(), 接着查=None, 最多等=900):
    """豆包（火山）录音文件识别，返回原始结果。付费：只有提交被拒才换资源再提交；查询超时打印 requestId 退出（码 2）。"""
    key = 配置("VOLCENGINE_API_KEY", "volc_api_key")
    if not key: 出错(f"没有豆包识别 key：设置环境变量 VOLCENGINE_API_KEY，或写进 {配置目录}/config.json 的 volc_api_key")
    rid_env = 配置("VOLCENGINE_ASR_RESOURCE_ID", "volc_resource_id")
    资源们 = [rid_env] if rid_env else ["volc.seedasr.auc", "volc.bigasr.auc"]
    BASE = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/"

    def 调(路径, 体, rid, res):
        req = urllib.request.Request(BASE + 路径, json.dumps(体).encode(), {
            "Content-Type": "application/json", "X-Api-Key": key, "X-Api-Resource-Id": res,
            "X-Api-Request-Id": rid, "X-Api-Sequence": "-1"})
        try:
            r = urllib.request.urlopen(req, timeout=180)
            return r.headers.get("X-Api-Status-Code"), r.headers.get("X-Api-Message"), r.read()
        except urllib.error.HTTPError as e:
            return e.headers.get("X-Api-Status-Code"), e.headers.get("X-Api-Message"), e.read()

    def 查(rid, res):
        到 = time.time() + 最多等
        while time.time() < 到:
            time.sleep(2)
            码, 话, raw = 调("query", {}, rid, res)
            if 码 == "20000000": return json.loads(raw)
            if 码 not in ("20000001", "20000002"): 出错(f"识别查询失败：{码} {话}")
        出错(f"识别还没出结果：加 --接着查 {rid}:{res} 再跑，别重新提交（会再扣一次钱）", 2)

    if 接着查:
        rid, res = 接着查.split(":", 1); d = 查(rid, res)
    else:
        wav = os.path.join(tempfile.mkdtemp(), "a16.wav")
        subprocess.run([工具("ffmpeg"), "-nostdin", "-v", "error", "-y", "-i", 音频, "-vn", "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav], check=True)
        数据 = base64.b64encode(open(wav, "rb").read()).decode(); os.remove(wav)
        d = None
        for res in 资源们:
            rid = uuid.uuid4().hex
            请求 = {"model_name": "bigmodel", "enable_itn": True, "enable_punc": True, "show_utterances": True}
            热 = [w.strip() for w in 热词 if w.strip()]
            if 热: 请求["corpus"] = {"context": json.dumps({"hotwords": [{"word": w} for w in 热]}, ensure_ascii=False)}
            体 = {"user": {"uid": "chengfeng-video-koubo"}, "audio": {"data": 数据, "format": "wav", "codec": "raw", "rate": 16000,
                  "bits": 16, "channel": 1, "language": "zh-CN"}, "request": 请求}
            码, 话, _ = 调("submit", 体, rid, res)
            print(f"提交识别（{res}）：{码} {话}", file=sys.stderr)
            if 码 == "20000000":
                print(f"  任务号 {rid}:{res}（查询超时就用它接着查）", file=sys.stderr); d = 查(rid, res); break
        if d is None: 出错("识别提交都被拒：看上面的状态码（45000xxx 多半是这把 key 没开通录音文件识别）")
    写(输出前缀 + ".json", d)
    return d


def 拆词(识别结果):
    """把识别结果拆成逐字（中文一字一个，英文/数字一词一个），标点挂在前一个字上。"""
    词们 = []
    for u in 识别结果.get("result", {}).get("utterances", []):
        文 = u.get("text", ""); p = 0
        ws = [w for w in u.get("words", []) if 规整(w.get("text"))]
        for k, w in enumerate(ws):
            t = w["text"].strip(); 低 = 文.lower()
            q = 低.find(t.lower(), p)
            if q < 0 or q - p > 12: q = p
            else: p = q + len(t)
            标 = ""
            while p < len(文) and (文[p] in 标点全部 or 文[p].isspace()):
                if not 文[p].isspace(): 标 += 文[p]
                p += 1
            词们.append({"字": t, "起": w["start_time"] / 1000, "止": w["end_time"] / 1000, "标点": 标})
        if 词们 and not (set(词们[-1]["标点"]) & 标点句末): 词们[-1]["句末"] = True   # 一段识别结束也当句子结束
    for i, w in enumerate(词们): w["id"] = f"w{i + 1:04d}"
    return 词们


def 连字(ws):
    """把一串字连成一句话：两个英文/数字词之间留空格，标点照挂。"""
    out = ""
    for x in ws:
        t = x["字"]
        if out and t and re.match(r"[A-Za-z0-9]", t) and re.search(r"[A-Za-z0-9]$", out): out += " "
        out += t + x.get("标点", "")
    return out


def 分句(词们):
    句们, 首 = [], 0
    for i, w in enumerate(词们):
        if set(w["标点"]) & 标点句末 or w.get("句末") or i == len(词们) - 1:
            sid = f"s{len(句们) + 1:03d}"
            for x in 词们[首:i + 1]: x["句"] = sid
            句们.append({"id": sid, "首": 词们[首]["id"], "尾": w["id"], "起": 词们[首]["起"], "止": w["止"], "文": 连字(词们[首:i + 1])})
            首 = i + 1
    return 句们


def 写逐字稿(工作目录, 稿):
    词们, 句们 = 稿["词"], 稿["句"]; 位 = {w["id"]: i for i, w in enumerate(词们)}
    行 = [f"# 逐字稿：{os.path.basename(稿['源'])}（{秒(稿['时长'])}，{len(句们)} 句，{len(词们)} 字）",
          "# 每行一句：句号  字号范围  开始时间  原话。删词时照抄原话里的字，或写字号范围。", ""]
    for k, s in enumerate(句们):
        i0 = 位[s["首"]]
        停 = 词们[i0]["起"] - (词们[i0 - 1]["止"] if i0 else 0)
        if 停 >= 0.8: 行.append(f"        （停 {停:.1f} 秒）")
        行.append(f"{s['id']}  [{s['首']}–{s['尾']}]  {秒(s['起'])}  {s['文']}")
        长 = [w for w in 词们[i0:位[s["尾"]] + 1] if not re.search(r"\d", w["字"]) and w["字"]
             and w["止"] - w["起"] >= (0.9 if len(w["字"]) > 1 else 0.6)]
        if 长: 行.append("        〔拖长：" + "，".join(f"{w['id']}「{w['字']}」{w['止'] - w['起']:.2f} 秒" for w in 长) + "〕")
    open(os.path.join(工作目录, "逐字稿.txt"), "w", encoding="utf-8").write("\n".join(行) + "\n")


def 找字(稿, sid, 文, 第几=None):
    """在一句里找一串原话，返回（头一个字的序号，最后一个字的序号）。头尾必须是完整的字。"""
    词们 = 稿["词"]; 位 = {w["id"]: i for i, w in enumerate(词们)}; 句 = {s["id"]: s for s in 稿["句"]}
    s = 句.get(sid)
    if not s: 出错(f"没有这一句：{sid}")
    串, 归 = "", []
    for i in range(位[s["首"]], 位[s["尾"]] + 1):
        t = 规整(词们[i]["字"]); 串 += t; 归 += [i] * len(t)
    目 = 规整(文)
    if not 目: 出错(f"{sid} 要找的字是空的")
    处, p = [], 串.find(目)
    while p >= 0:
        头, 尾 = 归[p], 归[p + len(目) - 1]
        if (p == 0 or 归[p - 1] != 头) and (p + len(目) == len(串) or 归[p + len(目)] != 尾): 处.append((头, 尾))
        p = 串.find(目, p + 1)
    if not 处: 出错(f"{sid} 里找不到“{文}”（或者它切在了英文词中间）。这一句是：{s['文']}")
    if len(处) > 1 and not 第几: 出错(f"{sid} 里“{文}”出现了 {len(处)} 次，写上 \"第几处\"")
    if 第几 and 第几 > len(处): 出错(f"{sid} 里“{文}”只有 {len(处)} 处")
    return 处[(第几 or 1) - 1]
