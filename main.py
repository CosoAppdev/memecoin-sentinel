import os
import requests
import json
import time
import threading
from flask import Flask

# --- MICRO SERVER HTTP PER RENDER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "MemeSentinel Bot è attivo e in esecuzione!"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- CONFIGURAZIONE BOT ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

DEXSCREENER_SOLANA_URL = "https://api.dexscreener.com/latest/dex/search?q=SOL"
RUGCHECK_API_URL = "https://api.rugcheck.xyz/v1/tokens/{mint}/report/summary"

MIN_LIQUIDITY_USD = 5000.0
MAX_SINGLE_HOLDER_PCT = 3.5
MIN_VOLUME_MCAP_RATIO = 0.8

def send_telegram_alert(message, token_address=None):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Errore: Credenziali Telegram mancanti nelle Environment Variables!")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False
    }

    if token_address:
        reply_markup = {
            "inline_keyboard": [
                [
                    {
                        "text": "⚡ Compra su Trojan", 
                        "url": f"https://t.me/solana_trojanbot?start=r-socio-{token_address}"
                    },
                    {
                        "text": "🪐 Compra su Jupiter", 
                        "url": f"https://jup.ag/swap/SOL-{token_address}"
                    }
                ],
                [
                    {
                        "text": "📊 DEXScreener", 
                        "url": f"https://dexscreener.com/solana/{token_address}"
                    },
                    {
                        "text": "🛡️ RugCheck", 
                        "url": f"https://rugcheck.xyz/tokens/{token_address}"
                    }
                ]
            ]
        }
        payload["reply_markup"] = json.dumps(reply_markup)

    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            print(f"Errore invio Telegram: {response.text}")
    except Exception as e:
        print(f"Eccezione durante l'invio su Telegram: {e}")

def check_rugcheck_safety(mint_address):
    try:
        url = RUGCHECK_API_URL.format(mint=mint_address)
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            risks = data.get("risks", [])
            for risk in risks:
                if risk.get("name") == "Single holder ownership" and float(risk.get("value", 0)) > MAX_SINGLE_HOLDER_PCT:
                    return False, f"Holder troppo concentrato: {risk.get('value')}%"
            score = data.get("score", 0)
            if score > 2000:
                return False, f"RugCheck High Risk Score: {score}"
            return True, "Safe"
        return True, "RugCheck No Data"
    except Exception as e:
        return True, f"Bypassed (Error API): {e}"

def process_solana_pairs(seen_pairs):
    try:
        res = requests.get(DEXSCREENER_SOLANA_URL, timeout=10)
        if res.status_code != 200:
            return
        
        pairs = res.json().get("pairs", [])
        for pair in pairs:
            if pair.get("chainId") != "solana":
                continue
                
            pair_address = pair.get("pairAddress")
            if pair_address in seen_pairs:
                continue
            
            seen_pairs.add(pair_address)
            
            base_token = pair.get("baseToken", {})
            mint_address = base_token.get("address")
            symbol = base_token.get("symbol", "N/A")
            liquidity = float(pair.get("liquidity", {}).get("usd", 0))
            fdv = float(pair.get("fdv", 0))
            volume_24h = float(pair.get("volume", {}).get("h24", 0))
            url_dex = pair.get("url", "")

            if liquidity < MIN_LIQUIDITY_USD:
                continue

            if fdv > 0 and (volume_24h / fdv) < MIN_VOLUME_MCAP_RATIO:
                continue

            is_safe, reason = check_rugcheck_safety(mint_address)
            if not is_safe:
                print(f"Scartato {symbol} per: {reason}")
                continue

            msg = (
                f"🚨 *MEMECOIN SOLANA RILEVATA* 🚨\n\n"
                f"**Token:** `{symbol}`\n"
                f"**Mint:** `{mint_address}`\n"
                f"**Liquidità:** ${liquidity:,.2f}\n"
                f"**FDV (MCap):** ${fdv:,.2f}\n"
                f"**Volume 24h:** ${volume_24h:,.2f}\n\n"
                f"🔗 [Apri su DEXScreener]({url_dex})\n"
                f"🛡️ [Verifica su RugCheck](https://rugcheck.xyz/tokens/{mint_address})"
            )
            send_telegram_alert(msg, token_address=mint_address)

    except Exception as e:
        print(f"Errore ciclo di scansione: {e}")

def bot_loop():
    print("MemeSentinel Bot avviato su Solana...")
    
    # --- MESSAGGIO DI TEST ALL'AVVIO ---
    send_telegram_alert("🟢 *MemeSentinel Bot ONLINE!* \n\nIl server è avviato ed è in ascolto sui nuovi lanci Solana.")
    
    seen_pairs = set()
    while True:
        process_solana_pairs(seen_pairs)
        time.sleep(20)

if __name__ == "__main__":
    # Avvia lo scanner in background
    t = threading.Thread(target=bot_loop)
    t.daemon = True
    t.start()
    
    # Avvia il server web richiesto da Render
    run_web_server()
