# -*- coding: utf-8 -*-
"""
Web 管理 API
支持 12306 账号管理、抢票任务管理、车站搜索、二维码登录
"""
import os
import json
import time

from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required

from py12306.config import Config
from py12306.helpers.func import timestamp_to_time
from py12306.helpers.config_manager import save_dynamic_config
from py12306.helpers.station import Station

manage = Blueprint('manage', __name__)


# ============================================================
# 12306 账号管理
# ============================================================

@manage.route('/manage/accounts', methods=['GET'])
@jwt_required()
def list_accounts():
    """获取所有 12306 账号及状态"""
    from py12306.user.user import User
    from py12306.user.job import UserJob

    result = []
    for account in Config().USER_ACCOUNTS:
        key = str(account.get('key'))
        user_job = User.get_user(key)
        info = {
            'key': key,
            'user_name': account.get('user_name', ''),
            'type': account.get('type', 'qr'),
            'configured': bool(account.get('user_name')),
        }
        if user_job and isinstance(user_job, UserJob):
            info.update({
                'is_ready': user_job.is_ready,
                'is_loaded': user_job.user_loaded,
                'display_name': user_job.get_name(),
                'last_heartbeat': timestamp_to_time(user_job.last_heartbeat) if user_job.last_heartbeat else None,
                'login_num': user_job.login_num,
                'has_qrcode': bool(user_job.current_qrcode_path and os.path.exists(user_job.current_qrcode_path)),
            })
        else:
            info.update({
                'is_ready': False,
                'is_loaded': False,
                'display_name': account.get('user_name', ''),
                'last_heartbeat': None,
                'login_num': 0,
                'has_qrcode': False,
            })
        result.append(info)
    return jsonify(result)


@manage.route('/manage/accounts', methods=['POST'])
@jwt_required()
def add_account():
    """
    添加 12306 账号
    Body: {"key": "0", "user_name": "xxx", "password": "xxx", "type": "qr"}
    """
    data = request.get_json(force=True)
    key = str(data.get('key', ''))
    user_name = data.get('user_name', '').strip()
    password = data.get('password', '')
    account_type = data.get('type', 'qr')

    if not key:
        # 自动生成 key
        existing_keys = [str(a.get('key')) for a in Config().USER_ACCOUNTS]
        idx = 0
        while str(idx) in existing_keys:
            idx += 1
        key = str(idx)

    if not user_name and account_type != 'qr':
        return jsonify({'msg': '用户名不能为空'}), 400

    # 检查 key 是否重复
    for account in Config().USER_ACCOUNTS:
        if str(account.get('key')) == key:
            return jsonify({'msg': '账号 key 已存在: {}'.format(key)}), 400

    old_accounts = list(Config().USER_ACCOUNTS)
    new_account = {
        'key': key,
        'user_name': user_name,
        'password': password,
        'type': account_type,
    }
    Config().USER_ACCOUNTS.append(new_account)

    # 触发运行时更新
    from py12306.user.user import User
    User().update_user_accounts(auto=True, old=old_accounts)

    # 持久化
    save_dynamic_config()

    return jsonify({'msg': '账号添加成功', 'key': key}), 201


@manage.route('/manage/accounts/<key>', methods=['DELETE'])
@jwt_required()
def delete_account(key):
    """删除 12306 账号"""
    key = str(key)
    old_accounts = list(Config().USER_ACCOUNTS)
    found = False
    new_accounts = []
    for account in Config().USER_ACCOUNTS:
        if str(account.get('key')) == key:
            found = True
        else:
            new_accounts.append(account)

    if not found:
        return jsonify({'msg': '账号不存在: {}'.format(key)}), 404

    Config().USER_ACCOUNTS = new_accounts

    # 触发运行时更新（会自动销毁已删除的用户线程）
    from py12306.user.user import User
    User().update_user_accounts(auto=True, old=old_accounts)

    # 持久化
    save_dynamic_config()

    return jsonify({'msg': '账号已删除', 'key': key})


@manage.route('/manage/accounts/<key>/relogin', methods=['POST'])
@jwt_required()
def relogin_account(key):
    """强制账号重新登录（清除 cookie，触发重新扫码/密码登录）"""
    key = str(key)
    from py12306.user.user import User
    user_job = User.get_user(key)
    if not user_job:
        return jsonify({'msg': '账号不存在或尚未初始化: {}'.format(key)}), 404

    user_job.force_relogin()
    return jsonify({'msg': '已触发重新登录，请查看二维码', 'key': key})


