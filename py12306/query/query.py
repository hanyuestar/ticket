from base64 import b64decode
import threading
import time

from py12306.config import Config
from py12306.cluster.cluster import Cluster
from py12306.app import app_available_check
from py12306.helpers.func import *
from py12306.helpers.request import Request
from py12306.log.query_log import QueryLog
from py12306.query.job import Job
from py12306.helpers.api import API_QUERY_INIT_PAGE, API_GET_BROWSER_DEVICE_ID
from py12306.helpers.device_id import fetch_device_id_by_browser, fetch_browser_session, is_browser_fingerprint_available


@singleton
class Query:
    """
    余票查询

    """
    jobs = []
    query_jobs = []
    session = {}

    # 查询间隔
    interval = {}
    cluster = None

    is_in_thread = False
    retry_time = 3
    is_ready = False
    api_type = None  # Query api url, Current know value  leftTicket/queryX | leftTicket/queryZ

    # 302 风控自愈：两次刷新之间的最小间隔（秒），防止多任务/多线程并发刷新风暴
    REJECT_REFRESH_COOLDOWN = 60

    def __init__(self):
        self.session = Request()
        self.last_reject_refresh_at = 0
        self._reject_refresh_lock = threading.Lock()
        self._browser_warmed = False
        self.warm_up_session_by_browser()
        self.request_device_id()
        self.cluster = Cluster()
        self.update_query_interval()
        self.update_query_jobs()
        self.get_query_api_type()

    def update_query_interval(self, auto=False):
        self.interval = init_interval_by_number(Config().QUERY_INTERVAL)
        if auto:
            jobs_do(self.jobs, 'update_interval')

    def update_query_jobs(self, auto=False):
        self.query_jobs = Config().QUERY_JOBS
        if auto:
            QueryLog.add_quick_log(QueryLog.MESSAGE_JOBS_DID_CHANGED).flush()
            self.refresh_jobs()
            if not Config().is_slave():
                jobs_do(self.jobs, 'check_passengers')

    @classmethod
    def run(cls):
        self = cls()
        app_available_check()
        self.start()
        pass

    @classmethod
    def check_before_run(cls):
        self = cls()
        self.init_jobs()
        self.is_ready = True

    def start(self):
        # return # DEBUG
        QueryLog.init_data()
        stay_second(3)
        # 多线程
        while True:
            if Config().QUERY_JOB_THREAD_ENABLED:  # 多线程
                if not self.is_in_thread:
                    self.is_in_thread = True
                    create_thread_and_run(jobs=self.jobs, callback_name='run', wait=Const.IS_TEST)
                if Const.IS_TEST: return
                stay_second(self.retry_time)
            else:
                if not self.jobs: break
                self.is_in_thread = False
                jobs_do(self.jobs, 'run')
                if Const.IS_TEST: return

        # while True:
        #     app_available_check()
        #     if Config().QUERY_JOB_THREAD_ENABLED:  # 多线程
        #         create_thread_and_run(jobs=self.jobs, callback_name='run')
        #     else:
        #         for job in self.jobs: job.run()
        #     if Const.IS_TEST: return
        # self.refresh_jobs()  # 刷新任务

    def refresh_jobs(self):
        """
        更新任务
        :return:
        """
        allow_jobs = []
        for job in self.query_jobs:
            id = md5(job)
            job_ins = objects_find_object_by_key_value(self.jobs, 'id', id)  # [1 ,2]
            if not job_ins:
                job_ins = self.init_job(job)
                if Config().QUERY_JOB_THREAD_ENABLED:  # 多线程重新添加
                    create_thread_and_run(jobs=job_ins, callback_name='run', wait=Const.IS_TEST)
            allow_jobs.append(job_ins)

        for job in self.jobs:  # 退出已删除 Job
            if job not in allow_jobs: job.destroy()

        QueryLog.print_init_jobs(jobs=self.jobs)

    def init_jobs(self):
        for job in self.query_jobs:
            self.init_job(job)
        QueryLog.print_init_jobs(jobs=self.jobs)

    def init_job(self, job):
        job = Job(info=job, query=self)
        self.jobs.append(job)
        return job

    def warm_up_session_by_browser(self):
        """
        无头浏览器会话预热（应对 12306 会话风控的核心手段）。

        2026-09 实测：查询接口 302 的根因不是缺少 RAIL_DEVICEID，而是
        requests 会话缺少由浏览器 JS 建立的反爬 Cookie（_uab_collina /
        JSESSIONID / BIGipServerotn / SF_cookie_2 等）。用无头浏览器打开
        一次查询页，把整套 Cookie + UA 导入本会话后，查询即可恢复 200。

        :return: True 表示预热成功
        """
        self._browser_warmed = True  # 无论成败均标记，避免后续重复开浏览器
        if not is_browser_fingerprint_available():
            QueryLog.add_quick_log('浏览器方案不可用(pyppeteer 未安装或已熔断)，跳过会话预热').flush()
            return False
        QueryLog.add_quick_log('正在通过无头浏览器预热会话(约需 10~30 秒)...').flush()
        result = fetch_browser_session()
        if not result:
            QueryLog.add_quick_log('无头浏览器会话预热失败，将按原流程继续').flush()
            return False
        self.session.cookies.update(result['cookies'])
        self.session.headers.update({'User-Agent': result['user_agent']})
        QueryLog.add_quick_log(
            '会话预热成功：已导入 {} 个浏览器 Cookie(含 {})'.format(
                len(result['cookies']), '/'.join(sorted(result['cookies'])[:4]))
        ).flush()
        return True

    def request_device_id(self, force_renew = False):
        """
        获取加密后的浏览器特征 ID (RAIL_DEVICEID / RAIL_EXPIRATION)

        获取优先级：
            1. env.py 手动配置 (CACHE_RAIL_ID_ENABLED=1 + RAIL_EXPIRATION/RAIL_DEVICEID)
            2. 无头浏览器方案 (helpers/device_id.py，由 12306 自家指纹 JS 种 Cookie，抗算法改版)
            3. 旧版 logdevice 流程（保底；12306 已加固，大概率 302 失败）

        注：2026-09 实测余票查询并不强校验 RAIL_DEVICEID（会话预热即可通过），
        本方法保留用于登录/下单等仍校验指纹的场景。
        :return:
        """
        expire_time =  self.session.cookies.get('RAIL_EXPIRATION')
        if not force_renew and expire_time and int(expire_time) - time_int_ms() > 0:
            return
        if Config().is_cache_rail_id_enabled():
            # 手动配置优先：不依赖任何可能被拦截的网络流程
            self.session.cookies.update({
                'RAIL_EXPIRATION': Config().RAIL_EXPIRATION,
                'RAIL_DEVICEID': Config().RAIL_DEVICEID,
            })
            QueryLog.add_quick_log('设备指纹已从配置载入 (CACHE_RAIL_ID_ENABLED=1)').flush()
            return
        if is_browser_fingerprint_available() and not self._browser_warmed:
            # 会话预热已由 warm_up_session_by_browser 完成时不再单独开浏览器
            QueryLog.add_quick_log('正在通过无头浏览器获取设备指纹(约需 10~40 秒)...').flush()
            result = fetch_device_id_by_browser()
            if result:
                self.session.cookies.update(result)
                QueryLog.add_quick_log('设备指纹获取成功(无头浏览器)').flush()
                return
            QueryLog.add_quick_log('无头浏览器获取设备指纹失败，回退旧版 logdevice 流程...').flush()
        if 'pjialin' not in API_GET_BROWSER_DEVICE_ID:
            return self.request_device_id2()
        response = self.session.get(API_GET_BROWSER_DEVICE_ID)
        if response.status_code == 200:
            try:
                result = json.loads(response.text)
                response = self.session.get(b64decode(result['id']).decode())
                if response.text.find('callbackFunction') >= 0:
                    result = response.text[18:-2]
                result = json.loads(result)
                if not Config().is_cache_rail_id_enabled():
                    self.session.cookies.update({
                        'RAIL_EXPIRATION': result.get('exp'),
                        'RAIL_DEVICEID': result.get('dfp'),
                    })
                else:
                    self.session.cookies.update({
                        'RAIL_EXPIRATION': Config().RAIL_EXPIRATION,
                        'RAIL_DEVICEID': Config().RAIL_DEVICEID,
                    })
            except Exception:
                return self.request_device_id()
        else:
            return self.request_device_id()

    def request_device_id2(self):
        headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Safari/537.36"
        }
        self.session.headers.update(headers)
        max_retry = 3
        for attempt in range(max_retry):
            try:
                response = self.session.get(API_GET_BROWSER_DEVICE_ID)
            except Exception:
                sleep(3)
                continue
            if response.status_code == 200:
                try:
                    if response.text.find('callbackFunction') >= 0:
                        result = response.text[18:-2]
                        result = json.loads(result)
                        if not Config().is_cache_rail_id_enabled():
                           self.session.cookies.update({
                               'RAIL_EXPIRATION': result.get('exp'),
                               'RAIL_DEVICEID': result.get('dfp'),
                           })
                        else:
                           self.session.cookies.update({
                               'RAIL_EXPIRATION': Config().RAIL_EXPIRATION,
                               'RAIL_DEVICEID': Config().RAIL_DEVICEID,
                           })
                        return
                except Exception:
                    pass
                QueryLog.add_quick_log(
                    '设备指纹接口(logdevice)未返回有效签名，12306 可能已拦截旧版签名流程'
                ).flush()
            else:
                QueryLog.add_quick_log(
                    '设备指纹接口(logdevice)返回 {}，可能已被 12306 拦截'.format(response.status_code)
                ).flush()
            sleep(3)
        QueryLog.add_quick_log(
            '旧版设备指纹流程获取失败；请在浏览器中打开 12306 查询页，'
            '按 F12 取 RAIL_DEVICEID / RAIL_EXPIRATION 填入 env.py 并设 CACHE_RAIL_ID_ENABLED=1'
        ).flush()

    def handle_query_rejected(self):
        """
        查询被 12306 风控拦截(302 -> error.html)时的自愈入口。

        刷新设备指纹与查询地址（api_type），带冷却时间与线程锁，
        防止多任务/多线程并发刷新风暴。
        """
        acquired = self._reject_refresh_lock.acquire(timeout=5)
        if not acquired:
            return  # 其他线程正在刷新
        try:
            now = time.time()
            if now - self.last_reject_refresh_at < self.REJECT_REFRESH_COOLDOWN:
                return
            self.last_reject_refresh_at = now
        finally:
            self._reject_refresh_lock.release()

        QueryLog.add_quick_log('开始自愈：预热浏览器会话 + 刷新设备指纹与查询地址...').flush()
        self.warm_up_session_by_browser()
        self.api_type = None
        self.request_device_id(force_renew=True)
        self.get_query_api_type()
        QueryLog.add_quick_log('风控自愈完成，下一轮查询将使用新会话').flush()

    @classmethod
    def wait_for_ready(cls):
        self = cls()
        if self.is_ready: return self
        stay_second(self.retry_time)
        return self.wait_for_ready()

    @classmethod
    def job_by_name(cls, name) -> Job:
        self = cls()
        for job in self.jobs:
            if job.job_name == name: return job
        return None

    @classmethod
    def job_by_name(cls, name) -> Job:
        self = cls()
        return objects_find_object_by_key_value(self.jobs, 'job_name', name)

    @classmethod
    def job_by_account_key(cls, account_key) -> Job:
        self = cls()
        return objects_find_object_by_key_value(self.jobs, 'account_key', account_key)

    @classmethod
    def get_query_api_type(cls):
        import re
        self = cls()
        if self.api_type:
            return self.api_type
        for attempt in range(10):
            response = self.session.get(API_QUERY_INIT_PAGE)
            if response.status_code == 200:
                res = re.search(r'var CLeftTicketUrl = \'(.*)\';', response.text)
                try:
                    self.api_type = res.group(1)
                except Exception:
                    pass
            if self.api_type:
                self.request_device_id(True)
                return self.api_type
            QueryLog.add_quick_log('查询地址获取失败, 正在重新获取...').flush()
            sleep(get_interval_num(self.interval) if self.interval else 3)
        self.api_type = 'leftTicket/queryG'  # fallback
        self.request_device_id(True)
        return self.api_type

# def get_jobs_from_cluster(self):
#     jobs = self.cluster.session.get_dict(Cluster.KEY_JOBS)
#     return jobs
#
# def update_jobs_of_cluster(self):
#     if config.CLUSTER_ENABLED and config.NODE_IS_MASTER:
#         return self.cluster.session.set_dict(Cluster.KEY_JOBS, self.query_jobs)
#
# def refresh_jobs(self):
#     if not config.CLUSTER_ENABLED: return
#     jobs = self.get_jobs_from_cluster()
#     if jobs != self.query_jobs:
#         self.jobs = []
#         self.query_jobs = jobs
#         QueryLog.add_quick_log(QueryLog.MESSAGE_JOBS_DID_CHANGED).flush()
#         self.init_jobs()
