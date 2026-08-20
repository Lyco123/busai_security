import asyncio

import requests
import json
from datetime import datetime

from application.settings import ai_api_url


async def fetch_report_summary(payload:dict):
    """
    从指定接口获取报告摘要数据
    """
    # 接口URL
    # url = "http://10.181.92.105:8001/ai/api/agent/reports/summary"
    url=ai_api_url

    # 请求参数
    # payload = {
    #     "driverName": "廖耀浪",
    #     "ppartition": "20260610"
    # }

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = {
        "userName": "appAdmin",
        "requestTime": current_time
    }
    result = json.dumps(data)

    # 请求头部信息
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "X-transparent-para": result,  # 请替换为实际值
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9"
    }

    try:
        # 发送POST请求
        response = requests.post(
            url=url,
            headers=headers,
            data=json.dumps(payload),
            timeout=120  # 设置120秒超时
        )

        # 检查响应状态
        response.raise_for_status()

        # 解析JSON响应
        result = response.json()

        return {
            "success": True,
            "status_code": response.status_code,
            "data": result
            # "headers": dict(response.headers)
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"请求失败: {str(e)}",
            "status_code": getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
        }
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"JSON解析失败: {str(e)}",
            "raw_response": response.text if 'response' in locals() else None
        }


async def fetch_send_report(content:str,url:str,id:str):

    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "id": id,
        "suggestedContent": content
    }

    #请求头部信息
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9"
    }

    try:
        # 发送POST请求
        response = requests.post(
            url=url,
            headers=headers,
            data=json.dumps(payload),
            timeout=60
        )

        # 检查响应状态
        response.raise_for_status()

        # 解析JSON响应
        result = response.json()

        return {
            "success": True,
            "status_code": response.status_code,
            "data": result
            # "headers": dict(response.headers)
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"请求失败: {str(e)}",
            "status_code": getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
        }
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"JSON解析失败: {str(e)}",
            "raw_response": response.text if 'response' in locals() else None
        }


async def report_main(payload:dict):
    """
    主函数：执行数据获取并处理结果
    """
    print("开始从接口获取数据...")
    print("=" * 50)

    # 调用函数获取数据
    result = await fetch_report_summary(payload)
    if result["success"]:
        print("✅ 请求成功！")
        # print(f"状态码: {result['status_code']}")
        # print(f"响应头: {json.dumps(result['headers'], indent=2, ensure_ascii=False)}")
        # print("\n📊 返回数据:")
        # print(json.dumps(result['data'], indent=2, ensure_ascii=False))

        # # 保存数据到文件
        return result['data']['content']
        # with open('report_summary.json', 'w', encoding='utf-8') as f:
        #     json.dump(result['data']['content'], f, indent=2, ensure_ascii=False)
        # print(f"\n💾 数据已保存到: report_summary.json")
        # return (json.dumps(result['data']['content'], indent=2, ensure_ascii=False))
    else:
        print("❌ 请求失败！")
        print(f"错误信息: {result}")
        # if 'status_code' in result and result['status_code']:
        #     print(f"状态码: {result['status_code']}")
        # if 'raw_response' in result:
        #     print(f"原始响应: {result['raw_response']}")
        return (json.dumps(result, indent=2, ensure_ascii=False))


async def send_report(content:dict,url:str,id:str):
    """
    主函数：执行数据获取并处理结果
    """
    print("开始总结报告入库...")
    print("=" * 50)

    # 调用函数获取数据
    result = await fetch_send_report(content,url,id)
    if result["success"]:
        print("✅ 请求成功！")
        # print(f"状态码: {result['status_code']}")
        # print(f"响应头: {json.dumps(result['headers'], indent=2, ensure_ascii=False)}")
        # print("\n📊 返回数据:")
        # print(json.dumps(result['data'], indent=2, ensure_ascii=False))
        return (json.dumps(result, indent=2, ensure_ascii=False))
        # # 保存数据到文件
        # with open('report_summary.json', 'w', encoding='utf-8') as f:
        #     json.dump(result['data'], f, indent=2, ensure_ascii=False)
        # print(f"\n💾 数据已保存到: report_summary.json"
    else:
        print("❌ 请求失败！")
        # print(f"错误信息: {result['error']}")
        # if 'status_code' in result and result['status_code']:
        #     print(f"状态码: {result['status_code']}")
        # if 'raw_response' in result:
        #     print(f"原始响应: {result['raw_response']}")
        return (json.dumps(result, indent=2, ensure_ascii=False))

