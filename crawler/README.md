# 中医百科爬虫

爬取中医百科站内列表页，将条目名称与详情页网址保存为 Excel（自动排除导航、页脚等无效数据）。

## 依赖安装

```bash
pip install -r requirements.txt
```

## 1. 中医方剂列表

```bash
python crawl_fangji.py
```

- 目标页：[中医方剂](https://zhongyibaike.com/wiki/%E4%B8%AD%E5%8C%BB%E6%96%B9%E5%89%82)
- 输出：**中医方剂列表.xlsx**，两列：**方剂名称**、**网址**

## 2. 中药大全列表

```bash
python crawl_zhongyao.py
```

- 目标页：[中药大全](https://zhongyibaike.com/wiki/%E4%B8%AD%E8%8D%AF%E5%A4%A7%E5%85%A8)
- 输出：**中药大全列表.xlsx**，两列：**名称**、**网址**

## 3. 按方剂列表抓取详情页为 txt

依赖 **中医方剂列表.xlsx**（需先运行 `crawl_fangji.py` 生成）。

```bash
python fetch_fangji_pages.py
```

- 读取 **中医方剂列表.xlsx** 中每一行的「网址」
- 请求每个网址，提取页面正文
- 将正文保存为 **方剂详情/** 目录下的 txt 文件，文件名由「方剂名称」生成（非法字符会替换）
- 每次请求间隔约 1 秒，减少对目标站压力
- 支持断点续传（已存在的 txt 会跳过）、按块提取正文并整理换行与标点格式

## 4. 按中药大全列表抓取详情页为 txt

依赖 **中药大全列表.xlsx**（需先运行 `crawl_zhongyao.py` 生成）。

```bash
python fetch_zhongyao_pages.py
```

- 读取 **中药大全列表.xlsx** 中每一行的「网址」
- 请求每个网址，按块提取正文并整理格式（与方剂详情脚本一致）
- 将正文保存为 **中药详情/** 目录下的 txt 文件，文件名由「名称」生成
- 支持断点续传（已存在且非空的 txt 会跳过），每次请求间隔约 1 秒
