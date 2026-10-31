"""LCMD 主程序入口."""

from lcmd.cli.app import app


def main() -> None:
    """启动 LCMD CLI。"""
    app()
