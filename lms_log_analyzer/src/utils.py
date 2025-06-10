"""一些簡化工具供測試環境使用。"""

from collections import OrderedDict

class LRUCache:
    """單元測試用的簡易 LRU 快取實作。"""

    def __init__(self, capacity: int):
        self.capacity = capacity
        self._data = OrderedDict()

    def get(self, key):
        if key not in self._data:
            return None
        value = self._data.pop(key)
        self._data[key] = value
        return value

    def put(self, key, value):
        if key in self._data:
            self._data.pop(key)
        elif len(self._data) >= self.capacity:
            self._data.popitem(last=False)
        self._data[key] = value

# 供其他模組使用的簡易存根
STATE = {}

def save_state(state):
    return state

# 最小化的 logger 取代方案
import logging
logger = logging.getLogger("lms_log_analyzer")

# 其他輔助函式

def tail_since(path):
    """讀取檔案內容並逐行回傳。"""
    with open(path, "r", encoding="utf-8") as f:
        return [line.rstrip("\n") for line in f]

def http_request_with_retry(method, url, **kwargs):
    """以 requests 重新嘗試 HTTP 呼叫的簡化函式。"""
    import requests
    func = getattr(requests, method)
    return func(url, **kwargs)
