"""
测试美女图片API接口
"""
import requests

def test_meinv_api():
    """测试xxapi.cn的美女图片接口"""
    url = 'https://v2.xxapi.cn/api/meinvpic?return=json'

    print(f"正在测试API: {url}")
    print("-" * 50)

    try:
        response = requests.get(url, timeout=10)

        print(f"状态码: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"响应数据: {data}")

            # 尝试获取图片URL
            image_url = data.get('data') or data.get('url') or data.get('img') or data.get('image')

            if image_url:
                print(f"\n成功获取图片URL: {image_url}")
                return True
            else:
                print(f"\n响应中未找到图片URL")
                return False
        else:
            print(f'API请求失败: {response.status_code}')
            return False

    except requests.exceptions.Timeout:
        print("请求超时")
        return False
    except requests.exceptions.RequestException as e:
        print(f"网络请求错误: {e}")
        return False
    except Exception as e:
        print(f"未知错误: {e}")
        return False

if __name__ == "__main__":
    test_meinv_api()
