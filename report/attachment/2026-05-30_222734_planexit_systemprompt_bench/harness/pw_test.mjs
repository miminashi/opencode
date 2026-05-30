// ブラウザ実機ユーザーテスト + スクリーンショット。
// 使い方: bun pw_test.mjs <mode: search|page|base> <port> <outdir>
import { chromium } from "playwright";
import fs from "fs";

const [mode, portArg, outdir] = process.argv.slice(2);
const port = portArg || "3010";
const base = `http://localhost:${port}/`;
fs.mkdirSync(outdir, { recursive: true });
const result = { mode, base, steps: [], notes: [] };

function log(o) { result.steps.push(o); }

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 1400 } });
page.setDefaultTimeout(15000);

async function shot(name) {
  const p = `${outdir}/${name}.png`;
  await page.screenshot({ path: p, fullPage: true });
  return p;
}
async function countArticles() {
  return await page.locator("article.article").count();
}

try {
  await page.goto(base, { waitUntil: "networkidle" });
  await shot("01_index");
  const total = await countArticles();
  log({ step: "index", articles: total, screenshot: "01_index.png" });

  if (mode === "search") {
    // 検索入力を防御的に探す
    const selectors = ['input[name="q"]', 'input[type="search"]',
      'form input[type="text"]', 'input[type="text"]', "form input"];
    let input = null, used = null;
    for (const s of selectors) {
      const loc = page.locator(s).first();
      if (await loc.count() > 0) { input = loc; used = s; break; }
    }
    if (!input) {
      result.notes.push("検索入力が見つからない");
      result.searchInputFound = false;
    } else {
      result.searchInputFound = true;
      result.searchSelector = used;
      await input.fill("Ruby");
      await shot("02_search_typed");
      // submit: ボタン優先、なければ Enter
      const submit = page.locator('input[type="submit"], button[type="submit"]').first();
      if (await submit.count() > 0) { await submit.click(); }
      else { await input.press("Enter"); }
      await page.waitForLoadState("networkidle").catch(() => {});
      await page.waitForTimeout(800);
      await shot("03_search_results");
      const hit = await countArticles();
      log({ step: "search_ruby", articles: hit, screenshot: "03_search_results.png" });
      result.searchRubyCount = hit;
      // タイトルに Ruby を含むか確認
      const titles = await page.locator("article.article .article__title").allInnerTexts().catch(() => []);
      result.sampleTitles = titles.slice(0, 25);
      result.allTitlesContainRuby = titles.length > 0 && titles.every(t => /ruby/i.test(t));
    }
  }

  if (mode === "page") {
    const firstPageCount = await countArticles();
    result.firstPageCount = firstPageCount;
    log({ step: "page1", articles: firstPageCount });
    // ページネーション UI を探す（kaminari は nav.pagination、汎用に ?page= リンク）
    const navCount = await page.locator("nav.pagination, .pagination").count();
    result.paginationNavFound = navCount > 0;
    const pageLinks = page.locator('a[href*="page="]');
    const linkCount = await pageLinks.count();
    result.pageLinkCount = linkCount;
    await shot("02_page1_bottom");
    if (linkCount > 0) {
      // 「2」へのリンク、なければ次へ
      let target = page.locator('a[href*="page=2"]').first();
      if (await target.count() === 0) target = pageLinks.last();
      await target.click();
      await page.waitForLoadState("networkidle").catch(() => {});
      await page.waitForTimeout(800);
      await shot("03_page2");
      const p2 = await countArticles();
      result.secondPageCount = p2;
      log({ step: "page2", articles: p2, screenshot: "03_page2.png" });
    } else {
      result.notes.push("ページネーションリンクが見つからない");
    }
  }

  result.ok = true;
} catch (e) {
  result.ok = false;
  result.error = String(e);
  try { await shot("99_error"); } catch {}
} finally {
  await browser.close();
  fs.writeFileSync(`${outdir}/result.json`, JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
}
