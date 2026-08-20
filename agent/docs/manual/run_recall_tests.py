"""
Recall rate test automation script using Playwright.
This script automates the testing process for the remaining 38 test cases
across 4 report pipelines (unit, route, driver, accident).

Usage:
  python run_recall_tests.py

Requirements:
  pip install playwright
  playwright install chromium

The script will:
1. Open the test page in a browser
2. For each test case, create a new conversation, send a message, and wait for response
3. Extract metadata.tool from the session poll response
4. Save results to a JSON file for backfilling into manual files
"""

import asyncio
import json
import re
import time
from pathlib import Path

from playwright.async_api import async_playwright

TEST_PAGE = "https://busodemo.canocache.com/assistant"
API_BASE = "https://api.buso.canocache.com/api/agent"
OUTPUT_FILE = Path(__file__).parent / "recall_test_results.json"

SINGLE_ROUND_TESTS = {
    "unit": {
        "E2": {
            "input": "帮我整一份单位维度的安全管理复盘，就二巴公司这一家，出完整正式报告，不要个人版。",
            "expected_tool": "generate_unit_report",
            "should_recall": True,
        },
        "E3": {
            "input": "任宇邦师傅的驾驶员安全分析报告，单人版，别搞单位汇总。",
            "expected_not_tool": "generate_unit_report",
            "should_recall": False,
        },
        "E4": {
            "input": "帮出一份组织管理人员版安全风险分析总结报告。（暂不指定具体单位名称）",
            "expected_not_tool": "generate_unit_report",
            "should_recall": False,
        },
        "E5": {
            "input": "二巴公司安全情况先给结论，再列出三条关键要点解读即可；不要生成完整正式报告，不用报告排版格式。",
            "expected_not_tool": "generate_unit_report",
            "should_recall": False,
        },
    },
    "route": {
        "R+1": {
            "input": "527路，管理口要看线路运营安全画像，正式完整输出。",
            "expected_tool": "generate_route_report",
            "should_recall": True,
        },
        "R+2": {
            "input": "整一份 527路 安全方面的正式材料，别给碎片化问答。",
            "expected_tool": "generate_route_report",
            "should_recall": True,
        },
        "R+3": {
            "input": "527路 的线路安全总结报告，管理人员版。",
            "expected_tool": "generate_route_report",
            "should_recall": True,
        },
        "R+5": {
            "input": "Route 527 ops safety profile (management); formal output required.",
            "expected_tool": "generate_route_report",
            "should_recall": True,
        },
        "R-1": {
            "input": "我要车辆安全画像，车牌 粤A02650D，不说线路编号。",
            "expected_not_tool": "generate_route_report",
            "should_recall": False,
        },
        "R-2": {
            "input": "不要出正式报告，查一下 527路 的日均客流、班次配置就行。",
            "expected_not_tool": "generate_route_report",
            "should_recall": False,
        },
        "R-3": {
            "input": "别生成报告。告诉我 527路 有没有线路安全画像数据就好。",
            "expected_not_tool": "generate_route_report",
            "should_recall": False,
        },
        "R-4": {
            "input": "527路 和 100130路 横向对比安全概况，不给单条线路的长篇报告。",
            "expected_not_tool": "generate_route_report",
            "should_recall": False,
        },
        "R-5": {
            "input": "公交线路运营安全管理一般从哪些维度入手？不提具体线路编号。",
            "expected_not_tool": "generate_route_report",
            "should_recall": False,
        },
    },
    "driver": {
        "R+1": {
            "input": "管理层要看 任宇邦 师傅的安全履职画像，正式版、别给碎片化问答。",
            "expected_tool": "generate_driver_report",
            "should_recall": True,
        },
        "R+2": {
            "input": "工号 03001402 这位师傅，帮搞一份车队长看的安全方面材料，别给零散点评。",
            "expected_tool": "generate_driver_report",
            "should_recall": True,
        },
        "R+3": {
            "input": "关飞鸿，管理人员版驾驶员安全总结正式报告。",
            "expected_tool": "generate_driver_report",
            "should_recall": True,
        },
        "R+5": {
            "input": "Need a driver safety briefing (management) for 关飞鸿; employee id 03001402 if the name is ambiguous.",
            "expected_tool": "generate_driver_report",
            "should_recall": True,
        },
        "R-1": {
            "input": "我要线路安全画像，527路，全程不说驾驶员名字。",
            "expected_not_tool": "generate_driver_report",
            "should_recall": False,
        },
        "R-2": {
            "input": "不出正式报告，查一下 03001982 的当班线路、累计里程就行。",
            "expected_not_tool": "generate_driver_report",
            "should_recall": False,
        },
        "R-3": {
            "input": "别生成报告。告诉我 任宇邦（03001982）有没有驾驶员画像数据就好。",
            "expected_not_tool": "generate_driver_report",
            "should_recall": False,
        },
        "R-4": {
            "input": "关飞鸿 和 任宇邦 安全表现横向对比，不要只给一个人的长篇报告。",
            "expected_not_tool": "generate_driver_report",
            "should_recall": False,
        },
        "R-5": {
            "input": "公交驾驶员日常安全考核一般看哪些指标？不提具体姓名或工号。",
            "expected_not_tool": "generate_driver_report",
            "should_recall": False,
        },
    },
    "accident": {
        "R+1": {
            "input": "事故 INC-20251014-01，帮出一份事故调查与整改措施正式报告，管理口径，章节齐全。",
            "expected_tool": "generate_accident_investigation_report",
            "should_recall": True,
        },
        "R+2": {
            "input": "搞一份 环市西路段刮碰事故 的事故调查复盘，要按正式调查报告格式输出，别给零碎问答。",
            "expected_tool": "generate_accident_investigation_report",
            "should_recall": True,
        },
        "R+3": {
            "input": "INC-20251014-01 那起刮碰事故，我要事故调查报告（含整改），标识对不上再问我。",
            "expected_tool": "generate_accident_investigation_report",
            "should_recall": True,
        },
        "R+5": {
            "input": "Please generate the accident investigation and remediation report for incident INC-20251014-01 (formal management version).",
            "expected_tool": "generate_accident_investigation_report",
            "should_recall": True,
        },
        "R-1": {
            "input": "不要出调查报告。把 INC-20251014-01 的事故经过与责任认定查出来即可，短文就行。",
            "expected_not_tool": "generate_accident_investigation_report",
            "should_recall": False,
        },
        "R-2": {
            "input": "环市西路段刮碰事故 同类事故还有几条？列编号和标题就行，不要给我整篇整改报告。",
            "expected_not_tool": "generate_accident_investigation_report",
            "should_recall": False,
        },
        "R-3": {
            "input": "INC-20251014-01 先解读三条风险要点就行，不要输出完整正式调查报告排版。",
            "expected_not_tool": "generate_accident_investigation_report",
            "should_recall": False,
        },
        "R-4": {
            "input": "我要 任宇邦 的驾驶员安全分析报告，个人版；别提事故编号。",
            "expected_not_tool": "generate_accident_investigation_report",
            "should_recall": False,
        },
        "R-5": {
            "input": "公交事故内部调查与整改的一般流程是怎样的？不提具体事故编号。",
            "expected_not_tool": "generate_accident_investigation_report",
            "should_recall": False,
        },
    },
}