# # 增强版：包含错误处理和重试机制
# class ReportFetcher:
#     def __init__(self, base_url="http://10.181.92.105:8001"):
#         self.base_url = base_url
#         self.session = requests.Session()
#
#     def fetch_with_retry(self, max_retries=3):
#         """
#         带重试机制的数据获取
#         """
#
#         url = f"{self.base_url}/ai/api/agent/reports/summary"
#         payload = {
#             "driverName": "廖耀浪",
#             "ppartition": "20260610"
#         }
#
#         current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#         data = {
#             "userName": "appAdmin",
#             "requestTime": current_time
#         }
#         result = json.dumps(data)
#
#         headers = {
#             "Accept": "application/json, text/plain, */*",
#             "Content-Type": "application/json",
#             "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
#             "X-transparent-para": result,
#             "Accept-Encoding": "gzip, deflate, br",
#             "Accept-Language": "zh-CN,zh;q=0.9"
#         }
#
#         for attempt in range(max_retries):
#             try:
#                 print(f"尝试第 {attempt + 1} 次请求...")
#                 response = self.session.post(
#                     url=url,
#                     headers=headers,
#                     json=payload,  # 使用json参数自动序列化
#                     timeout=120
#                 )
#
#                 response.raise_for_status()
#                 data = response.json()
#
#                 print(f"✅ 第 {attempt + 1} 次尝试成功！")
#                 return {
#                     "success": True,
#                     "data": data,
#                     "attempts": attempt + 1
#                 }
#
#             except requests.exceptions.RequestException as e:
#                 print(f"第 {attempt + 1} 次尝试失败: {str(e)}")
#                 if attempt == max_retries - 1:
#                     return {
#                         "success": False,
#                         "error": f"所有{max_retries}次尝试均失败",
#                         "last_error": str(e)
#                     }
#                 # 等待后重试
#                 import time
#                 time.sleep(2 ** attempt)  # 指数退避
#
#     def analyze_response(self, data):
#         """
#         分析响应数据
#         """
#         if not data.get("success"):
#             return "无法分析失败响应"
#
#         result = data["data"]
#         analysis = []
#
#         # 基本分析
#         analysis.append("📈 数据摘要:")
#         analysis.append(f"- 数据类型: {type(result).__name__}")
#
#         if isinstance(result, dict):
#             analysis.append(f"- 包含字段数: {len(result)}")
#             analysis.append(f"- 主要字段: {', '.join(result.keys())}")
#
#             # 如果有特定字段，提供更多信息
#             if 'summary' in result:
#                 analysis.append(f"- 摘要内容: {result['summary'][:100]}...")
#             if 'total' in result:
#                 analysis.append(f"- 总计: {result['total']}")
#
#         elif isinstance(result, list):
#             analysis.append(f"- 列表项数: {len(result)}")
#             if result and isinstance(result, dict):
#                 analysis.append(f"- 每项包含字段: {', '.join(result.keys())}")
#
#         return "\n".join(analysis)


if __name__ == "__main__":
    # 方式1：使用简单函数
    print("方法1：直接调用函数")
    print("-" * 30)
    asyncio.run(report_main())

    print("\n" + "=" * 50 + "\n")

    # 方式2：使用增强版类
    # print("方法2：使用增强版类（带重试机制）")
    # print("-" * 30)
    # fetcher = ReportFetcher()
    # result = fetcher.fetch_with_retry(max_retries=3)
    #
    # if result["success"]:
    #     print(f"✅ 获取成功，尝试次数: {result['attempts']}")
    #     print(fetcher.analyze_response(result))
    #
    #     # 保存详细数据
    #     import datetime
    #
    #     timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    #     filename = f"report_summary_{timestamp}.json"
    #
    #     with open(filename, 'w', encoding='utf-8') as f:
    #         json.dump(result['data'], f, indent=2, ensure_ascii=False)
    #     print(f"💾 详细数据已保存到: {filename}")
    # else:
    #     print(f"❌ 获取失败: {result['error']}")
