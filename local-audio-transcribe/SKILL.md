---
name: local-audio-transcribe
description: 在 macOS（Apple Silicon）上把本地音频/录音转成文字，全本地推理、不联网、不上传。首选 MLX Whisper large-v3-turbo 走 GPU（实测 79 分钟音频 130 秒完成），覆盖：Apple 语音备忘录 .qta / m4a / mp3 解码转 16k mono wav、长音频转录、健身房/会议等远场嘈杂录音的幻觉抑制、双版本交叉验证过滤幻觉、输出 txt/srt/json。记录本机已踩过的坑：faster-whisper 本地 medium 模型 model.bin 可能残缺（需从 HF 重下）、CPU 跑长音频慢到不可用、brew install whisper-cpp 被本机 brew sandbox 拒绝、pip install mlx-whisper 会被 SIGKILL 137（需 pip download + 手动解包）。触发词：转录、语音转文字、whisper、本地 whisper、录音转文字、语音备忘录转录、qta 转文字、会议录音转写、把这段录音整理成文字。
version: 1.0.0
agent_created: true
metadata:
  short-description: macOS 本地 Whisper 音频转录
---

# macOS 本地音频转录（MLX Whisper）

全本地推理，音频不出本机。目标：给定任意录音文件，产出带时间戳的 txt / srt / json。

## 0. 选型结论（先看这个）

| 方案 | 本机实测 | 结论 |
|---|---|---|
| **MLX Whisper large-v3-turbo（GPU）** | 79 分钟音频 **130 秒**，中文质量最好 | **首选** |
| faster-whisper small（CPU，int8） | 79 分钟音频 168 秒，但中文错字多、VAD 会整段丢内容 | 仅作质量对照，不单独用 |
| faster-whisper medium（CPU，int8） | 4 分钟音频约 100–230 秒 → 79 分钟需 **40+ 分钟** | 不可接受 |
| whisper.cpp（Metal） | 本机 `brew install whisper-cpp` 失败，见 §4 | 未走通 |

环境前提：Apple Silicon（M 系列）。本机 Python 环境 `~/.workbuddy/binaries/python/envs/default`。

## 1. 转码：任意格式 → 16k 单声道 wav

```bash
ffmpeg -y -i input.qta -vn -ac 1 -ar 16000 -c:a pcm_s16le out.wav
ffprobe -v error -show_format -show_streams input.qta | grep -E "codec_name|duration|channels"
```

- Apple 语音备忘录 `.qta` 实际是 `mov/mp4/m4a` 容器 + AAC；`ffmpeg` 直接读得到。
- `.qta` 里常带 Spatial Audio 的额外音轨（`channels=4` 的 unknown stream），转 mono 时自动忽略，不影响人声。
- 79 分钟 ≈ 148 MB wav / 16kHz mono。先 `cp` 一份到工作区：语音备忘录的路径在 `~/Library/Containers/com.apple.VoiceMemos/Data/tmp/.com.apple.uikit.itemprovider.temporary.*/`，属临时目录，随时可能被系统清掉。

## 2. 安装 mlx-whisper（关键：不要直接 pip install）

```bash
PY=/Users/$USER/.workbuddy/binaries/python/envs/default/bin/python

# 1) 核心包可以正常装
$PY -m pip install mlx scipy more-itertools tqdm huggingface_hub tiktoken numba

# 2) mlx-whisper 本体直接 pip install 会被 SIGKILL(137) —— 改用手动解包
$PY -m pip download --no-deps mlx-whisper -d /tmp/mw
SP=$($PY -c "import site;print(site.getsitepackages()[0])")
unzip -o -q /tmp/mw/mlx_whisper-*.whl -d "$SP"

# 3) 验证
$PY -c "import mlx_whisper; print('OK')"
```

若 `import mlx_whisper` 报 `ModuleNotFoundError`，缺什么装什么（历史上缺过 `scipy`）。

