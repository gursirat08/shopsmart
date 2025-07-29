import random
import serpapi

SERPAPI_KEY = "83557b4f077c56b9d2907ec15415d99dbb59e030bd0cf6e11a8785c337770188"


# Fallback class to simulate GoogleSearch (for older versions)
class GoogleSearch:

    def __init__(self, params):
        self.params = params

    def get_dict(self):
        return serpapi.search(self.params)


#  Extract price
def extract_price(item):
    if item.get("price"):
        return item["price"], False
    if "extracted_price" in item:
        return f"₹{item['extracted_price']}", False
    if "extensions" in item:
        for ext in item["extensions"]:
            if "₹" in ext:
                return ext, False
    return f"₹{random.randint(4000, 90000)}", True


#  Search Amazon
def search_amazon(product_name):
    params = {
        "engine": "google",
        "q": f"{product_name} site:amazon.in",
        "api_key": SERPAPI_KEY
    }

    search = GoogleSearch(params)
    results = search.get_dict()
    print("🔍 Amazon RAW:", results)

    products = []
    for item in results.get("shopping_results", []) + results.get(
            "organic_results", []):
        price, estimated = extract_price(item)
        products.append({
            "title": item.get("title", "No title"),
            "price": price,
            "estimated": estimated,
            "link": item.get("link", "#"),
            "source": "Amazon"
        })

    return products


# Search Flipkart
def search_flipkart(product_name):
    params = {
        "engine": "google",
        "q": f"{product_name} site:flipkart.com",
        "api_key": SERPAPI_KEY
    }

    search = GoogleSearch(params)
    results = search.get_dict()
    print("🔍 Flipkart RAW:", results)

    products = []
    for item in results.get("shopping_results", []) + results.get(
            "organic_results", []):
        price, estimated = extract_price(item)
        products.append({
            "title": item.get("title", "No title"),
            "price": price,
            "estimated": estimated,
            "link": item.get("link", "#"),
            "source": "Flipkart"
        })

    return products
