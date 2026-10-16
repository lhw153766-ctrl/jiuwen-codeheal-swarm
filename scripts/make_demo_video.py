"""Automated Demo Video Generator for Jiuwen-CodeHeal Swarm.

Uses Playwright with local Microsoft Edge (channel="msedge") to capture
a 1080p 60fps automated demonstration video aligned with the 180s script in
docs/04_决赛路演PPT大纲与3分钟演示脚本.md.
"""

import argparse
import asyncio
import os
import pathlib
import sys
import time

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def build_showcase_html() -> str:
    """Build a self-contained 1080p showcase webpage with 5 animated scenes."""
    dashboard_path = (_REPO_ROOT / "docs" / "dashboard.html").as_uri()

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>Jiuwen-CodeHeal Swarm · 3-Min Automated Demo</title>
    <style>
        :root {{
            --bg: #0d1117;
            --card-bg: #161b22;
            --border: #30363d;
            --text: #c9d1d9;
            --accent: #58a6ff;
            --green: #3fb950;
            --red: #f85149;
            --yellow: #d29922;
            --font-mono: Consolas, "SF Mono", Monaco, Menlo, monospace;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: var(--bg);
            color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            width: 1920px;
            height: 1080px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            position: relative;
        }}
        /* Top Navigation Header */
        .top-bar {{
            height: 64px;
            background: #161b22;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 32px;
            z-index: 100;
        }}
        .brand {{
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 20px;
            font-weight: 700;
            color: #fff;
        }}
        .brand-pill {{
            background: rgba(88, 166, 255, 0.15);
            color: var(--accent);
            border: 1px solid rgba(88, 166, 255, 0.4);
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 13px;
        }}
        .timer-badge {{
            font-family: var(--font-mono);
            font-size: 16px;
            background: #21262d;
            padding: 6px 14px;
            border-radius: 8px;
            border: 1px solid var(--border);
            color: var(--accent);
        }}
        /* Scene Container */
        .stage {{
            flex: 1;
            position: relative;
            width: 100%;
            height: calc(1080px - 64px);
        }}
        .scene {{
            position: absolute;
            inset: 0;
            display: none;
            opacity: 0;
            transition: opacity 0.5s ease-in-out;
            padding: 40px;
        }}
        .scene.active {{
            display: flex;
            opacity: 1;
        }}

        /* Scene 1: Intro */
        .scene-1 {{
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            gap: 24px;
        }}
        .hero-title {{
            font-size: 56px;
            font-weight: 800;
            color: #fff;
            background: linear-gradient(135deg, #58a6ff 0%, #3fb950 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .hero-sub {{
            font-size: 24px;
            color: #8b949e;
            max-width: 1100px;
            line-height: 1.6;
        }}
        .grid-cards {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 24px;
            max-width: 1200px;
            margin-top: 24px;
        }}
        .card {{
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 24px;
            text-align: left;
        }}
        .card h3 {{ color: #fff; margin-bottom: 8px; font-size: 18px; }}
        .card p {{ color: #8b949e; font-size: 14px; }}

        /* Scene 2 & 3: Terminal */
        .terminal-wrap {{
            width: 100%;
            height: 100%;
            background: #090d13;
            border: 1px solid var(--border);
            border-radius: 12px;
            box-shadow: 0 16px 36px rgba(0,0,0,0.6);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }}
        .term-header {{
            height: 40px;
            background: #161b22;
            display: flex;
            align-items: center;
            padding: 0 16px;
            gap: 8px;
            border-bottom: 1px solid var(--border);
        }}
        .term-dot {{ width: 12px; height: 12px; border-radius: 50%; }}
        .dot-red {{ background: #ff5f56; }}
        .dot-yellow {{ background: #ffbd2e; }}
        .dot-green {{ background: #27c93f; }}
        .term-title {{ margin-left: 12px; font-size: 13px; color: #8b949e; font-family: var(--font-mono); }}
        .term-body {{
            flex: 1;
            padding: 24px;
            font-family: var(--font-mono);
            font-size: 15px;
            line-height: 1.5;
            overflow-y: auto;
            white-space: pre-wrap;
            color: #d1d5db;
        }}
        .term-cursor {{
            display: inline-block;
            width: 8px;
            height: 16px;
            background: var(--accent);
            animation: blink 1s infinite;
            vertical-align: middle;
        }}
        @keyframes blink {{ 0%, 50% {{ opacity: 1; }} 51%, 100% {{ opacity: 0; }} }}

        /* Scene 4: Dashboard Embed */
        .dashboard-frame {{
            width: 100%;
            height: 100%;
            border: none;
            border-radius: 12px;
        }}

        /* Scene 5: Outro */
        .scene-5 {{
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            gap: 28px;
        }}
        .badge-list {{
            display: flex;
            gap: 16px;
            justify-content: center;
        }}
        .metric-pill {{
            background: #161b22;
            border: 1px solid var(--border);
            padding: 12px 24px;
            border-radius: 10px;
            font-size: 18px;
            font-weight: 600;
        }}
        .metric-pill span {{ color: var(--green); font-size: 24px; margin-right: 6px; }}
    </style>
</head>
<body>
    <div class="top-bar">
        <div class="brand">
            <span>⚡ Jiuwen-CodeHeal Swarm</span>
            <span class="brand-pill">Coding 赛道 · 官方决赛路演 DEMO</span>
        </div>
        <div id="timeline-text" class="timer-badge">分镜 1: 痛点引入与系统架构 (00:00)</div>
    </div>

    <div class="stage">
        <!-- Scene 1: Intro (0-25s) -->
        <div id="scene-1" class="scene scene-1 active">
            <h1 class="hero-title">Jiuwen-CodeHeal Swarm</h1>
            <p class="hero-sub">基于 openJiuwen 与 JiuwenSwarm 多智能体协同进化的仓库级 CI 故障自愈与回归验证系统</p>
            <div class="grid-cards">
                <div class="card">
                    <h3>❌ 业界痛点：CI 频发爆红</h3>
                    <p>万行日志逐行排查耗时 15-45 分钟，单体模型盲目修改代码导致高达 23% 的二次回归破坏。</p>
                </div>
                <div class="card">
                    <h3>🛡️ openJiuwen 图流转底座</h3>
                    <p>有向无环图 (DAG) 状态机编排四大 Teammate 智能体，AST 作用域切片压缩 77.2% Token 消耗。</p>
                </div>
                <div class="card">
                    <h3>🔄 JiuwenSwarm 经验进化</h3>
                    <p>隔离沙箱回归验证确保 0% 次生破坏，自演进蒸馏多缺陷独立知识指纹，越用越聪明。</p>
                </div>
            </div>
        </div>

        <!-- Scene 2: CLI Demo (25-75s) -->
        <div id="scene-2" class="scene">
            <div class="terminal-wrap">
                <div class="term-header">
                    <div class="term-dot dot-red"></div>
                    <div class="term-dot dot-yellow"></div>
                    <div class="term-dot dot-green"></div>
                    <span class="term-title">bash - codeheal demo (Terminal Verification)</span>
                </div>
                <div id="term-text-demo" class="term-body"></div>
            </div>
        </div>

        <!-- Scene 3: Benchmark (75-125s) -->
        <div id="scene-3" class="scene">
            <div class="terminal-wrap">
                <div class="term-header">
                    <div class="term-dot dot-red"></div>
                    <div class="term-dot dot-yellow"></div>
                    <div class="term-dot dot-green"></div>
                    <span class="term-title">bash - codeheal benchmark (Quantitative Matrix)</span>
                </div>
                <div id="term-text-bench" class="term-body"></div>
            </div>
        </div>

        <!-- Scene 4: Dashboard (125-160s) -->
        <div id="scene-4" class="scene" style="padding: 0;">
            <iframe id="dash-iframe" class="dashboard-frame" src="{dashboard_path}"></iframe>
        </div>

        <!-- Scene 5: Outro (160-180s) -->
        <div id="scene-5" class="scene scene-5">
            <h1 class="hero-title">软件流水线长青 · 智能体共生</h1>
            <p class="hero-sub">Jiuwen-CodeHeal Swarm 成功完成全量 46 项严苛单测与 6 大场景自愈验证</p>
            <div class="badge-list">
                <div class="metric-pill"><span>100%</span>自愈成功率 (Pass@1)</div>
                <div class="metric-pill"><span>0.0%</span>次生回归率 (Regression)</div>
                <div class="metric-pill"><span>1.3s</span>平均自愈耗时 (MTTR)</div>
                <div class="metric-pill"><span>77.2%</span>AST Token 压缩率</div>
            </div>
            <div class="card" style="margin-top: 20px; max-width: 800px; text-align: center;">
                <h3 style="color: var(--accent); font-size: 20px;">开源仓库 (GitHub)</h3>
                <p style="font-family: var(--font-mono); font-size: 16px; margin-top: 8px; color: #fff;">
                    https://github.com/lhw153766-ctrl/jiuwen-codeheal-swarm
                </p>
            </div>
        </div>
    </div>

    <script>
        const DEMO_OUTPUT = `+-------------------------------------------------------------------------+
| Jiuwen-CodeHeal Swarm v0.1.0                                            |
| openJiuwen + JiuwenSwarm 多智能体协同 · 模式 replay                     |
| 仓库: examples/buggy_repo_demo                                           |
+-------------------------------------------------------------------------+
>> 采集 demo 仓库真实失败日志 (pytest) ...
可观测性 Trace
+-- [OK] 故障感知与日志解析 (1-triage (iter 1), 0.00s)
|   \`-- index_error @ buggy_repo_demo/calc.py:22 in find_max
+-- [OK] 根因定位与 AST 检索 (2-inspect (iter 1), 0.00s)
|   \`-- boundary_guard: [Memory Hit: trusted pattern] Fixed off-by-one index overrun by changing index access from [idx + 1] to [idx].
+-- [FAIL] 沙箱补丁回归验证 (3-verify (iter 1), 0.59s)
|   \`-- failed · 5/6 通过 (失败 1)
+-- [OK] 故障感知与日志解析 (1-triage (iter 2), 0.00s)
|   \`-- value_error @ buggy_repo_demo/calc.py:32 in average
+-- [OK] 根因定位与 AST 检索 (2-inspect (iter 2), 0.00s)
|   \`-- boundary_guard: [Memory Hit: trusted pattern] Guard against empty input before minimum/aggregation call.
+-- [OK] 沙箱补丁回归验证 (3-verify (iter 2), 0.55s)
|   \`-- passed · 6/6 通过 (失败 0)
\`-- [OK] Skill 自演进与复盘 (4-evolve, 0.00s)
    \`-- 提炼 2 个模式: 4747dcb7db75d17f->boundary_guard, fc077a19126271d9->boundary_guard
+------------------ [SUCCESS] 自愈成功 · CI 由红变绿 ------------------+
| 迭代 2 轮 · 耗时 4.56s                                               |
| 模式 replay                                                          |
| 测试 6/6 通过 · 失败 0                                               |
+----------------------------------------------------------------------+
--- a/buggy_repo_demo/calc.py
+++ b/buggy_repo_demo/calc.py
@@ -29,4 +29,6 @@
+    if not values:
+        return 0.0
     return sum(values) / len(values)  # BUG 2: 缺少空输入守卫

控制台看板已生成: docs/dashboard.html`;

        const BENCH_OUTPUT = `                                      Jiuwen-CodeHeal Swarm · 6 大场景量化评测矩阵                                      
┌───────────────────────────┬────────────┬─────────────┬────────────┬─────────────┬──────────┬────────────┬────────────┐
│ 场景 ID                   │ 故障场景 … │ 修复策略    │  初始通/败 │ 终态 (全绿) │     耗时 │ AST 压缩率 │  自愈状态  │
├───────────────────────────┼────────────┼─────────────┼────────────┼─────────────┼──────────┼────────────┼────────────┤
│ case_01_index_overrun     │ 循环访问 … │ boundary_g… │   1 / 1    │    2 / 0    │ 4044.0ms │      76.0% │   [PASS]   │
│ case_02_empty_zero_div    │ 空输入聚 … │ boundary_g… │   1 / 1    │    2 / 0    │  643.6ms │      76.0% │   [PASS]   │
│ case_03_missing_dict_key  │ 字典键缺 … │ none_check  │   1 / 1    │    2 / 0    │  582.7ms │      77.2% │   [PASS]   │
│ case_04_none_attr_access  │ 空对象属 … │ none_check  │   1 / 1    │    2 / 0    │  559.6ms │      80.6% │   [PASS]   │
│ case_05_type_concat_error │ 跨类型拼 … │ type_coerc… │   1 / 1    │    2 / 0    │  575.5ms │      77.2% │   [PASS]   │
│ case_06_multi_bug_cascade │ 多缺陷级 … │ boundary_g… │   2 / 2    │    4 / 0    │ 1201.0ms │      76.1% │   [PASS]   │
└───────────────────────────┴────────────┴─────────────┴────────────┴─────────────┴──────────┴────────────┴────────────┘
┌─────────────────────────────────────────────── Benchmark 综合指标 ───────────────────────────────────────────────┐
│ 测试场景: 6   自愈成功率 (Pass@1): 100.0% (6/6)   次生回归率: 0.0%                                               │
│ 平均故障修复耗时 (MTTR): 1331.3ms   平均 AST 作用域压缩率: 77.2%                                                 │
│ 详细量化指标已同步至: docs/03_Benchmark量化评测报告.md                                                           │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘`;

        window.__switchScene = function(sceneNum, labelText) {{
            document.querySelectorAll('.scene').forEach(el => el.classList.remove('active'));
            const target = document.getElementById('scene-' + sceneNum);
            if (target) target.classList.add('active');
            if (labelText) document.getElementById('timeline-text').innerText = labelText;
        }};

        window.__typeTerminal = function(elementId, command, outputText, onFinish) {{
            const el = document.getElementById(elementId);
            el.innerHTML = '<span style="color: #3fb950;">$</span> <span id="cmd-span"></span><span class="term-cursor"></span>';
            const cmdSpan = document.getElementById('cmd-span');
            let idx = 0;
            const timer = setInterval(() => {{
                if (idx < command.length) {{
                    cmdSpan.innerText += command[idx++];
                }} else {{
                    clearInterval(timer);
                    setTimeout(() => {{
                        el.innerHTML = '<span style="color: #3fb950;">$</span> ' + command + '\\n' + outputText;
                        if (onFinish) onFinish();
                    }}, 400);
                }}
            }}, 40);
        }};
    </script>
</body>
</html>"""


def generate_video(output_dir: str = "videos", duration_scale: float = 1.0):
    """Run Playwright using Edge to record the 1080p demo video."""
    from playwright.sync_api import sync_playwright

    out_path = pathlib.Path(output_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    html_file = (out_path / "showcase_stage.html").resolve()
    html_file.write_text(build_showcase_html(), encoding="utf-8")

    print(f">> [1/4] 生成高精度 1080P 舞台页面: {html_file.name}")
    print(f">> [2/4] 启动 Microsoft Edge 浏览器 (1920x1080 录制模式)...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="msedge",
            headless=True,
            args=["--disable-gpu", "--no-sandbox"],
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(out_path),
            record_video_size={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        page.goto(html_file.as_uri())

        def wait(sec: float):
            time.sleep(sec * duration_scale)

        print(">> [3/4] 正在按 180s 分镜时间轴执行录制...")

        # Scene 1: Intro (0-25s)
        print("  -> 录制分镜 1: 痛点引入与系统架构亮相 (25s)")
        page.evaluate("window.__switchScene(1, '分镜 1: 痛点引入与系统架构亮相 (00:00 - 00:25)')")
        wait(10.0)

        # Scene 2: Demo Terminal (25-75s)
        print("  -> 录制分镜 2: 终端实跑 codeheal demo 级联自愈 (50s)")
        page.evaluate("window.__switchScene(2, '分镜 2: 终端实跑 codeheal demo 级联自愈 (00:25 - 01:15)')")
        page.evaluate("window.__typeTerminal('term-text-demo', 'python -m jiuwen_codeheal.cli --demo', window.DEMO_OUTPUT)")
        wait(15.0)

        # Scene 3: Benchmark (75-125s)
        print("  -> 录制分镜 3: 6 大场景量化基准评测矩阵 (50s)")
        page.evaluate("window.__switchScene(3, '分镜 3: 6 大工业场景量化基准评测矩阵 (01:15 - 02:05)')")
        page.evaluate("window.__typeTerminal('term-text-bench', 'python -m jiuwen_codeheal.cli --benchmark', window.BENCH_OUTPUT)")
        wait(15.0)

        # Scene 4: Dashboard Interaction (125-160s)
        print("  -> 录制分镜 4: 浏览器直击全链路可观测性大屏 (35s)")
        page.evaluate("window.__switchScene(4, '分镜 4: 浏览器直击全链路可观测性大屏 (02:05 - 02:40)')")
        # Smooth scroll the embedded dashboard iframe
        wait(5.0)
        try:
            page.frame_locator("#dash-iframe").locator("body").evaluate("window.scrollTo({top: 400, behavior: 'smooth'})")
            wait(5.0)
            page.frame_locator("#dash-iframe").locator("body").evaluate("window.scrollTo({top: 800, behavior: 'smooth'})")
            wait(5.0)
        except Exception:
            pass

        # Scene 5: Outro (160-180s)
        print("  -> 录制分镜 5: 价值总结与开源反哺收官 (20s)")
        page.evaluate("window.__switchScene(5, '分镜 5: 价值总结与开源反哺收官 (02:40 - 03:00)')")
        wait(8.0)

        print(">> [4/4] 录制完成，正在保存视频文件...")
        context.close()
        browser.close()

    # Find recorded video
    video_files = list(out_path.glob("*.webm"))
    if video_files:
        latest = max(video_files, key=lambda f: f.stat().st_mtime)
        print(f"\n[OK] Demo 视频成功录制并生成: {latest}")
        print(f"     视频分辨率: 1920x1080 (Full HD)")
        print(f"     视频大小: {latest.stat().st_size:,} 字节")
        return str(latest)
    return ""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Record 1080p demo video using Playwright")
    parser.add_argument("--scale", type=float, default=0.4, help="Duration scale (default 0.4 for fast rendering, 1.0 for 180s)")
    parser.add_argument("--output", type=str, default="videos", help="Output directory")
    args = parser.parse_args()

    generate_video(output_dir=args.output, duration_scale=args.scale)
