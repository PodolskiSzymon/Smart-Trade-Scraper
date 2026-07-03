from bs4 import BeautifulSoup
import requests

url="https://www.vinted.pl/catalog/3063-karty-pamieci?referrer=item-crumbs"
headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36 Edg/149.0.0.0"}

response= requests.get(url, headers=headers)

if(response.status_code!=200):
    print(f"blad statusu: ", response.status_code)
else:
    print("sukces")
