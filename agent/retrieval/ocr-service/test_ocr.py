# test_ocr.py
import requests
import sys

def test_ocr(file_path: str):
    url = "http://localhost:8000/ocr/parse"
    
    with open(file_path, 'rb') as f:
        files = {'file': f}
        response = requests.post(url, files=files, data={'language': 'ch'})
    
    result = response.json()
    
    if result['success']:
        print(f"✅ 识别成功")
        print(f"引擎: {result['engine']}")
        print(f"耗时: {result['elapsed_ms']}ms")
        print(f"文本长度: {len(result['full_text'])} 字符")
        print(f"警告: {result['warnings']}")
        print("\n前500字符预览:")
        print(result['full_text'][:500])
    else:
        print(f"❌ 识别失败: {result['error_code']}")
        print(f"错误信息: {result['message']}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python test_ocr.py <文件路径>")
        sys.exit(1)
    test_ocr(sys.argv[1])
