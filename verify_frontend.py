"""前端验证脚本：playwright 打开 web/index.html，验证渲染与联动，截图 4 张。"""
import sys, os, time, threading, http.server, functools
from playwright.sync_api import sync_playwright

ROOT = "/Users/mac/WorkBuddy/选品工作台/美妆数据看板"
URL = "http://localhost:8899/index.html"
OUT = os.path.join(ROOT, "需求挖掘", "_素材")


def serve():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=os.path.join(ROOT, "web"))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 8899), handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd

def main():
    httpd = serve()
    time.sleep(0.5)
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        pg = b.new_page(viewport={"width": 1440, "height": 960})
        errors = []
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(URL)
        pg.wait_for_timeout(1500)

        # 1. 增速看板
        r = pg.evaluate("""() => ({
            hero: document.getElementById('ggHeroName').textContent,
            groups: document.querySelectorAll('#ggGroups .panel').length,
            rows: document.querySelectorAll('#ggGroups tbody tr').length,
            imgs: document.querySelectorAll('#ggGroups img').length,
            echo: document.querySelector('.f-echo')?.textContent,
        })""")
        print("[growth]", r)
        pg.screenshot(path=os.path.join(OUT, "v2_growth.png"), full_page=False)

        # 2. 商品榜（切换 + 验证联动）
        pg.click('.nav-item[data-target="product-rank"]')
        pg.wait_for_timeout(600)
        r2 = pg.evaluate("""() => ({
            rows: document.querySelectorAll('#prBody tr').length,
            firstImg: document.querySelector('#prBody img')?.src?.slice(0,60),
            firstLink: document.querySelector('#prBody tr')?.getAttribute('onclick')?.slice(0,80),
        })""")
        print("[product]", r2)
        pg.screenshot(path=os.path.join(OUT, "v2_product.png"), full_page=False)

        # 联动测试：筛选只看「眼部护理」
        pg.evaluate("""() => {
            window.FilterState.categories = ['眼部护理'];
            window._filterSubs.forEach(f => f(window.FilterState));
        }""")
        pg.wait_for_timeout(400)
        eye_rows = pg.evaluate("document.querySelectorAll('#prBody tr').length")
        print("[product·筛选眼部护理后] rows:", eye_rows)

        # 3. 成分库（点击成分弹层）
        pg.evaluate("window.FilterState.categories=[]; window._filterSubs.forEach(f=>f(window.FilterState))")
        pg.click('.nav-item[data-target="ingredient-lib"]')
        pg.wait_for_timeout(600)
        lib_rows = pg.evaluate("document.querySelectorAll('#libGrowthBody tr').length")
        print("[ingredient-lib] rows:", lib_rows)
        if lib_rows:
            pg.click("#libGrowthBody tr:first-child")
            pg.wait_for_timeout(500)
            modal = pg.evaluate("""() => ({
                show: document.getElementById('ingModal').classList.contains('show'),
                title: document.getElementById('ingModalTitle').textContent,
                prodRows: document.querySelectorAll('#ingModalBody .ing-modal-list tbody tr').length,
            })""")
            print("[ingredient-modal]", modal)
            pg.screenshot(path=os.path.join(OUT, "v2_ingredient.png"), full_page=False)
            pg.click("#ingModal .modal-close")

        # 4. 策略台
        pg.click('.nav-item[data-target="strategy-cards"]')
        pg.wait_for_timeout(600)
        st = pg.evaluate("""() => ({
            heroes: document.querySelectorAll('.strat-hero').length,
            verdicts: [...document.querySelectorAll('.strat-hero .verdict')].map(e=>e.textContent.trim()),
            anaCards: document.querySelectorAll('.ana-card').length,
            llm: document.querySelector('.llm-body')?.textContent?.slice(0,60) || null,
        })""")
        print("[strategy]", st)
        pg.screenshot(path=os.path.join(OUT, "v2_strategy.png"), full_page=True)

        print("console errors:", errors[:5] if errors else "无")
        b.close()

if __name__ == "__main__":
    main()
