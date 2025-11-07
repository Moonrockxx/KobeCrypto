import json, urllib.request
def get(url, timeout=8):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))
def main():
    base = "https://api.binance.com"
    pong = get(base + "/api/v3/ping")
    time = get(base + "/api/v3/time")
    print("ping:", pong, "serverTime:", time.get("serverTime"))
if __name__ == "__main__":
    main()
