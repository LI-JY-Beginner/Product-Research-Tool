"""kimi-webbridge 客户端封装（复用成熟方案，自研只做连接）。
通过本地 daemon(:10086) 驱动用户 Chrome，带罗盘/蝉妈妈登录态。
关键约束：浏览器单例串行，不并行操作。"""
import json, time, urllib.request

DAEMON = "http://127.0.0.1:10086"

def _post(payload, timeout=60):
    req = urllib.request.Request(
        DAEMON + "/command",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

class Bridge:
    def __init__(self, session):
        self.session = session

    def status(self):
        with urllib.request.urlopen(DAEMON + "/status", timeout=8) as r:
            return json.loads(r.read().decode("utf-8"))

    def navigate(self, url, new_tab=False, group_title=None):
        args = {"url": url, "newTab": new_tab}
        if group_title:
            args["group_title"] = group_title
        return _post({"action": "navigate", "args": args, "session": self.session})

    def evaluate(self, code, timeout=60):
        return _post({"action": "evaluate", "args": {"code": code}, "session": self.session}, timeout)

    def fetch_json(self, url, extra_headers=None):
        """在页面上下文里 fetch 一个同源 JSON 接口（带登录 cookie）。
        罗盘 msToken/a_bogus 每次变，必须走这条路，不能外部拼 URL。"""
        headers = {"x-e2e-platform": "compass", "agw-js-conv": "str"}
        if extra_headers:
            headers.update(extra_headers)
        js = (
            "(async()=>{const r=await fetch(%s,{credentials:'include',headers:%s});"
            "const t=await r.text();try{return JSON.parse(t)}catch(e){return {__raw:t.slice(0,2000)}}})()"
            % (json.dumps(url), json.dumps(headers))
        )
        res = self.evaluate(js)
        return res.get("data", {}).get("value", {})

    def wait(self, sec):
        time.sleep(sec)
