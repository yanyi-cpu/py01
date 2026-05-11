import requests
from lxml import html


target_url="https://www.tiobe.com/tiobe-index/"

response=requests.get(target_url)

doc=html.fromstring(response.text)
data=doc.xpath("//table/thead/tr")
for i in data:
    data1=i.xpath("./th/text()")
    print(data1)