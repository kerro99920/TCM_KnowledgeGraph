import requests
from bs4 import BeautifulSoup

url = 'http://www.baidu.com'
response = requests.get(url)
html = response.text

print(html)