# Kripto Bot — Kurulum

> ⚠️ **Yatırım tavsiyesi değildir.** Burada yer alan bilgi ve ayarlar yatırım danışmanlığı kapsamında
> değildir. Kâr garantisi yoktur, paranın tamamını kaybedebilirsin. İşlem tutarı, kâr hedefi ve
> **stop-loss oranlarını kendi risk durumuna göre kendin belirle.** Ayrıntılar: [README.md](README.md)

## 1. Python paketleri
Klasörde komut satırı (cmd) aç:
```
pip install -r requirements.txt
```

## 2. Borsa API anahtarı (Binance örneği)
Binance → Profil → API Yönetimi → Yeni API oluştur.
- **Yalnızca "Spot işlem" iznini aç.**
- **"Para çekme" iznini KESİNLİKLE açma.**
- Mümkünse IP kısıtlaması koy (kendi IP adresin).

## 3. Telegram botu
1. Telegram'da **@BotFather**'a yaz → `/newbot` → isim ver → sana **token** verir.
2. Yeni botuna herhangi bir mesaj at ("merhaba").
3. Tarayıcıda aç: `https://api.telegram.org/bot<TOKEN>/getUpdates`
   → çıkan yazıda `"chat":{"id":123456789` kısmındaki sayı senin **chat id**'n.

## 4. Ayarlar
`.env.example` dosyasını kopyala, adını `.env` yap, içini doldur.
Önemli ayarlar:
- `TRADE_USDT` — her alımda kullanılacak USDT (Binance'te en küçük emir 5 USDT; bot en az 6 ister)
- `TAKE_PROFIT_PCT` — alış fiyatından % kaç yükselirse satılır
- `STOP_LOSS_PCT` — giriş fiyatından % kaç düşerse zararına satılır (`0` = kapalı)
- Satıştan sonra fiyat son satış fiyatının altına düşünce tekrar alınır
- `MAX_DAILY_LOSS_USDT` — gün içinde bu kadar zarar edilirse o gün yeni alım yapılmaz
- `PAPER=true` yaparsan gerçek emir göndermeden dener

## 5. Çalıştır
```
python bot.py
```
Durdurmak için `Ctrl+C`.

## 6. Telegram'dan yönetme
Bot açıldığında **bekleme** modundadır; alım yapmaz. Telegram'dan botuna yaz:
- `/baslat` — alım-satımı başlatır
- `/durdur` — yeni alımları durdurur (açık pozisyon hedef fiyatta yine satılır)
- `/durum` — fiyat, açık pozisyon, günlük kâr/zarar ve bakiye

Komutlar yalnızca `TELEGRAM_CHAT_ID`'deki kişiden kabul edilir. `python bot.py` bilgisayarda çalışmıyorsa
Telegram komutlarına cevap gelmez.

## Bilmen gerekenler
- Stop-loss'u **bot** takip ediyor (30 saniyede bir). Bilgisayar kapanırsa veya bot durursa stop-loss çalışmaz. Açık pozisyon `state.json`'da saklanır, bot yeniden başlayınca kaldığı yerden devam eder.
- Tüm işlemler `trades.csv`'ye, hatalar `bot.log`'a yazılır.
- Bot aynı anda tek pozisyon açar ve yalnızca spot alım yapar (kaldıraç ya da short yok).
- Strateji basit bir "%X kârda sat, son satışın altında tekrar al" döngüsü; kâr garantisi yoktur. Stop-loss kapalıyken fiyat düşerse pozisyon zararda bekler.
