# 爬取数据

# 1.用request库爬取索引页

用**requests**库爬取索引页，注意结果是在Ajax中返回的，所以请求的页面应该是Ajax请求的页面，并不是索引页原始html请求的页面，所以爬取的url为：[https://www.toutiao.com/search\_content/?offset=0&format=json&keyword=街拍&autoload=true&count=20&cur\_tab=1&from=search\_tab](https://www.toutiao.com/search_content/?offset=0&format=json&keyword=街拍&autoload=true&count=20&cur_tab=1&from=search_tab)  
定义一个_**get\_index\_page()**_函数来获得索引页的源码：

```py
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
```
**urllib.parse.encode()**方法可以将dict解析为url的参数。
接下来解析索引页面，定义一个**_parse_index_page()_**函数来进行解析索引页的源码，并解析出每组图的url：
```py
def parse_index_page(html):
    data = json.loads(html)  # 将Json对象解析为python字典，data的形式为{{}..,data:[{}...{},...],{}}
    if data and 'data' in data.keys():
        for item in data.get('data'):  # data.get('data') 得到的是包含字典的列表
            yield item.get('article_url')  # 没有article_url属性会得到空值
```
因为请求回来的html是以Json形式返回的，所以用**_json.loads()_**方法将Json字符串转换为Python对象（此处是python字典）。这样就获得了组图url的生成器。
接下来定义一个**_get_detail_page()_**函数，根据上面获取的url来请求每个组图的详细页面：
```py
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
```
然后定义一个**_parse_detail_page()_**函数来对详情页面进行解析，得到每个组图的**title**和子图的**url**：
```py
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
```
用BeautifulSoup的CSS选择器来直接提取每个组图的**title**，并用正则表达式获得包含子图url的Json对象。匹配到的Json对象中含有**\**,需要格式化一下，不然**_json.loads()_**方法会报错。因为只有图集形式的页面的html中才含有这个格式的Json对象，所以_**re.search()**_后，判断一下**result**，就自动把那些非图集形式的url筛选掉了。在匹配到的Json对象中**sub_imagesj**的键值就是子图url的列表，解表进行遍历并下载。然后返回一个图集标题，图集url，图集子图url的字典，方便存入Mongodb。上述使用的**_download_images()_**函数定义如下：
```py
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
```
该函数请求子图url并调用**_save_images()_**函数来讲图片保存到本地。**_save_images()_**函数定义如下：
```py
def save_images(content):
    file_path = '{0}/images/{1}.{2}'.format(os.getcwd(), md5(content).hexdigest(), 'jpg')
    if not os.path.exists(file_path):
        with open(file_path, 'wb') as file:
            file.write(content)
            file.close()
```
**_hashlib.md5()_**保证不会下载重复的图片。
最后定义一个**_main()_**函数来进行调度：
```py
def main(offset):
    html = get_index_page(offset, KEYWORD)  # 根据位移和关键字获取索引页面
    for url in parse_index_page(html):  # 遍历解析出的组图url
        if url:  # 有可能data数据中没有article_url属性，返回为空，所以需要判断一下
            html = get_detail_page(url)  # 根据组图url请求详情页面
            result = parse_detail_page(html, url)  # 解析详情页面，保存图片，并返回一个字典用于存入Mongodb
            if result:
                save_to_mongo(result)
```
通过索引页，观察Ajax请求，发现其他参数都是一样的只有**offset**参数以20的倍数增加，所有可以用**offset**来控制开启多线程控制遍历。上述**_save_to_mongo()_**定义如下：
```py
client = pymongo.MongoClient(MONGO_URL)
db = client[MONGO_DB]
def save_to_mongo(result):
    if db[MONGO_TABLE].insert(result):
        print('存储到MongoDb成功', result)
        return True
    else:
        return False
```
这里使用了一个名为**config.py**的配置文件。
最后的测试：
```py
if __name__ == '__main__':
    groups = [x*20 for x in range(GROUP_START, GROUP_END+1)]
    pool = Pool()
    pool.map(main, groups)
```
完成的代码上传到Github上。
