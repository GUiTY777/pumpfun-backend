
import asyncio
import json
import requests
import time
import threading
from flask import Flask, jsonify
import websockets

app = Flask(__name__)
CACHE_FILE = "tokens_cache.json"
RELAY_WS_URL = "wss://relay.helius.xyz/v0/transactions?api-key=0221b876-8c23-4c04-b7f2-8e542abfea66"

tokens = []

def save_tokens():
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(tokens, f, ensure_ascii=False, indent=2)

def extract_token_info(tx):
    try:
        for event in tx.get("events", []):
            if event.get("type") == "initializeMint":
                info = event.get("info", {})
                token = {
                    "mint": info.get("mint"),
                    "decimals": info.get("decimals"),
                    "mintAuthority": info.get("mintAuthority"),
                    "freezeAuthority": info.get("freezeAuthority"),
                }
                return token
    except Exception as e:
        print("Ошибка при извлечении токена:", e)
    return None

async def ws_listener():
    global tokens
    async with websockets.connect(RELAY_WS_URL) as ws:
        print("🔌 Подключено к Relay WebSocket")

        # Пример подписки без фильтра, получаем все события
        await ws.send(json.dumps({
            "type": "subscribe",
            "accounts": [],
            "commitment": "confirmed"
        }))

        while True:
            try:
                msg = await ws.recv()
                data = json.loads(msg)

                print("📥 Пришло событие:", json.dumps(data, indent=2))

                token = extract_token_info(data)
                if token and token not in tokens:
                    tokens.append(token)
                    print("🪙 Новый токен:", token)
                    save_tokens()

            except Exception as e:
                print("Ошибка WebSocket:", e)
                time.sleep(5)

def start_ws_listener():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(ws_listener())

@app.route("/tokens")
def get_tokens():
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        data = []
    return jsonify(data)

if __name__ == "__main__":
    threading.Thread(target=start_ws_listener, daemon=True).start()
    app.run(host="0.0.0.0", port=8080)