MULTI_ROUND_TESTS = {
    "unit": {
        "M1": {
            "q1": "广州今天天气怎么样？",
            "q2": "换个话题。请按业务数据给二巴公司出一份单位安全风险分析总结报告（管理人员版）。",
            "expected_tool": "generate_unit_report",
            "should_recall": True,
        },
        "M2": {
            "q1": "二巴公司的管理层安全总结我这边要汇报用。",
            "q2": "就按正式报告流程输出。",
            "expected_tool": "generate_unit_report",
            "should_recall": True,
        },
        "M3": {
            "q1": "组织级安全类产出有哪些？先列类型。",
            "q2": "那就给二巴公司出单位安全风险分析总结，管理人员版。",
            "expected_tool": "generate_unit_report",
            "should_recall": True,
        },
        "M4": {
            "q1": "帮我准备一份公司层面安全材料，管理口要用。",
            "q2": "补充：要单位正式安全风险分析总结报告，对象是二巴公司。",
            "expected_tool": "generate_unit_report",
            "should_recall": True,
        },
        "M5": {
            "q1": "生成一汽公司的单位安全风险分析总结报告（管理人员版）。",
            "q2": "单位搞错了，应该是二巴公司，请按二巴公司继续生成单位报告。",
            "expected_tool": "generate_unit_report",
            "should_recall": True,
        },
    },
    "route": {
        "R+4": {
            "q1": "我要线路级的安全总结，模块要齐全。",
            "q2": "线路 527路。",
            "expected_tool": "generate_route_report",
            "should_recall": True,
        },
    },
    "driver": {
        "R+4": {
            "q1": "我要出一份驾驶员侧的安全总结，版式齐、别漏模块。",
            "q2": "驾驶员 任宇邦，工号 03001982。",
            "expected_tool": "generate_driver_report",
            "should_recall": True,
        },
    },
    "accident": {
        "R+4": {
            "q1": "帮我生成事故调查整改的正式报告，格式要齐。",
            "q2": "事故编号 INC-20251014-01。",
            "expected_tool": "generate_accident_investigation_report",
            "should_recall": True,
        },
    },
}


