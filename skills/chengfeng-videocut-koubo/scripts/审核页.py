#!/usr/bin/env python3
"""第 7 步 审核页：出一个本地网页，两张表 + 剪后和原声两个播放器，点哪条就跳到哪儿听。浏览器直接打开，不用装别的。

用法：python3 审核页.py <工作目录>   →  <工作目录>/审核页.html
"""
import html, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import 共用 as g

W = os.path.abspath(sys.argv[1]); E = html.escape
稿 = g.读(os.path.join(W, "逐字.json")); 结果 = g.读(os.path.join(W, "删词结果.json")); 表 = g.读(os.path.join(W, "剪辑表.json"))
核 = g.读(os.path.join(W, "核对.json")) if os.path.exists(os.path.join(W, "核对.json")) else None
词们 = 稿["词"]; 位 = {w["id"]: i for i, w in enumerate(词们)}; 删 = set(结果["删"])
按后字 = {c["后字"]: c for c in 表["刀口"]}
def 剪后秒(ids):
    j = 位[ids[-1]] + 1
    while j < len(词们) and 词们[j]["id"] in 删: j += 1
    c = 按后字.get(词们[j]["id"]) if j < len(词们) else None
    return c["剪后秒"] if c else 表["剪后长"]
有片 = os.path.exists(os.path.join(W, "剪后.mp4"))
剪后 = "剪后.mp4" if 有片 else "剪后.wav"; 原 = os.path.relpath(稿["源"], W)
def 钮(t, 哪, 字): return f'<button onclick="跳(\'{哪}\',{max(t - 2, 0):.2f})">{字}</button>'
行 = []
for n, c in enumerate(结果["条"], 1):
    t = 剪后秒(c["ids"])
    行.append(f"<tr><td>{n}</td><td>{g.秒(c['起'])}</td><td>{E(c['类'])}</td><td><del>{E(c['删除'])}</del></td>"
              f"<td>{E(c['剩下读作'])}</td><td>{E(c['风险'])}</td><td>{钮(c['起'] + 1, '原', '听原声')}{钮(t, '剪', '听剪后')}</td></tr>")
重 = "".join(f"<tr><td>{E(str(r.get('句子', '')))}</td><td>{E(str(r.get('说了几遍', '')))}</td><td>{E(str(r.get('保了哪遍', '')))}</td>"
            f"<td>{E(str(r.get('删了哪几遍', '')))}</td><td>{E(str(r.get('风险', '')))}</td></tr>" for r in 结果.get("重复句子", [])) \
     or '<tr><td colspan="5">没有说了多遍的句子</td></tr>'
待 = [c for c in 表["刀口"] if c["可疑"]]
待行 = "".join(f"<li>{钮(c['剪后秒'], '剪', g.秒(c['剪后秒']))} {E(c['上下文'])}　<span class=m>{E('；'.join(c['可疑']))}</span></li>" for c in 待) or "<li>没有</li>"
核行 = ""
if 核:
    核行 = "".join(f"<li>{钮(f['剪后秒'], '剪', g.秒(f['剪后秒']))} {E(f['类'])}：听到「{E(f['听到'])}」应是「{E(f['应是'])}」　<span class=m>{E(f['上下文'])}</span></li>"
                  for f in 核["要回去听"]) or "<li>0 条</li>"
媒 = f'<video id="剪" src="{E(剪后)}" controls></video>' if 有片 else f'<audio id="剪" src="{E(剪后)}" controls></audio>'
页 = f"""<!doctype html><meta charset="utf-8"><title>剪口播审核：{E(os.path.basename(稿['源']))}</title>
<style>body{{font:15px/1.6 -apple-system,"PingFang SC",sans-serif;max-width:1100px;margin:24px auto;padding:0 16px;color:#1b1b1d}}
table{{border-collapse:collapse;width:100%;margin:8px 0 24px}}td,th{{border-bottom:1px solid #e3ded4;padding:6px 8px;text-align:left;vertical-align:top}}
del{{color:#b3261e}}button{{font-size:12px;margin:0 4px 2px 0}}.m{{color:#6b6760}}.播{{position:sticky;top:0;background:#fff;padding:8px 0;border-bottom:1px solid #e3ded4}}
audio,video{{width:100%;max-height:240px}}h2{{margin-top:28px}}</style>
<h1>剪口播审核</h1>
<p>{E(os.path.basename(稿['源']))}：{g.秒(表['原长'])} → {g.秒(表['剪后长'])}，删 {len(结果['条'])} 处</p>
<div class="播"><div>剪后</div>{媒}<div>原声</div><audio id="原" src="{E(原)}" controls></audio></div>
<h2>删词汇总表</h2><table><tr><th>#</th><th>时间</th><th>类型</th><th>删除</th><th>剩下读作</th><th>风险</th><th></th></tr>{''.join(行)}</table>
<h2>重复句子表</h2><table><tr><th>句子（开头）</th><th>说了几遍</th><th>保了哪遍</th><th>删了哪几遍</th><th>风险</th></tr>{重}</table>
<h2>接缝待听</h2><ul>{待行}</ul>
{'<h2>剪后核对要回去听的</h2><ul>' + 核行 + '</ul>' if 核 else ''}
<script>function 跳(哪,t){{const m=document.getElementById(哪==='剪'?'剪':'原');document.querySelectorAll('audio,video').forEach(x=>x!==m&&x.pause());m.currentTime=t;m.play()}}</script>
"""
open(os.path.join(W, "审核页.html"), "w", encoding="utf-8").write(页)
print(f"审核页 → {W}/审核页.html")