@manage.route('/manage/accounts/<key>/qrcode', methods=['GET'])
@jwt_required()
def get_qrcode(key):
    """获取登录二维码图片"""
    key = str(key)
    from py12306.user.user import User
    user_job = User.get_user(key)
    if not user_job:
        return jsonify({'msg': '账号不存在'}), 404

    qr_path = user_job.current_qrcode_path
    if not qr_path or not os.path.exists(qr_path):
        return jsonify({
            'msg': '二维码尚未生成，请稍候重试（账号可能正在登录中）',
            'available': False,
            'is_ready': user_job.is_ready,
        }), 404

    return send_file(qr_path, mimetype='image/png')


@manage.route('/manage/accounts/<key>/passengers', methods=['GET'])
@jwt_required()
def get_passengers(key):
    """获取账号的乘客列表"""
    key = str(key)
    from py12306.user.user import User
    user_job = User.get_user(key)
    if not user_job:
        return jsonify({'msg': '账号不存在'}), 404
    if not user_job.is_ready:
        return jsonify({'msg': '账号尚未登录成功'}), 400

    passengers = user_job.get_user_passengers()
    result = []
    for p in passengers:
        result.append({
            'code': p.get('code'),
            'name': p.get('passenger_name'),
            'id_no': p.get('passenger_id_no'),
            'type': p.get('passenger_type'),
            'mobile': p.get('mobile_no'),
        })
    return jsonify(result)


# ============================================================
# 抢票任务管理
# ============================================================

@manage.route('/manage/jobs', methods=['GET'])
@jwt_required()
def list_jobs():
    """获取所有抢票任务"""
    from py12306.query.query import Query
    from py12306.query.job import Job

    result = []
    for job_config in Config().QUERY_JOBS:
        job_name = job_config.get('job_name') or '{} -> {}'.format(
            job_config.get('stations', {}).get('left', '?'),
            job_config.get('stations', {}).get('arrive', '?')
        )
        info = {
            'name': job_name,
            'account_key': str(job_config.get('account_key', '')),
            'left_dates': job_config.get('left_dates', []),
            'stations': job_config.get('stations', {}),
            'members': job_config.get('members', []),
            'seats': job_config.get('seats', []),
            'train_numbers': job_config.get('train_numbers', []),
            'except_train_numbers': job_config.get('except_train_numbers', []),
            'allow_less_member': bool(job_config.get('allow_less_member', 0)),
            'period': job_config.get('period', {'from': '00:00', 'to': '24:00'}),
            'active': False,
        }
        # 检查是否在运行中
        for active_job in Query().jobs:
            if isinstance(active_job, Job) and active_job.job_name == job_name:
                info['active'] = True
                info['alive'] = active_job.is_alive
                break
        result.append(info)
    return jsonify(result)


