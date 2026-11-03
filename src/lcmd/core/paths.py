from pathlib import Path

from platformdirs import user_config_path, user_data_path

_APP_NAME = "lcmd"


def get_config_dir() -> Path:
    """获取 LCMD 用户配置目录。"""
    return Path(user_config_path(_APP_NAME, appauthor=False))


def get_config_file() -> Path:
    """获取 LCMD 配置文件路径。"""
    return get_config_dir() / "config.toml"


def get_data_dir() -> Path:
    """获取 LCMD 用户数据目录。"""
    return Path(user_data_path(_APP_NAME, appauthor=False))


def get_default_knowledge_path() -> Path:
    """获取默认知识库目录。"""
    return get_data_dir() / "knowledge"