async def get_metadata_tool_from_network(page, max_wait=120):
    """Wait for the chat/stream response and extract metadata.tool from network requests."""
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        await page.wait_for_timeout(5000)
        
        try:
            captured_tool = await page.evaluate("window._capturedTool")
            if captured_tool:
                return captured_tool
        except:
            pass
    
    return None


async def run_single_round_test(page, test_id, test_data, pipeline):
    """Run a single-round test: create new conversation, send message, get result."""
    
    # Reset captured tool
    await page.evaluate("window._capturedTool = null")
    
    # Click "新建对话" button
    await page.get_by_role("button", name="新建对话").click()
    await page.wait_for_timeout(2000)
    
    # Type the test message in the textarea and submit
    textarea = page.locator("textarea[placeholder*='输入消息']")
    await textarea.fill(test_data["input"])
    await textarea.press("Enter")
    
    # Wait for the response and extract metadata.tool
    tool = await get_metadata_tool_from_network(page, max_wait=120)
    
    # Evaluate the result
    result = {
        "test_id": test_id,
        "pipeline": pipeline,
        "input": test_data["input"],
        "should_recall": test_data["should_recall"],
        "metadata_tool": tool,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    
    if tool is None:
        result["status"] = "timeout"
        result["pass"] = False
    elif test_data["should_recall"]:
        expected = test_data.get("expected_tool", f"generate_{pipeline}_report")
        result["status"] = "hit" if tool == expected else "wrong_tool"
        result["pass"] = tool == expected
    else:
        not_expected = test_data.get("expected_not_tool", f"generate_{pipeline}_report")
        result["status"] = "correct_rejection" if tool != not_expected else "false_positive"
        result["pass"] = tool != not_expected
    
    return result


async def run_multi_round_test(page, test_id, test_data, pipeline):
    """Run a multi-round test: send Q1, wait for response, then send Q2 in same session."""
    
    # Reset captured tool
    await page.evaluate("window._capturedTool = null")
    
    # Click "新建对话" button
    await page.get_by_role("button", name="新建对话").click()
    await page.wait_for_timeout(2000)
    
    # Type Q1 and submit
    textarea = page.locator("textarea[placeholder*='输入消息']")
    await textarea.fill(test_data["q1"])
    await textarea.press("Enter")
    
    # Wait for Q1 response (shorter wait, since Q1 is usually a simple question)
    await page.wait_for_timeout(60_000)
    
    # Reset captured tool for Q2
    await page.evaluate("window._capturedTool = null")
    
    # Type Q2 and submit (in the SAME session)
    await textarea.fill(test_data["q2"])
    await textarea.press("Enter")
    
    # Wait for Q2 response and extract metadata.tool
    tool = await get_metadata_tool_from_network(page, max_wait=120)
    
    # Evaluate the result
    result = {
        "test_id": test_id,
        "pipeline": pipeline,
        "q1": test_data["q1"],
        "q2": test_data["q2"],
        "should_recall": test_data["should_recall"],
        "metadata_tool": tool,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    
    if tool is None:
        result["status"] = "timeout"
        result["pass"] = False
    else:
        expected = test_data.get("expected_tool", f"generate_{pipeline}_report")
        result["status"] = "hit" if tool == expected else "wrong_tool"
        result["pass"] = tool == expected
    
    return result


async def install_fetch_interceptor(page):
    """Install a fetch interceptor to capture metadata.tool from SSE responses."""
    await page.evaluate("""
        () => {
            window._capturedTool = null;
            const originalFetch = window.fetch;
            window.fetch = function(...args) {
                const url = args[0];
                const options = args[1] || {};
                
                if (url && url.toString().includes('/api/agent/chat/stream') && options.method === 'POST') {
                    return originalFetch.apply(this, args).then(async response => {
                        const cloned = response.clone();
                        try {
                            const text = await cloned.text();
                            const lines = text.split('\\n');
                            for (const line of lines) {
                                if (line.startsWith('data: ')) {
                                    try {
                                        const data = JSON.parse(line.substring(6));
                                        if (data.type === 'final' && data.message && data.message.metadata && data.message.metadata.tool) {
                                            window._capturedTool = data.message.metadata.tool;
                                        }
                                    } catch(e) {}
                                }
                            }
                        } catch(e) {}
                        return response;
                    });
                }
                
                return originalFetch.apply(this, args);
            };
        }
    """)


async def main():
    results = {}
    
    # Load any previously saved results
    if OUTPUT_FILE.exists():
        results = json.loads(OUTPUT_FILE.read_text())
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        # Navigate to test page
        await page.goto(TEST_PAGE)
        await page.wait_for_timeout(5000)
        
        # Install fetch interceptor
        await install_fetch_interceptor(page)
        
        # Run single-round tests
        for pipeline, tests in SINGLE_ROUND_TESTS.items():
            for test_id, test_data in tests.items():
                # Skip if already done
                if test_id in results.get(pipeline, {}):
                    print(f"Skipping {pipeline}/{test_id} - already done")
                    continue
                
                print(f"Running {pipeline}/{test_id}: {test_data['input'][:50]}...")
                result = await run_single_round_test(page, test_id, test_data, pipeline)
                
                print(f"  Result: tool={result['metadata_tool']}, status={result['status']}, pass={result['pass']}")
                
                if pipeline not in results:
                    results[pipeline] = {}
                results[pipeline][test_id] = result
                
                # Save results incrementally
                OUTPUT_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False))
        
        # Run multi-round tests
        for pipeline, tests in MULTI_ROUND_TESTS.items():
            for test_id, test_data in tests.items():
                if test_id in results.get(pipeline, {}):
                    print(f"Skipping {pipeline}/{test_id} - already done")
                    continue
                
                print(f"Running {pipeline}/{test_id} (multi-round): Q1={test_data['q1'][:30]}...")
                result = await run_multi_round_test(page, test_id, test_data, pipeline)
                
                print(f"  Result: tool={result['metadata_tool']}, status={result['status']}, pass={result['pass']}")
                
                if pipeline not in results:
                    results[pipeline] = {}
                results[pipeline][test_id] = result
                
                OUTPUT_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False))
        
        await browser.close()
    
    print(f"\nAll tests completed. Results saved to {OUTPUT_FILE}")
    
    # Print summary
    for pipeline in ["unit", "route", "driver", "accident"]:
        if pipeline in results:
            pipeline_results = results[pipeline]
            total = len(pipeline_results)
            passed = sum(1 for r in pipeline_results.values() if r.get("pass", False))
            print(f"{pipeline}: {passed}/{total} passed")


if __name__ == "__main__":
    asyncio.run(main())