@manage.route('/manage/jobs', methods=['POST'])
@jwt_required()
def add_job():
    """
    添加抢票任务
    Body: {
        "account_key": "0",
        "left_dates": ["2026-10-01"],
        "stations": {"left": "北京", "arrive": "深圳"},
        "members": ["张三"],
        "seats": ["硬卧", "硬座"],
        "train_numbers": [],
        "except_train_numbers": [],
        "allow_less_member": false,
        "period": {"from": "00:00", "to": "24:00"}
    }
    """
    data = request.get_json(force=True)

    account_key = str(data.get('account_key', '0'))
    left_dates = data.get('left_dates', [])
    stations = data.get('stations', {})
    members = data.get('members', [])
    seats = data.get('seats', [])
    train_numbers = data.get('train_numbers', [])
    except_train_numbers = data.get('except_train_numbers', [])
    allow_less_member = 1 if data.get('allow_less_member') else 0
    period = data.get('period', {'from': '00:00', 'to': '24:00'})
    job_name = data.get('job_name', '')

    # 校验
    if not left_dates:
        return jsonify({'msg': '出发日期不能为空'}), 400
    if not stations or not stations.get('left') or not stations.get('arrive'):
        return jsonify({'msg': '出发站和到达站不能为空'}), 400
    if not members:
        return jsonify({'msg': '乘客不能为空'}), 400

    # 校验车站是否存在
    left_code = Station.get_station_key_by_name(stations['left'])
    arrive_code = Station.get_station_key_by_name(stations['arrive'])
    if not left_code:
        return jsonify({'msg': '出发站不存在: {}'.format(stations['left'])}), 400
    if not arrive_code:
        return jsonify({'msg': '到达站不存在: {}'.format(stations['arrive'])}), 400

    # 生成任务名称
    if not job_name:
        job_name = '{} -> {}'.format(stations['left'], stations['arrive'])

    # 检查重名
    for job in Config().QUERY_JOBS:
        existing_name = job.get('job_name') or '{} -> {}'.format(
            job.get('stations', {}).get('left', '?'),
            job.get('stations', {}).get('arrive', '?')
        )
        if existing_name == job_name:
            return jsonify({'msg': '任务名称已存在: {}'.format(job_name)}), 400

    new_job = {
        'job_name': job_name,
        'account_key': account_key,
        'left_dates': left_dates,
        'stations': stations,
        'members': members,
        'allow_less_member': allow_less_member,
        'seats': seats,
        'train_numbers': train_numbers,
        'except_train_numbers': except_train_numbers,
        'period': period,
    }

    old_jobs = list(Config().QUERY_JOBS)
    Config().QUERY_JOBS.append(new_job)

    # 触发运行时更新
    from py12306.query.query import Query
    Query().update_query_jobs(auto=True)

    # 持久化
    save_dynamic_config()

    return jsonify({'msg': '任务添加成功', 'name': job_name}), 201


@manage.route('/manage/jobs/<name>', methods=['DELETE'])
@jwt_required()
def delete_job(name):
    """删除抢票任务"""
    old_jobs = list(Config().QUERY_JOBS)
    found = False
    new_jobs = []
    for job in Config().QUERY_JOBS:
        job_name = job.get('job_name') or '{} -> {}'.format(
            job.get('stations', {}).get('left', '?'),
            job.get('stations', {}).get('arrive', '?')
        )
        if job_name == name:
            found = True
        else:
            new_jobs.append(job)

    if not found:
        return jsonify({'msg': '任务不存在: {}'.format(name)}), 404

    Config().QUERY_JOBS = new_jobs

    # 触发运行时更新（会自动销毁已删除的任务线程）
    from py12306.query.query import Query
    Query().update_query_jobs(auto=True)

    # 持久化
    save_dynamic_config()

    return jsonify({'msg': '任务已删除', 'name': name})


# ============================================================
# 车站搜索（自动补全）
# ============================================================

@manage.route('/manage/stations', methods=['GET'])
@jwt_required()
def search_stations():
    """
    搜索车站
    ?q=关键词  返回匹配的车站列表
    """
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])

    results = []
    try:
        station_obj = Station()
        for s in station_obj.stations:
            name = s.get('name', '')
            code = s.get('key', '')
            pinyin = s.get('pinyin', '')
            if q in name or q.lower() in code.lower() or q.lower() in pinyin.lower():
                results.append({'name': name, 'code': code, 'pinyin': pinyin})
                if len(results) >= 20:
                    break
    except Exception:
        pass

    return jsonify(results)


# ============================================================
# 系统信息
# ============================================================

@manage.route('/manage/info', methods=['GET'])
@jwt_required()
def system_info():
    """获取系统运行信息"""
    from py12306.user.user import User
    from py12306.query.query import Query
    from py12306.log.query_log import QueryLog

    info = {
        'web_enabled': bool(Config().WEB_ENABLE),
        'web_port': Config().WEB_PORT,
        'cluster_enabled': bool(Config().is_cluster_enabled()),
        'cdn_enabled': bool(Config().is_cdn_enabled()),
        'account_count': len(Config().USER_ACCOUNTS),
        'job_count': len(Config().QUERY_JOBS),
        'active_users': len([u for u in User().users if u.is_ready]),
        'active_jobs': len([j for j in Query().jobs if j.is_alive]),
        'query_count': QueryLog().data.get('query_count', 0),
        'log_enabled': bool(Config().OUT_PUT_LOG_TO_FILE_ENABLED),
        'log_path': Config().OUT_PUT_LOG_TO_FILE_PATH,
    }
    return jsonify(info)
