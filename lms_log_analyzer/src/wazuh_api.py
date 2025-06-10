"""Wazuh ``logtest`` API 的簡易封裝，僅供測試環境使用。"""

from typing import Any

import requests

from .. import config
from .utils import logger


def logtest(line: str) -> bool:
    """檢查單行日誌是否會觸發 Wazuh 告警。

    參數
    ----
    line:
        單一原始日誌行。

    回傳
    ----
    bool
        若 Wazuh 產生告警則回傳 ``True``。
    """
    url = f"{config.WAZUH_API_URL}/logtest"
    try:
        resp = requests.post(
            url,
            auth=(config.WAZUH_API_USER, config.WAZUH_API_PASSWORD),
            json={"event": line},
            timeout=5,
        )
        resp.raise_for_status()
        data: Any = resp.json()
        # Common fields: 'total_alerts' or 'hits'. Any non-zero indicates match
        total = (
            data.get("total_alerts")
            or data.get("hits")
            or (len(data.get("data", [])) if isinstance(data.get("data"), list) else 0)
        )
        return bool(total)
    except Exception as exc:  # pragma: no cover - network errors
        logger.error("Wazuh logtest failed: %s", exc)
    return False
