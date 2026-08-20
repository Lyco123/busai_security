import requests
from bs4 import BeautifulSoup
import csv
import json
import time
from urllib.parse import urljoin, urlparse
import argparse


def fetch_html(url, headers=None, timeout=10):
    """
    获取网页HTML内容
    """
    if headers is None:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        return response.text
    except requests.RequestException as e:
        print(f"请求失败: {e}")
        return None


def parse_html(html_content):
    """
    解析HTML内容，提取文本和链接
    """
    if not html_content:
        return None

    soup = BeautifulSoup(html_content, 'html.parser')

    # 移除script和style标签
    for script in soup(["script", "style"]):
        script.decompose()

    # 提取页面标题
    title = soup.title.string if soup.title else "无标题"

    # 提取所有文本内容
    text_content = soup.get_text()

    # 清理文本（移除多余空白字符）
    lines = (line.strip() for line in text_content.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text_content = ' '.join(chunk for chunk in chunks if chunk)

    # 提取所有链接
    links = []
    for link in soup.find_all('a', href=True):
        links.append({
            'text': link.get_text().strip(),
            'url': link['href']
        })

    # 提取所有图片
    images = []
    for img in soup.find_all('img', src=True):
        images.append({
            'alt': img.get('alt', ''),
            'src': img['src']
        })

    return {
        'title': title,
        'content': text_content,
        'links': links,
        'images': images
    }


def save_to_csv(data, filename):
    """
    将数据保存为CSV格式
    """
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['title', 'content']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow({'title': data['title'], 'content': data['content'][:1000] + '...'})


def save_to_json(data, filename):
    """
    将数据保存为JSON格式
    """
    with open(filename, 'w', encoding='utf-8') as jsonfile:
        json.dump(data, jsonfile, ensure_ascii=False, indent=2)


def scrape_website(url, output_format='json'):
    """
    爬取网站内容并保存
    """
    print(f"正在爬取: {url}")

    # 获取HTML内容
    html_content = fetch_html(url)
    if not html_content:
        return False

    # 解析内容
    parsed_data = parse_html(html_content)
    if not parsed_data:
        return False

    # 生成文件名
    domain = urlparse(url).netloc
    timestamp = int(time.time())
    filename_base = f"{domain}_{timestamp}"

    # 保存数据
    if output_format.lower() == 'csv':
        save_to_csv(parsed_data, f"{filename_base}.csv")
        print(f"数据已保存到 {filename_base}.csv")
    else:
        save_to_json(parsed_data, f"{filename_base}.json")
        print(f"数据已保存到 {filename_base}.json")

    # 显示结果摘要
    print("\n爬取结果摘要:")
    print(f"标题: {parsed_data['title']}")
    print(f"内容长度: {len(parsed_data['content'])} 字符")
    print(f"链接数量: {len(parsed_data['links'])}")
    print(f"图片数量: {len(parsed_data['images'])}")

    return True


def main():
    parser = argparse.ArgumentParser(description='网页内容爬取工具')
    parser.add_argument('--url', help='要爬取的网页URL')
    parser.add_argument('--format', choices=['json', 'csv'], default='json', help='输出格式 (默认: json)')

    args = parser.parse_args()

    args.url="http://127.0.0.1:900/vadmin/analysis/getCanData"
    # 执行爬取
    success = scrape_website(args.url, args.format)

    if not success:
        print("爬取失败!")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
