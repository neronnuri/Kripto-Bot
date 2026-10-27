"""
Basit kripto al-sat botu
- Strateji: al → fiyat alış fiyatının %TAKE_PROFIT_PCT üstüne çıkınca sat →
  fiyat son satış fiyatının altına düşünce tekrar al (ilk alım hemen yapılır)
- Aynı anda tek pozisyon, tek kripto (SYMBOL)
- İsteğe bağlı stop-loss (STOP_LOSS_PCT=0 ise kapalı); stop-loss sonrası SL_COOLDOWN_MIN dakika alım yapılmaz
- Alım tutarı: en fazla TRADE_USDT, spot bakiye daha azsa bakiyenin tamamı
- Günlük zarar limiti (aşılırsa o gün yeni alım yapılmaz)
- Telegram: her işlem anında + her gün belirlenen saatte özet
- Telegram komutları: /baslat, /durdur, /durum, /hedef <fiyat> (yalnızca TELEGRAM_CHAT_ID'den gelenler)
"""
import os, re, time, json, csv, logging, socket
from datetime import datetime
from zoneinfo import ZoneInfo

import ccxt
import requests
from dotenv import load_dotenv

load_dotenv()
E = os.getenv

EXCHANGE = E("EXCHANGE", "binance")
SYMBOL = E("SYMBOL", "BTC/USDT")
TRADE_USDT = float(E("TRADE_USDT", "6"))
SL_PCT = float(E("STOP_LOSS_PCT", "0")) / 100
TP_PCT = float(E("TAKE_PROFIT_PCT", "1")) / 100
MAX_DAILY_LOSS = float(E("MAX_DAILY_LOSS_USDT", "10"))
SL_COOLDOWN = float(E("SL_COOLDOWN_MIN", "30")) * 60
PAPER = E("PAPER", "false").lower() == "true"
TG_TOKEN, TG_CHAT = E("TELEGRAM_TOKEN"), E("TELEGRAM_CHAT_ID")
REPORT_HOUR = int(E("DAILY_REPORT_HOUR", "23"))
TZ = ZoneInfo(E("TIMEZONE", "Europe/Istanbul"))
CHECK_SECONDS = 30
FEE = 0.001  # yalnızca simülasyonda kullanılır
MODE_TXT = "SİMÜLASYON" if PAPER else f"{EXCHANGE.capitalize()} Hesabı"

DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(DIR, "state.json")
TRADES_FILE = os.path.join(DIR, "trades.csv")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(os.path.join(DIR, "bot.log"), encoding="utf-8"),
              logging.StreamHandler()],
)
log = logging.getLogger("bot")

exchange = getattr(ccxt, EXCHANGE)({
    # simülasyonda anahtar gerekmez; geçersiz anahtar gönderilirse borsa hata verir
    "apiKey": None if PAPER else E("API_KEY"),
    "secret": None if PAPER else E("API_SECRET"),
    "enableRateLimit": True,
})


# ---------- yardımcılar ----------
def tg(text):
    log.info("TG: %s", text.replace("\n", " | "))
    if not (TG_TOKEN and TG_CHAT):
        return
    try:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                      data={"chat_id": TG_CHAT, "text": text}, timeout=10)
    except Exception as e:
        log.warning("Telegram gönderilemedi: %s", e)


tg_offset = None


def tg_wait(seconds):
    """Telegram'dan gelen komutları en fazla `seconds` saniye bekler, metinlerini döndürür."""
    global tg_offset
    if not (TG_TOKEN and TG_CHAT):
        time.sleep(seconds)
        return []
    params = {"timeout": seconds, "allowed_updates": '["message"]'}
    if tg_offset is None:
        params = {"offset": -1}  # ilk çağrı: bot kapalıyken gelen eski komutları atla
    else:
        params["offset"] = tg_offset
    try:
        r = requests.get(f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates",
                         params=params, timeout=seconds + 10).json()
    except Exception as e:
        log.warning("Telegram okunamadı: %s", e)
        time.sleep(seconds)
        return []
    updates = r.get("result", [])
    first = tg_offset is None
    tg_offset = updates[-1]["update_id"] + 1 if updates else (tg_offset or 0)
    if first:
        return []
    return [u["message"].get("text", "") for u in updates
            if "message" in u and str(u["message"]["chat"]["id"]) == str(TG_CHAT)]


