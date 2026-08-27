# -*- coding: utf-8 -*-
"""
诊断 12306 余票接口字段索引
- 不动项目代码
- 跑一次就能看到 ticket_info 各位置的含义
"""
import re
import sys
import requests

URL_INIT = 'https://kyfw.12306.cn/otn/leftTicket/init'
URL_QUERY = (
    'https://kyfw.12306.cn/otn/leftTicket/queryG?'
    'leftTicketDTO.train_date={date}&'
    'leftTicketDTO.from_station={from_code}&'
    'leftTicketDTO.to_station={to_code}&'
    'purpose_codes=ADULT'
)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://kyfw.12306.cn/otn/leftTicket/init',
}

# 从 stations.txt 找车站代码
def find_station_code(name):
    with open('data/stations.txt', encoding='utf-8') as f:
        for line in f.read().lstrip('@').split('@'):
            parts = line.split('|')
            if len(parts) > 3 and parts[1] == name:
                return parts[2]
    return None

def main():
    # 1. 先访问 init 页拿动态 CLeftTicketUrl
    s = requests.Session()
    s.headers.update(HEADERS)
    init_resp = s.get(URL_INIT, timeout=10)
    m = re.search(r"var CLeftTicketUrl\s*=\s*'([^']+)'", init_resp.text)
    api_type = m.group(1) if m else 'leftTicket/queryG'
    print(f'[+] 当前查询接口类型: {api_type}')

    # 2. 构造查询 URL
    from_code = find_station_code('广州南')
    to_code = find_station_code('衡阳东')
    print(f'[+] 广州南={from_code}  衡阳东={to_code}')
    url = URL_QUERY.format(date='2026-08-30', from_code=from_code, to_code=to_code)
    print(f'[+] 请求 URL: {url}\n')

    # 3. 请求余票
    resp = s.get(url, timeout=10)
    print(f'[+] HTTP {resp.status_code}, Content-Type={resp.headers.get("Content-Type")}')
    try:
        data = resp.json()
    except Exception as e:
        print(f'[!] 解析失败: {e}')
        print(resp.text[:500])
        return 1
    results = (data.get('data') or {}).get('result') or []
    print(f'[+] 返回 {len(results)} 条车次\n')

    if not results:
        print('[!] 无车次数据')
        return 1

    # 4. 打印字段索引对照表 (找 G6030)
    target = None
    for r in results:
        parts = r.split('|')
        if len(parts) > 3 and parts[3] == 'G6030':
            target = parts
            break
    if not target:
        target = results[0].split('|')
        print('[!] 未找到 G6030, 取第一条车次为例\n')

    print('=' * 70)
    print('字段索引对照表 (对照 py12306/query/job.py 第 60-69 行)')
    print('=' * 70)
    labels = {
        0:  'secretStr',
        1:  'order_text(下单按钮文字)',
        2:  'train_no(车次内部编号)',
        3:  'station_train_code(显示车次 G6030)',
        4:  'start_station(始发站代码)',
        5:  'end_station(终点站代码)',
        6:  'from_station(用户查询出发站代码)',
        7:  'to_station(用户查询到达站代码)',
        8:  'left_time(出发时间 HH:MM)',
        9:  'arrive_time(到达时间 HH:MM)',
        10: 'duration(历时)',
        11: 'can_buy(能否购买 Y/N)',
        12: 'yp_info(座位类型明细)',
        13: 'left_date(出发日期)',
    }
    for i in range(min(len(target), 37)):
        label = labels.get(i, f'index_{i}')
        val = target[i] if target[i] else '<空>'
        print(f'  [{i:>2}] {label:<45} = {val}')

    # 5. 关键诊断:对比 4 和 6
    print()
    print('=' * 70)
    print('关键诊断')
    print('=' * 70)
    print(f'  [4] start_station(始发站代码)     = {target[4] if len(target)>4 else "<无>"}')
    print(f'  [6] from_station(用户出发站代码)  = {target[6] if len(target)>6 else "<无>"}')
    print(f'  [5] end_station(终点站代码)       = {target[5] if len(target)>5 else "<无>"}')
    print(f'  [7] to_station(用户到达站代码)    = {target[7] if len(target)>7 else "<无>"}')

    # 反查车站名
    with open('data/stations.txt', encoding='utf-8') as f:
        kvs = {}
        for line in f.read().lstrip('@').split('@'):
            p = line.split('|')
            if len(p) > 3:
                kvs[p[2]] = p[1]

    for idx in (4, 5, 6, 7):
        if idx < len(target):
            code = target[idx]
            name = kvs.get(code, '<未知>')
            print(f'  index[{idx}] = {code}  ->  {name}')

    # 6. 列出所有经过 广州南→衡阳东 的车次,看哪些是真正从广州南出发
    print()
    print('=' * 70)
    print('所有车次的"上车站" (即 index[6] 反查)')
    print('=' * 70)
    print(f'  查询条件: {kvs.get(from_code)} -> {kvs.get(to_code)}')
    print()
    for r in results:
        p = r.split('|')
        if len(p) < 8: continue
        train = p[3]
        actual_from = kvs.get(p[6], p[6])
        actual_to = kvs.get(p[7], p[7])
        start = kvs.get(p[4], p[4]) if len(p)>4 else '?'
        end = kvs.get(p[5], p[5]) if len(p)>5 else '?'
        left_time = p[8] if len(p)>8 else '?'
        flag = '⚠️ ' if (p[6] != from_code or p[7] != to_code) else '  '
        print(f'  {flag}{train:<8} {start} -> {end}  | 实际区间: {actual_from} {left_time} -> {actual_to}')
    return 0

if __name__ == '__main__':
    sys.exit(main())