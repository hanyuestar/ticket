# -*- coding: utf-8 -*-
"""
动态配置管理器
用于 Web 端添加/删除的 12306 账号和抢票任务的持久化存储
存储在 RUNTIME_DIR/config.json，容器重启后自动恢复
"""
import json
import os

from py12306.config import Config


def get_dynamic_config_path():
    """获取动态配置文件路径"""
    return os.path.join(Config().RUNTIME_DIR, 'config.json')


def load_dynamic_config():
    """
    从动态配置文件加载账号和任务，覆盖 env.py 中的配置
    在 Config 初始化完成后调用
    """
    path = get_dynamic_config_path()
    if not os.path.exists(path):
        return False
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data.get('USER_ACCOUNTS'), list):
            Config().USER_ACCOUNTS = data['USER_ACCOUNTS']
        if isinstance(data.get('QUERY_JOBS'), list):
            Config().QUERY_JOBS = data['QUERY_JOBS']
        return True
    except Exception as e:
        print('[config_manager] 加载动态配置失败: {}'.format(e))
        return False


def save_dynamic_config():
    """
    将当前内存中的账号和任务保存到动态配置文件
    Web API 修改配置后调用
    """
    path = get_dynamic_config_path()
    data = {
        'USER_ACCOUNTS': Config().USER_ACCOUNTS,
        'QUERY_JOBS': Config().QUERY_JOBS,
    }
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print('[config_manager] 保存动态配置失败: {}'.format(e))
        return False