def tg_set_commands():
    if not TG_TOKEN:
        return
    cmds = [{"command": "baslat", "description": "Alım-satımı başlat"},
            {"command": "durdur", "description": "Yeni alımları durdur"},
            {"command": "durum", "description": "Pozisyon, fiyat ve kâr durumu"},
            {"command": "hedef", "description": "Açık pozisyonun satış hedefini değiştir: /hedef 82500"}]
    try:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/setMyCommands",
                      json={"commands": cmds}, timeout=10)
    except Exception as e:
        log.warning("Telegram komutları ayarlanamadı: %s", e)


def load_state():
    s = {"position": None, "last_sell": None, "dust": 0.0, "last_report": "", "active": False,
         "cooldown_until": 0}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            s.update(json.load(f))
    return s


def save_state(s):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)


def record(side, price, amount, usdt, pnl, reason):
    new = not os.path.exists(TRADES_FILE)
    with open(TRADES_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time", "side", "price", "amount", "usdt", "pnl", "reason"])
        w.writerow([datetime.now(TZ).isoformat(timespec="seconds"), side,
                    round(price, 6), amount, round(usdt, 4), round(pnl, 4), reason])


def today_trades():
    if not os.path.exists(TRADES_FILE):
        return []
    today = datetime.now(TZ).date().isoformat()
    with open(TRADES_FILE, encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r["time"].startswith(today)]


def today_pnl():
    return sum(float(r["pnl"]) for r in today_trades())


# ---------- işlemler ----------
def buy(state, price, reason):
    if PAPER:
        cost = TRADE_USDT
        amount, entry = cost * (1 - FEE) / price, price
    else:
        quote = SYMBOL.split("/")[1]
        free = float(exchange.fetch_balance()["free"].get(quote, 0) or 0)
        spend = min(TRADE_USDT, free * 0.995)
        if spend < MIN_COST * 1.2:
            raise RuntimeError(f"Spot {quote} bakiyesi yetersiz: {free:.2f} (en az {MIN_COST * 1.2:g} gerekli)")
        if exchange.has.get("createMarketBuyOrderWithCost"):
            o = exchange.create_market_buy_order_with_cost(SYMBOL, spend)
        else:
            amt = float(exchange.amount_to_precision(SYMBOL, spend / price))
            o = exchange.create_market_buy_order(SYMBOL, amt)
        amount = float(o.get("filled") or o.get("amount"))
        fee = o.get("fee") or {}
        if fee.get("currency") == SYMBOL.split("/")[0]:  # komisyon coin'den kesildiyse
            amount -= float(fee.get("cost") or 0)
        entry = float(o.get("average") or price)
        cost = float(o.get("cost") or spend)  # borsa miktarı yuvarladığı için harcanan, istenenden az olabilir
    state["position"] = {
        "amount": amount, "entry": entry, "cost": cost,
        "sl": entry * (1 - SL_PCT) if SL_PCT > 0 else None,
        "tp": entry * (1 + TP_PCT),
        "time": datetime.now(TZ).isoformat(timespec="seconds"),
    }
    record("BUY", entry, amount, cost, 0, reason)
    p = state["position"]
    sl_txt = f"{p['sl']:.2f}" if p["sl"] else "kapalı"
    tg(f"🟢 ALIM {SYMBOL} ({reason})\nFiyat: {entry:.2f}\nMiktar: {amount:.8f} ({cost:.2f} USDT)\n"
       f"Satış hedefi (+%{TP_PCT*100:g}): {p['tp']:.2f}\nStop-loss: {sl_txt}"
       + ("\n(SİMÜLASYON)" if PAPER else ""))


def sell(state, price, reason):
    pos = state["position"]
    if PAPER:
        amount, proceeds = pos["amount"], pos["amount"] * price * (1 - FEE)
    else:
        # borsa miktarı adımlara yuvarlar; satılamayan küsurat (dust) bir sonraki satışa eklenir.
        # Bot yalnızca kendi aldığı miktarı satar, hesaptaki diğer coin'lere dokunmaz.
        base = SYMBOL.split("/")[0]
        want = pos["amount"] + state["dust"]
        free = float(exchange.fetch_balance()["free"].get(base, 0) or 0)
        amount = float(exchange.amount_to_precision(SYMBOL, min(want, free)))
        o = exchange.create_market_sell_order(SYMBOL, amount)
        state["dust"] = max(want - amount, 0.0)
        price = float(o.get("average") or price)
        proceeds = float(o.get("cost") or amount * price)
        fee = o.get("fee") or {}
        if fee.get("currency") == SYMBOL.split("/")[1]:
            proceeds -= float(fee.get("cost") or 0)
    pnl = proceeds - amount * pos["cost"] / pos["amount"]
    record("SELL", price, amount, proceeds, pnl, reason)
    state["position"] = None
    state["last_sell"] = price
    next_txt = f"Sonraki alım: fiyat {price:.2f} altına düşünce"
    if reason == "STOP-LOSS" and SL_COOLDOWN > 0:
        state["cooldown_until"] = time.time() + SL_COOLDOWN
        next_txt += f" ({SL_COOLDOWN / 60:g} dk bekledikten sonra)"
    icon = "✅" if pnl >= 0 else "🔴"
    tg(f"{icon} SATIŞ {SYMBOL} ({reason})\nGiriş: {pos['entry']:.2f} → Çıkış: {price:.2f}\n"
       f"Kâr/Zarar: {pnl:+.4f} USDT\nBugün toplam: {today_pnl():+.4f} USDT\n"
       + next_txt + ("\n(SİMÜLASYON)" if PAPER else ""))


def daily_report():
    rows = today_trades()
    sells = [r for r in rows if r["side"] == "SELL"]
    total = sum(float(r["pnl"]) for r in sells)
    wins = sum(1 for r in sells if float(r["pnl"]) > 0)
    lines = [f"📊 Günlük rapor {datetime.now(TZ):%d.%m.%Y} — {SYMBOL}",
             f"İşlem: {len(rows)} (alım {len(rows) - len(sells)}, satış {len(sells)})",
             f"Kazanan/kaybeden: {wins}/{len(sells) - wins}",
             f"Net kâr/zarar: {total:+.4f} USDT", ""]
    for r in rows:
        pnl_txt = "" if r["side"] == "BUY" else f"{float(r['pnl']):+.4f}"
        lines.append(f"{r['time'][11:16]} {r['side']} {float(r['price']):.2f} {pnl_txt} {r['reason']}")
    if not rows:
        lines.append("Bugün işlem yapılmadı.")
    tg("\n".join(lines))


def status_text(state):
    price = float(exchange.fetch_ticker(SYMBOL)["last"])
    lines = [f"ℹ️ Durum: {'▶️ çalışıyor' if state['active'] else '⏸ durduruldu'} "
             f"({MODE_TXT})",
             f"{SYMBOL} fiyatı: {price:.2f}"]
    pos = state["position"]
    if pos:
        change = (price / pos["entry"] - 1) * 100
        lines.append(f"Açık pozisyon: {pos['amount']:.8f} @ {pos['entry']:.2f} ({change:+.2f}%)\n"
                     f"Satış hedefi: {pos['tp']:.2f} | Stop-loss: "
                     + (f"{pos['sl']:.2f}" if pos.get("sl") else "kapalı"))
    elif state["last_sell"]:
        lines.append(f"Pozisyon yok. Sonraki alım: fiyat {state['last_sell']:.2f} altına düşünce")
        wait = state["cooldown_until"] - time.time()
        if wait > 0:
            lines.append(f"Stop-loss sonrası bekleme: {wait / 60:.0f} dk kaldı")
    else:
        lines.append("Pozisyon yok. Başlatılınca ilk alım hemen yapılır")
    lines.append(f"Bugün kâr/zarar: {today_pnl():+.4f} USDT")
    if not PAPER:
        base, quote = SYMBOL.split("/")
        total = exchange.fetch_balance()["total"]
        b, q = float(total.get(base, 0) or 0), float(total.get(quote, 0) or 0)
        lines.append(f"💰 {EXCHANGE.capitalize()} spot bakiyesi:\n"
                     f"{base}: {b:.8f} (≈ {b * price:.2f} {quote})\n"
                     f"{quote}: {q:.2f}\n"
                     f"Toplam: ≈ {b * price + q:.2f} {quote}")
    return "\n".join(lines)


def parse_price(txt):
    """'80720', '80.720' (binlik nokta), '80,720.5' veya '80720,5' gibi yazımları sayıya çevirir."""
    txt = txt.strip().replace("$", "")
    if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", txt):      # 80.720 veya 80.720,5
        txt = txt.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", txt):    # 80,720 veya 80,720.5
        txt = txt.replace(",", "")
    else:
        txt = txt.replace(",", ".")
    return float(txt)


def set_target(state, args):
    pos = state["position"]
    if not pos:
        tg("Açık pozisyon yok, değiştirilecek bir satış hedefi bulunmuyor.")
        return
    if not args:
        tg(f"Şu anki satış hedefi: {pos['tp']:.2f}\nDeğiştirmek için: /hedef 82500")
        return
    try:
        target = parse_price(args[0])
    except ValueError:
        tg("Fiyatı anlayamadım. Örnek: /hedef 82500")
        return
    price = float(exchange.fetch_ticker(SYMBOL)["last"])
    if not (price * 0.5 <= target <= price * 2):
        tg(f"⛔ {target:.2f} mevcut fiyattan ({price:.2f}) çok uzak, hedef değiştirilmedi.")
        return
    confirmed = len(args) > 1 and args[1].lower() in ("evet", "onay", "onayla")
    if target <= price and not confirmed:
        tg(f"⚠️ {target:.2f} şu anki fiyatın ({price:.2f}) altında: bu hedefle pozisyon HEMEN satılır"
           + (f" ve alış fiyatının ({pos['entry']:.2f}) altında olduğu için ZARARINA satılır." if target < pos["entry"] else ".")
           + f"\nYine de istiyorsan şunu yaz: /hedef {args[0]} evet")
        return
    old = pos["tp"]
    pos["tp"] = target
    change = (target / pos["entry"] - 1) * 100
    tg(f"🎯 Satış hedefi değişti: {old:.2f} → {target:.2f} (alış fiyatına göre {change:+.2f}%)\n"
       f"Şu anki fiyat: {price:.2f}")


def live_line(state, price):
    """Her kontrolde ekrana (yalnızca konsola, log dosyasına değil) tek satır durum yazar."""
    parts = [datetime.now(TZ).strftime("%H:%M:%S"),
             f"{SYMBOL.split('/')[0]} {price:,.2f}",
             "▶ çalışıyor" if state["active"] else "⏸ durdu"]
    pos = state["position"]
    if pos:
        pnl = (price / pos["entry"] - 1) * 100
        val = pos["amount"] * price - pos["cost"]
        parts.append(f"Pozisyon {pnl:+.2f}% ({val:+.3f} USDT)")
        parts.append(f"Hedef {pos['tp']:,.2f} (%{(pos['tp'] / price - 1) * 100:.2f} uzakta)")
        if pos.get("sl"):
            parts.append(f"SL {pos['sl']:,.2f} (%{(1 - pos['sl'] / price) * 100:.2f} uzakta)")
    elif state["last_sell"]:
        parts.append(f"Pozisyon yok, alım için fiyat < {state['last_sell']:,.2f} olmalı")
        wait = state["cooldown_until"] - time.time()
        if wait > 0:
            parts.append(f"bekleme {wait / 60:.0f} dk")
    else:
        parts.append("Pozisyon yok")
    print(" | ".join(parts), flush=True)


def handle_command(state, text):
    parts = text.split()
    cmd = (parts or [""])[0].split("@")[0].lower()
    if cmd == "/hedef":
        set_target(state, parts[1:])
    elif cmd == "/baslat":
        state["active"] = True
        tg("▶️ Alım-satım başladı.")
    elif cmd == "/durdur":
        state["active"] = False
        tg("⏸ Durduruldu. Yeni alım yapılmayacak; açık pozisyon varsa hedef fiyatta yine satılır.")
    elif cmd == "/durum":
        tg(status_text(state))
    else:
        tg("Komutlar:\n/baslat — alım-satımı başlat\n/durdur — yeni alımları durdur\n/durum — durumu göster\n/hedef 82500 — satış hedefini değiştir")
    save_state(state)


MIN_COST = 0.0


def check_min_order():
    global MIN_COST
    exchange.load_markets()
    min_cost = MIN_COST = (exchange.market(SYMBOL)["limits"].get("cost") or {}).get("min") or 0
    # satışta komisyon ve miktar yuvarlaması düşüldükten sonra da limitin üstünde kalmalı
    if TRADE_USDT < min_cost * 1.2:
        msg = (f"⛔ TRADE_USDT={TRADE_USDT:g} çok düşük. {EXCHANGE} {SYMBOL} için en küçük emir "
               f"{min_cost:g} USDT; güvenli olması için TRADE_USDT en az {min_cost * 1.2:g} olmalı.")
        tg(msg)
        raise SystemExit(msg)


LOCK_PORT = 47653
_lock = None


def single_instance():
    """Aynı anda iki bot çalışıp çift alım yapmasın diye yerel bir port kilitlenir."""
    global _lock
    _lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        _lock.bind(("127.0.0.1", LOCK_PORT))
    except OSError:
        msg = "⛔ Bot zaten çalışıyor; ikinci kopya kapatıldı."
        tg(msg)
        raise SystemExit(msg)


# ---------- ana döngü ----------
def main():
    single_instance()
    state = load_state()
    while True:  # bilgisayar yeni açıldıysa internet gelene kadar bekle
        try:
            check_min_order()
            break
        except (ccxt.NetworkError, requests.RequestException) as e:
            log.warning("Borsaya bağlanılamadı, 30 sn sonra tekrar: %s", e)
            time.sleep(30)
    tg_set_commands()
    tg_wait(0)  # bot kapalıyken gelen eski komutları atla
    tg(f"🤖 Bot açıldı ({MODE_TXT})\n{SYMBOL} | "
       f"işlem başı {TRADE_USDT:g} USDT | %{TP_PCT*100:g} kârda sat | "
       f"son satışın altına düşünce al | SL {'%' + format(SL_PCT*100, 'g') if SL_PCT else 'kapalı'} | "
       f"günlük zarar limiti {MAX_DAILY_LOSS:g} USDT\n"
       + ("Durum: ▶️ çalışıyor (durdurmak için /durdur)" if state["active"]
          else "Durum: ⏸ bekliyor — başlatmak için /baslat"))
    last_err = 0
    while True:
        try:
            price = float(exchange.fetch_ticker(SYMBOL)["last"])
            pos = state["position"]
            if pos:
                if price >= pos["tp"]:
                    sell(state, price, "TAKE-PROFIT")
                elif pos.get("sl") and price <= pos["sl"]:
                    sell(state, price, "STOP-LOSS")
            elif state["active"] and time.time() >= state["cooldown_until"]:
                last = state["last_sell"]
                if last is None or price < last:
                    if MAX_DAILY_LOSS > 0 and today_pnl() <= -MAX_DAILY_LOSS:
                        log.info("Günlük zarar limiti doldu, alım atlandı.")
                    else:
                        buy(state, price, "ilk alım" if last is None else "son satışın altında")
            live_line(state, price)

            now = datetime.now(TZ)
            if now.hour >= REPORT_HOUR and state["last_report"] != now.date().isoformat():
                daily_report()
                state["last_report"] = now.date().isoformat()
            save_state(state)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            log.exception("Hata")
            if time.time() - last_err > 3600:  # en fazla saatte bir hata mesajı
                tg(f"⚠️ Bot hatası: {e}")
                last_err = time.time()
        for text in tg_wait(CHECK_SECONDS):
            try:
                handle_command(state, text)
            except Exception as e:
                log.exception("Komut hatası")
                tg(f"⚠️ Komut çalıştırılamadı: {e}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        tg("⏹ Bot durduruldu.")
