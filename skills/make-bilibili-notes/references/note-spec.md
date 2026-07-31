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

## 处理记录

- 官方字幕：有/无。
- 内容提取：官方字幕/硬字幕 OCR/视觉识别/音频 ASR。
- OCR/ASR 引擎与模型。
- 人工或模型复核的抽样位置。
- 遇到的问题、采取的回退路径、仍然存在的不确定性。
```

## Writing rules

- 先完成转录 QA，再做摘要。
- 重要结论带时间戳；不要伪造逐字准确度。
- 不把视频中的产品展示、个人经验或动画示意图写成证据。
- 外部解释必须有标记，不能混入“视频原观点”。
- PPT 型视频只保存能够补充文本的稳定帧，并在图片说明中写时间戳。
- 使用 `$$...$$` 表示块级 LaTeX，以兼容 ChatGPT 与 Obsidian。
