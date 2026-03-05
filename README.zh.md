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

### 🎮 游戏工具

#### epic-cli

Epic Games 游戏库管理 CLI 工具。使用 Legendary 从终端浏览、安装、启动、同步存档和管理你的 Epic Games 游戏库。

**使用场景：** 管理 Epic Games、安装游戏、同步云存档或浏览 Epic 游戏收藏时。

**功能特性：**
- 列出和浏览 Epic Games 游戏库
- 安装和启动游戏
- 同步云存档
- 检查更新
- 跨平台支持（Linux、macOS、Windows）

**文档：** 详细用法请参阅 [skills/epic-cli/SKILL.md](skills/epic-cli/SKILL.md)

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
