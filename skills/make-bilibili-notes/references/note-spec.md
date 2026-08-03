# Obsidian note specification

## Frontmatter

Use this schema and fill only verified values:

```yaml
---
title: 视频标题
source: Bilibili
url: https://www.bilibili.com/video/BV.../
author: UP主
published: YYYY-MM-DD
duration: "HH:MM:SS"
created: YYYY-MM-DD
transcript_source: official_subtitle | hard_subtitle_ocr | hard_subtitle_vision | audio_asr
tags:
  - video-notes
  - domain-tag
---
```

Tags must be concise English kebab-case. Repeat them as Obsidian hashtags below
the H1, for example:

```markdown
#complexity-science #systems-thinking #video-notes
```

## Required note structure

```markdown
# 视频标题

#english-tags #video-notes

> [!summary] 一句话结论
> 用一到三句说明视频解决的问题、核心结论和最重要限制。

## 核心要点

- 带时间戳的要点。

## 时间线

### 00:00–03:20 小节标题

说明该段论证、例子与结论。保持视频实际顺序。

## 完整笔记

### 00:00–03:20 小节标题

把这一时段的全部实质内容整理成连贯、正式的书面文本。继续按时间顺序覆盖
后续时段，直到视频结束。

## 视频原观点与外部核查

明确区分：

- **视频原观点**：来自字幕/音频/画面的陈述。
- **外部核查**：由独立来源支持、修正或反驳的内容。
- **AI 补充解释**：为帮助理解而加入，但并非视频原话。

## 局限与待核实项

- 记录含混字幕、缺失上下文、无法验证的数字或引用。

## 来源

- [原视频](URL)
- 外部来源只列实际读过且直接支持正文主张的页面。
```

Do not add a `处理记录` section or equivalent implementation history to the
note.

## Complete-note fidelity

`完整笔记` is a faithful full-content rewrite, not an expanded summary. Preserve
the source order and every substantive claim, explanation, example, condition,
contrast, transition, caveat, and conclusion. You may:

- remove filler words, stutters, false starts, and exact repetitions;
- repair punctuation, sentence boundaries, and obvious pronoun references;
- organize consecutive speech into readable paragraphs and timestamped
  subsections;
- translate non-Chinese speech faithfully into Chinese, retaining important
  source-language technical terms on first mention.

Do not compress away reasoning steps, examples, qualifications, or repeated
ideas that add meaning. Do not introduce facts from the summary, external
research, or general knowledge. If extraction is incomplete, mark the missing
range at the relevant location and disclose the coverage limit.

## Separate processing log

Keep processing history outside the note in one UTF-8 plain-text `processing.log`
in the same output directory. Append one entry per video or part using this
compact shape:

```text
[YYYY-MM-DD HH:MM] 视频标题或分 P
output=正式笔记文件名
url=原视频 URL
source=官方字幕/硬字幕 OCR/视觉识别/音频 ASR
engine=实际使用的引擎与模型
qa=抽查位置与结论
external_processing=例如 Colab 上传与远端清理；没有则写“无”
fallbacks=认证限制、错挂字幕、失败路径及采取的回退
unresolved=仍可能影响转写完整性或准确性的内容
```

Do not copy this log into the note. Reader-facing uncertainty about the video's
claims belongs in `局限与待核实项`; extraction mechanics and tool history belong
only in `processing.log`.

## Writing rules

- 先完成转录 QA，再做摘要。
- 重要结论带时间戳；不要伪造逐字准确度。
- `完整笔记` 紧跟在 `时间线` 后，覆盖全部实质内容，只清理不承载语义的口语
  噪声，不做摘要式删减。
- 不把视频中的产品展示、个人经验或动画示意图写成证据。
- 外部解释必须有标记，不能混入“视频原观点”。
- PPT 型视频只保存能够补充文本的稳定帧，并在图片说明中写时间戳。
- 使用 `$$...$$` 表示块级 LaTeX，以兼容 ChatGPT 与 Obsidian。
