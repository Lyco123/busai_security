import asyncio
import time


import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import logging


# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class WebPageExecutor:
    def __init__(self, url):
        self.url = url
        self.driver = None

    def setup_driver(self):
        """设置Chrome浏览器驱动"""

        chrome_options = Options()
        chrome_options.add_argument('--headless')  # 无头模式（不显示浏览器窗口）
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        # service = Service(ChromeDriverManager().install())
        # service = Service(executable_path='./bin/chromedriver.exe')  # 使用相对路径
        # self.driver = webdriver.Chrome(service=service,options=chrome_options)

        self.driver = webdriver.Chrome(options=chrome_options)


    def open_and_run_page(self):
        """打开网页并等待运行完成"""
        try:
            if not self.driver:
                self.setup_driver()

            # 打开指定网页
            logger.info(f"正在打开页面: {self.url}")
            self.driver.get(self.url)

            # 等待页面加载完成
            # 这里可以根据页面具体特征调整等待条件
            try:
                wait = WebDriverWait(self.driver, 30)
            except Exception as e:
                logger.error(f"打开页面时出错: {str(e)}")
                return None
            # 等待页面中某个元素出现（根据实际情况修改）
            # 例如等待页面标题包含特定文本
            try:
                wait.until(EC.title_contains("CAN"))
            except Exception as e:
                logger.error(f"打开页面时出错: {str(e)}")
                return None

            # 或者等待某个特定元素出现
            # wait.until(EC.presence_of_element_located((By.ID, "output")))

            # 等待一段时间让JavaScript执行完成
            time.sleep(5)

            # 获取页面标题和URL验证页面已加载
            logger.info(f"页面标题: {self.driver.title}")
            logger.info(f"当前URL: {self.driver.current_url}")

            # 可以执行页面中的JavaScript
            page_data = self.driver.execute_script("""
                // 获取页面中的关键数据
                try {
                    // 根据实际页面结构调整选择器
                    const canData = document.getElementById('output')?.innerText;
                    const obuidData = document.getElementById('obuid')?.innerText;

                    return {
                        title: document.title,
                        url: window.location.href,
                        can: canData,
                        obuid: obuidData,
                        timestamp: new Date().toISOString()
                    };
                } catch (e) {
                    return {
                        title: document.title,
                        url: window.location.href,
                        error: e.message,
                        timestamp: new Date().toISOString()
                    };
                }
            """)

            logger.info("页面执行完成，获取到数据")
            return page_data

        except Exception as e:
            logger.error(f"打开页面时出错: {str(e)}")
            return None

    def submit_data(self, data, target_url):
        """提交数据到指定接口"""
        try:
            if data:
                # 提交到指定后端地址
                response = requests.post(
                    target_url,
                    json={"data": data},
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )

                if response.status_code == 200:
                    logger.info("数据提交成功")
                    return response.json()
                else:
                    logger.error(f"数据提交失败，状态码: {response.status_code}")
                    return None
            else:
                logger.warning("没有数据可提交")
                return None

        except Exception as e:
            logger.error(f"提交数据时出错: {str(e)}")
            return None

    def run_once(self, submit_url=None):
        """执行一次完整的流程"""
        try:
            logger.info("开始执行网页...")
            page_data = self.open_and_run_page()
            return page_data

            # if page_data and submit_url:
            #     logger.info("开始提交数据...")
            #     result = self.submit_data(page_data, submit_url)
            #     return result
            # else:
            #     return page_data

        except Exception as e:
            logger.error(f"执行任务时出错: {str(e)}")
            return None
        finally:
            if self.driver:
                self.driver.quit()
                self.driver = None


async def decrypt_main():
    """can数据解密"""
    # 配置目标网页URL
    target_url = "http://127.0.0.1:9000/vadmin/analysis/getCanData"

    # 可选：配置数据提交URL
    submit_url = "http://127.0.0.1:9000/vadmin/analysis/updateTest"  # 如果需要提交数据


    # # 创建执行器实例
    executor = WebPageExecutor(target_url)

    try:
        # 执行一次任务
        result = executor.run_once(submit_url)

        if result:
            # logger.info(f"任务执行成功，返回数据: {json.dumps(result, indent=2, ensure_ascii=False)}")
            logger.info(f"任务执行成功")
        else:
            logger.error("任务执行失败")

    except Exception as e:
        logger.error(f"主程序执行出错: {str(e)}")


if __name__ == "__main__":
    asyncio.run(decrypt_main())
