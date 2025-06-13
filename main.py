
import asyncio
import json
import requests
import time
import threading
from flask import Flask, jsonify
import websockets

app = Flask(__name__)
CACHE_FILE = "tokens_cache.json"
API_KEY = "0221b876-8c23-4c04-b7f2-8e542abfea66"
WS_URL = f"wss://rpc.helius.xyz/?api-key={API_KEY}"
RPC_URL = f"https://mainnet.helius-rpc.com/?api-key={API_KEY}"

tokens = []

def save_tokens():
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(tokens, f, ensure_ascii=False, indent=2)

def get_transaction(signature):
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTransaction",
        "params": [signature, {"encoding": "jsonParsed"}]
    }
    try:
        res = requests.post(RPC_URL, json=body, timeout=10)
        return res.json().get("result")
    except Exception as e:
        print("Ошибка getTransaction:", e)
        return None

def extract_token_info(tx):
    token_infos = []
    if not tx:
        return token_infos
    instructions = tx.get("transaction", {}).get("message", {}).get("instructions", [])
    for ix in instructions:
        if ix.get("program") == "spl-token" and ix.get("parsed", {}).get("type") == "initializeMint":
            info = ix["parsed"]["info"]
            token_infos.append({
                "mint": ix.get("accounts", [None])[0],
                "decimals": info.get("decimals"),
                "mintAuthority": info.get("mintAuthority"),
                "freezeAuthority": info.get("freezeAuthority")
            })
    return token_infos

async def ws_listener():
    global tokens
    async with websockets.connect(WS_URL) as ws:
        print("🔌 Подключено к WebSocket (transactionSubscribe)")

        await ws.send(json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "transactionSubscribe",
            "params": [
                {
                    "mentions": ["TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"]
                },
                {
                    "encoding": "jsonParsed",
                    "commitment": "confirmed"
                }
            ]
        }))

        while True:
            try:
                msg = await ws.recv()
                data = json.loads(msg)

                tx = data.get("params", {}).get("result", {}).get("transaction", {})
                logs = data.get("params", {}).get("result", {}).get("meta", {}).get("logMessages", [])
                signature = data.get("params", {}).get("result", {}).get("transaction", {}).get("signatures", [""])[0]

                print("📥 logs:", logs)

                if any("Program log: Instruction: InitializeMint" in log for log in logs):
                    print(f"🔍 Токен найден: {signature}")
                    tx_data = {
                        "transaction": tx,
                        "meta": data.get("params", {}).get("result", {}).get("meta", {})
                    }
                    new_tokens = extract_token_info(tx_data)
                    for t in new_tokens:
                        if t not in tokens:
                            tokens.append(t)
                            print("🪙 Новый токен:", t)
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
