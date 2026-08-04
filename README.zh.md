# Agent Skills

[English](README.md) | 简体中文

> 为 AI 驱动的开发工具提供实用 Agent 技能集合。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub stars](https://img.shields.io/github/stars/carton/agent-skills?style=social)](https://github.com/carton/agent-skills)

## 概述

本仓库包含一系列可复用的 agent 技能，旨在扩展 Claude Code、Cursor 及其他兼容工具等 AI 编程助手的能力。

## 快速开始

### 安装方式

#### 方式 1：使用 npx skills（推荐）

```bash
npx skills add carton/agent-skills
```

#### 方式 2：注册为插件市场

在 Claude Code 中运行以下命令：

```
/plugin marketplace add carton/agent-skills
```

然后浏览和安装可用技能：

```
/plugin
```

导航到 **Marketplaces** 标签 → 选择 **agent-skills** → 安装所需技能

#### 方式 3：手动安装

```bash
# 克隆仓库
git clone https://github.com/carton/agent-skills.git

# 复制技能到你的 Claude skills 目录
cp -r agent-skills/skills/* ~/.claude/skills/
```

### 使用方法

安装后，技能会自动可用。你可以通过名称调用它们：

```
请帮我管理我的 Epic Games 游戏库
```

Claude 会自动加载并使用相应的技能。

## 可用技能

### 🎮 游戏库与商店工具

#### [epic-cli](skills/epic-cli/SKILL.md)

使用 Legendary 在终端中管理 Epic Games 游戏库。

**使用场景：** 浏览已拥有的 Epic 游戏、安装或启动游戏、检查更新，或同步云存档。

#### [steam-cli](skills/steam-cli/SKILL.md)

管理自己拥有的 Steam 游戏库、查询 Steam 商店信息，并估算安装所需磁盘空间。

**使用场景：** 查找未玩游戏、查看游玩时长、导出已拥有游戏列表、查询商店详情或区域价格，或确认游戏所需磁盘空间。

### 📱 Android 诊断

#### [android-logcat-analyzer](skills/android-logcat-analyzer/SKILL.md)

分析 Android logcat 日志，定位崩溃、ANR、内存和性能问题。

**使用场景：** Android 应用崩溃、出现 ANR、被系统意外杀死、发生内存泄漏，或存在卡顿和掉帧时。

### 🔧 开发工作流

#### [commit-message](skills/commit-message/SKILL.md)

基于实际 Git diff 生成准确的 Conventional Commit 提交信息。

**使用场景：** 编写或审查提交标题与正文，或准备 squash 合并提交信息时。

#### [reverse-to-readable-c](skills/reverse-to-readable-c/SKILL.md)

通过分阶段的逆向工程流程，将原生 PE 或 ELF 二进制文件整理为可维护的 C 源码树。

**使用场景：** 探索二进制文件、分类函数、反编译模块、重命名符号，或将反编译输出清理为可读 C 代码时。

### 📝 内容归档

#### [make-bilibili-notes](skills/make-bilibili-notes/SKILL.md)

将 Bilibili 视频转为带时间戳、可追溯的 Obsidian Markdown 笔记。

**使用场景：** 总结、转录、事实核查或归档 Bilibili 视频时；流程会依次优先使用官方字幕、硬字幕 OCR 和音频转录。

## 开发

### 本地测试

在本地测试技能：

```bash
# 创建指向你技能目录的符号链接
ln -s /path/to/agent-skills/skills/* ~/.claude/skills/
```

### 验证

技能会自动验证以确保：
- 有效的 frontmatter 格式
- 必需字段（name、description）
- 正确的 markdown 结构

## 路线图

- [ ] 添加更多游戏平台集成
- [ ] 添加开发工具技能
- [ ] 添加内容生成技能
- [ ] 添加自动化实用工具

## 灵感来源

本仓库灵感来自：
- [baoyu-skills](https://github.com/JimLiu/baoyu-skills) by Jim Liu
- [agent-skills](https://github.com/vercel-labs/agent-skills) by Vercel Labs

## 许可证

MIT License - 详见 [LICENSE](LICENSE)

## 致谢

- 为 Claude Code 生态系统构建
- 由 [Agent Skills Specification](https://github.com/agent-skills/spec) 提供支持
- 更广泛的技能市场生态系统的一部分

---

由 [Carton He](https://github.com/carton) 用 ❤️ 制作
