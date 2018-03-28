import requests
import json
import re
import os
import pymongo
from urllib.parse import urlencode
from requests.exceptions import RequestException
from bs4 import BeautifulSoup
from config import *
from hashlib import md5
from multiprocessing import Pool


client = pymongo.MongoClient(MONGO_URL)
db = client[MONGO_DB]


def get_index_page(offset, keyword):
    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/65.0.3325.146 Safari/537.36'
    }
    data = {
        'offset': offset,
        'format': 'json',
        'keyword': keyword,
        'autoload': 'true',
        'count': '20',
        'cur_tab': 1,
        'from': 'search_tab'
    }
    url = 'https://www.toutiao.com/search_content/?' + urlencode(data)
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.text
        return None
    except RequestException:
        print('请求索引页失败!')
        return None


def parse_index_page(html):
    data = json.loads(html)  # 将Json对象解析为python字典，data的形式为{{}..,data:[{}...{},...],{}}
    if data and 'data' in data.keys():
        for item in data.get('data'):  # data.get('data') 得到的是包含字典的列表
            yield item.get('article_url')  # 没有article_url属性会得到空值


def get_detail_page(url):
    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/65.0.3325.146 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.text
        return None
    except RequestException:
        print('请求详细页失败!', url)
        return None


def parse_detail_page(html, url):
    soup = BeautifulSoup(html, 'lxml')
    title = soup.select('title')[0].get_text()
    image_pattern = re.compile('gallery: JSON.parse\("(.*?)"\),', re.S)
    result = re.search(image_pattern, html)
    if result:  # 有的页面数据不一定存放在JSON.parse位置，直接忽略，所以这个位置判断一下
        formate_result = re.sub(r'\\|\\\\', '', result.group(1))  # 将字符串格式化一下，不然json.loads()后还是个str对象
        data = json.loads(formate_result)  # data转换为dic对象
        if data and 'sub_images' in data.keys():
            sub_images = data.get('sub_images')
            image = [item.get('url') for item in sub_images]
            for item in image:
                download_images(item)
            return {
                'title': title,
                'url': url,
                'images': image
            }


def save_to_mongo(result):
    if db[MONGO_TABLE].insert(result):
        print('存储到MongoDb成功', result)
        return True
    else:
        return False


def download_images(url):
    print('下载图片：', url)
    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/65.0.3325.146 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            save_images(response.content)
        return None
    except RequestException:
        print('下载图片失败!', url)
        return None


def save_images(content):
    file_path = '{0}/images/{1}.{2}'.format(os.getcwd(), md5(content).hexdigest(), 'jpg')
    if not os.path.exists(file_path):
        with open(file_path, 'wb') as file:
            file.write(content)
            file.close()


def main(offset):
    html = get_index_page(offset, KEYWORD)  # 根据位移和关键字获取索引页面
    for url in parse_index_page(html):  # 遍历解析出的组图url
        if url:  # 有可能data数据中没有article_url属性，返回为空，所以需要判断一下
            html = get_detail_page(url)  # 根据组图url请求详情页面
            result = parse_detail_page(html, url)  # 解析详情页面，保存图片，并返回一个字典用于存入Mongodb
            if result:
                save_to_mongo(result)


if __name__ == '__main__':
    groups = [x*20 for x in range(GROUP_START, GROUP_END+1)]
    pool = Pool()
    pool.map(main, groups)