模型权重首次运行自动从 HF 拉到 `~/.cache/huggingface`：`mlx-community/whisper-large-v3-turbo`（约 1.6 GB）+ `openai/whisper-large-v3-turbo` 的 tokenizer 类文件。网络可达 `huggingface.co` 时不用手动下。

## 3. 转录

用本 skill 附带的 `scripts/mlx_transcribe.py`（改 `PROMPT` 适应当前领域）：

```bash
$PY scripts/mlx_transcribe.py out.wav prefix
# 产出 prefix.txt / prefix.srt / prefix.json / prefix.plain.txt
```

核心参数：

- `language="zh"` —— 显式指定，别让它自动检测。
- `initial_prompt` —— **强烈建议写一段含领域专有名词的句子**（如"健身教练讲解杠铃卧推、握距、肩胛后缩、组间休息"）。对专有词识别率提升明显。
- `temperature=0` + `condition_on_previous_text=False` —— 降低长音频串味和重复幻觉。

## 4. 幻觉抑制（嘈杂录音必做）

健身房、会议室、公共场合的录音里，背景音乐/噪声段会被模型"强行解码"成周期性重复的假文本（典型特征：同一句重复几十次、出现"中文字幕志愿者""请不吝点赞订阅转发"这类训练集模板句）。**这是数据本身信噪比不足，不是参数没调好。**

两件事一起做：

**a) 提高判定阈值再跑一遍**（作为第二版本，不替换第一版）：

```python
mlx_whisper.transcribe(
    wav, path_or_hf_repo="mlx-community/whisper-large-v3-turbo", language="zh",
    initial_prompt=PROMPT,
    temperature=(0.0, 0.2, 0.4),
    condition_on_previous_text=False,
    no_speech_threshold=0.85,        # 默认 0.6，调高抑制幻听
    compression_ratio_threshold=1.8, # 默认 2.4，调低抑制循环重复
    logprob_threshold=-1.0,
)
```

**b) 双版本交叉验证**（`scripts/crosscheck.py`）：按时间轴重叠 + `SequenceMatcher` 相似度，只保留两版一致的段落。相似度 ≥0.6 记为高置信，0.35–0.6 记中等置信。实测可把幻觉从 ~40% 压到可读水平。

输出 `verified.txt`，**向用户汇报时以高置信段落为事实依据**。

## 5. 已知坑

- **`RuntimeError: File model.bin is incomplete`** —— `~/.workbuddy/models/faster-whisper-medium/model.bin` 历史上是残缺的（233 MB，完整应为 1527906378 B）。修复：从 `https://huggingface.co/Systran/faster-whisper-medium/resolve/main/` 下 `model.bin` / `vocabulary.txt`，并删掉目录里 3 个 15 字节的 `Entry not found` 垃圾文件（`generation_config.json`、`preprocessor_config.json`、`vocabulary.json`）。
- **`brew install whisper-cpp` 失败**：报 `sandbox-exec: sandbox_apply: Operation not permitted`。加 `HOMEBREW_NO_SANDBOX=1` 或沙箱外执行都无效（本机 brew 自身 sandbox 被系统拒绝）。要装 whisper.cpp 需换其他途径。
- **`pip install mlx-whisper` → exit 137**：不是内存不足，用 §2 的 `pip download + unzip` 绕开。
- **不要对长音频用 VAD 过滤**：实测 `vad_filter=True` 会把中间几十秒的有效语音连同噪声一起丢掉（79 分钟音频被砍成只剩前 6 分钟有效内容）。宁可跑两版再交叉验证。
- CPU 分片并行没意义：medium + `shard_worker.py` 三进程三线程跑 10 分钟分片，10 分钟都出不来一片。

## 6. 交付

- 转录产物：`*.txt`（带 `[HH:MM:SS - HH:MM:SS]` 时间戳）、`*.srt`、`*.json`、`*.plain.txt`（无时间戳连排）、`verified.txt`（交叉验证结果）。
- 汇报时**必须区分**：录音中确证的内容 / 未辨识到的内容 / 补充的标准知识。远场录音必然有信息缺口，不要用常识填空后当成录音原话。
