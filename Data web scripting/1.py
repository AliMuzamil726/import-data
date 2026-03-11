import requests
from bs4 import BeautifulSoup

url = "http://18.232.68.152/index"
response = requests.get(url)
soup = BeautifulSoup(response.text, "html.parser")

# Extract all paragraph texts
for p in soup.find_all("p"):
    print(p.text)
