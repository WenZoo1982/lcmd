"""LCMD 命令行程序入口。"""

from lcmd.cli.app import create_app


def main() -> None:
    """启动 LCMD 命令行应用。"""
    app = create_app()
    app()
