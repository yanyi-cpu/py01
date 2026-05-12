import csv
import requests
from lxml import html

all_data = []
target_url = "https://quotes.toscrape.com/"


def main():
    print("正在爬取第1页...")
    response = requests.get(target_url, timeout=60)
    parse_page(response.text)

    for num in range(2, 11):
        print(f"正在爬取第{num}页...")
        url = target_url + f"page/{num}/"
        response = requests.get(url, timeout=60)
        parse_page(response.text)

def parse_page(html_text):
    doc = html.fromstring(html_text)
    quote_list = doc.xpath('//div[@class="quote"]')
    for quote in quote_list:
        text = quote.xpath("./span[@class='text']/text()")
        author = quote.xpath("./span/small[@class='author']/text()")
        tags = quote.xpath("./div[@class='tags']/a/text()")

        dict_data = {
            "text": text[0].strip() if text else "",
            "author": author[0].strip() if author else "",
            "tags": ",".join(tags) if tags else ""
        }
        all_data.append(dict_data)


def write_csv(data):
    with open("quotes_all.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "author", "tags"])
        writer.writeheader()
        writer.writerows(data)
    print(f"✅ 爬取完成！共获取 {len(data)} 条数据，已保存到 quotes_all.csv")


if __name__ == '__main__':
    main()
    write_csv(all_data)