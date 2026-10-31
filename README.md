# LCMD

LCMD 是面向命令行用户的简体中文命令速查与学习工具。

核心理念：少记忆，易理解；需要时快速查找。

LCMD 只提供知识查询，不执行系统命令。

## 开发环境

- Python 3.11 或更高版本
- Git

## 本地开发（Windows）

创建虚拟环境：

    py -3 -m venv .venv

安装开发依赖：

    .\.venv\Scripts\python.exe -m pip install -e ".[dev]"

运行程序：

    .\.venv\Scripts\lcmd.exe --help

运行测试：

    .\.venv\Scripts\python.exe -m pytest

代码检查：

    .\.venv\Scripts\ruff.exe check .

代码格式检查：

    .\.venv\Scripts\ruff.exe format --check .

## 项目文档

项目架构、开发阶段和实际进度统一记录在 LCMD-DEV.md。
