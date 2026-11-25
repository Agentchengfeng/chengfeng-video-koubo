# 成峰剪口播 chengfeng-videocut-koubo

> 自己录的口播，交给 AI 剪：口误、重复、重录剪掉，停顿压短，剪完给你一张能逐条试听的审核页。

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

录口播很少一遍过：一句话起了三次头，说错一个数字又重说一遍，中间还停了好几秒。一句句去找、去剪，很费时间。

成峰剪口播是一个给 Claude Code / Codex 等 Agent 用的 Skill。AI 先把录音转成逐字稿，每个字都带时间；从头读一遍，同一句录了好几遍的、说一半断掉的、说错又重说的，删前面那遍，留后面说对的那遍；然后真的剪，太长的停顿按标点压短；剪完再让识别把剪好的声音听一遍，逐字对，看有没有漏删、切坏的字；最后出一张审核页，删了哪句，点一下就能听。

不用装剪辑软件。

## 实测

一条 2 分 30 秒的真人口播：

- 剪到 1 分 48 秒。
- AI 第一遍删了 11 处。跟作者自己审过的版本按时间逐字比：没有多删，漏了 1 处句首的残词。
- 剪后核对 0 条。有 2 处刀口落在连着说话的地方，机器判不准，单独列出来给人耳听。

## 需要什么

- `python3` 3.8 以上（只用标准库）
- `ffmpeg` / `ffprobe`（macOS：`brew install ffmpeg`）
- 一把豆包（火山引擎）“录音文件识别”的 key，按录音时长计费。每条录音识别两次：剪前一次，剪后核对一次。
- Node.js 18+（只有一键安装要用）

## 安装

最简单的方式：把这句发给你的 AI，它会照着命令装好：

```text
帮我运行这条命令，安装成峰剪口播 Skill：npx -y github:Agentchengfeng/chengfeng-videocut-koubo install
```

自己在终端装也行：

```sh
npx -y github:Agentchengfeng/chengfeng-videocut-koubo install
```

再配好识别 key，二选一：

```sh
export VOLCENGINE_API_KEY=你的key
# 或者写进文件
mkdir -p ~/.chengfeng-videocut-koubo && echo '{"volc_api_key": "你的key"}' > ~/.chengfeng-videocut-koubo/config.json
```

装好后重启 Agent，让它重新加载 Skill 列表。

## 怎么用

直接说：

```text
剪口播：~/录音/今天的口播.mp4
```

```text
把我录的这段剪一下，口误和重复都去掉
```

它会一步步做：

1. **转录**：每个字带时间。
2. **修字**：听错的专名先改对（Claude 被写成 Cloud 这类）。
3. **删词**：先通览整段，找隔得很远的重录；再逐字扫五轮：重复、残句改口、口误重说、英文卡壳、语气词。
4. **汇总**：出两张表（删了什么、剩下读作什么；哪句录了几遍、保了哪遍），AI 先自己把删后全文读一遍，读不通的撤掉。
5. **剪**：真的剪，停顿按标点分档压短，刀口挪到附近最安静的地方。
6. **剪后核对**：识别把剪好的声音再听一遍，逐字对出漏删和切坏的字，到 0 条为止。
7. **审核页**：剪后和原声两个播放器，点哪条听哪条。你说哪里不对，它改了重剪。

你只在两处说话：开头说剪哪条；最后听审核页、说哪里要改。

## 剪出来什么

原素材只读不改。所有东西都在录音旁边的 `<录音名>-剪口播/` 文件夹里：

| 文件 | 是什么 |
|---|---|
| `逐字稿.txt` | 一句一行的稿子，带时间 |
| `两张表.md` | 删词汇总表、重复句子表 |
| `剪后.wav` / `剪后.mp4` | 剪好的人声 / 视频（源是视频才有 mp4） |
| `审核页.html` | 浏览器打开，逐条试听 |
| `接缝待听.md` | 机器拿不准、要人耳听的刀口 |

你的口味和专名会记在 `~/.chengfeng-videocut-koubo/偏好.md`、`词典.md`，剪得越多越合你的习惯。

## 它怎么判断删哪段

- **删前保后**：前一遍不完整、说错的删，后一遍完整、说对的留。
- **先通览再逐字**：先读完整篇找重录，再一轮只带一个判据逐字扫，不一口气什么都找。
- **拿不准就不删**：整句、长段、专名或数字改口都算高风险，AI 自己回稿里前后念一遍，确认不了就不删，不拿去一条条问你。
- **停顿和刀口交给脚本**：AI 只决定删哪几个字；停顿压多少、刀落在哪，按标点和响度算，不靠 AI 猜毫秒。
- **机器核对不等于人耳听过**：报告里写“剪后核对 0 条 / 接缝待听 N 处”，不写成“听过没问题”。

## 不做什么

- 不做字幕、配乐、画面动画。
- 不改原素材。
- 你说出口的话跟事实对不上，不替你删字，列出来让你定。

## 检查与卸载

```sh
npx -y github:Agentchengfeng/chengfeng-videocut-koubo doctor
npx -y github:Agentchengfeng/chengfeng-videocut-koubo uninstall
```

`doctor` 会查 Skill 装好没有，python3、ffmpeg 和识别 key 在不在（只看有没有，不打印 key）。安装器会把 Skill 放进本机 Agent 的 Skill 目录，已有的旧版本会先备份。包里只有说明文件和脚本，不含 API key 或任何个人数据。

## 脚本也能单独用

```sh
S=~/.claude/skills/chengfeng-videocut-koubo/scripts
python3 $S/转录.py 口播.mp4 口播-剪口播 --热词 'Claude,Codex'
python3 $S/修字.py 口播-剪口播 口播-剪口播/修字.json      # 格式见 修字.py 开头
python3 $S/删词.py 口播-剪口播 口播-剪口播/删词.json      # 格式见 删词.py 开头
python3 $S/剪.py 口播-剪口播
python3 $S/核对.py 口播-剪口播 --热词 'Claude,Codex'
python3 $S/审核页.py 口播-剪口播
```

## 仓库结构

```text
chengfeng-videocut-koubo/
├── SKILL.md
├── LICENSE / NOTICE.md / CITATION.cff
├── package.json
├── bin/install.js
└── skills/chengfeng-videocut-koubo/
    ├── SKILL.md
    ├── 更新日志.md
    ├── agents/openai.yaml
    ├── references/            # 删词规则、专名词典、事故簿
    └── scripts/               # 转录、修字、删词、剪、核对、审核页
```

## 官方来源

由 **成峰 / AI产品自由** 创建和维护。

- GitHub：[Agentchengfeng](https://github.com/Agentchengfeng) —— 安装问题和 bug 请提 Issue。
- X：[@chengfeng240928](https://x.com/chengfeng240928)
- 小红书 / 公众号 / B站 / 抖音 / 视频号：AI产品自由

## License

Apache-2.0。见 [LICENSE](LICENSE) 和 [NOTICE.md](NOTICE.md)。使用、翻译、转载或改编时，请保留署名与 NOTICE。
