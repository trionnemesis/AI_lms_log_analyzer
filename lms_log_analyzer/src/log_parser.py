import re

try:
    from grok import GrokPattern
except Exception:  # pragma: no cover - optional dependency
    GrokPattern = None

APACHE_GROK = None
if GrokPattern is not None:
    try:  # pragma: no cover - compile once at import
        APACHE_GROK = GrokPattern("%{HTTPD_COMBINEDLOG}(?: %{GREEDYDATA:extras})?")
    except Exception:  # fallback silently if pattern unavailable
        APACHE_GROK = None


def parse_line(line: str) -> dict:
    """Parse a log line using Grok when available."""
    if APACHE_GROK is not None:
        m = APACHE_GROK.match(line)
        if m:
            data = m.groupdict()
            extras = data.get("extras", "") or ""
            rt = re.search(r"resp_time:(\d+(?:\.\d+)?)", extras)
            if rt:
                data["resp_time"] = rt.group(1)
            return data
    return {}

def parse_status(line: str) -> int:
    """Extract HTTP status code from a log line."""
    data = parse_line(line)
    if data and data.get("response"):
        try:
            return int(data["response"])
        except ValueError:
            pass
    m = re.search(r"\"\S+\s+\S+\s+HTTP/\d\.\d\"\s+(\d{3})", line)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return 0

def response_time(text: str) -> float:
    """Return the response time value in seconds if present."""
    data = parse_line(text)
    if data and data.get("resp_time"):
        try:
            return float(data["resp_time"])
        except ValueError:
            pass
    m = re.search(r"resp_time:(\d+(?:\.\d+)?)", text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return 0.0

def fast_score(line: str) -> float:
    """A very rough heuristic scoring suspicious log lines."""
    score = 0.0
    lower = line.lower()
    if '/etc/passwd' in lower:
        score += 0.5
    if 'nmap' in lower:
        score += 0.3
    status = parse_status(line)
    if status >= 400:
        score += 0.1
    return min(score, 1.0)
