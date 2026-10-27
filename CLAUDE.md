# Kripto Bot — proje notları

Bu dosya, projenin Claude sohbetinde (Kripto Trader projesi) nasıl kurulduğunu özetler.
Kullanıcıyla **Türkçe** konuş. Kullanıcı yazılımcı değil; adımları sade anlat.

## Ne yapıyor
Binance spot hesabında **gerçek parayla** BTC/USDT al-sat yapan basit bir Python botu.
Bilgisayarda `baslat.bat` ile çalışır (Windows Terminal'de "kripto-bot" sekmesi).

## Strateji (bot.py)
- Al → fiyat alış fiyatının `TAKE_PROFIT_PCT` üstüne çıkınca sat → fiyat son satış fiyatının altına düşünce tekrar al. İlk alım hemen yapılır.
- Aynı anda tek pozisyon. Alım tutarı en fazla `TRADE_USDT`; bakiye azsa bakiyenin tamamı.
- Stop-loss isteğe bağlı (`STOP_LOSS_PCT=0` kapalı); stop-loss sonrası `SL_COOLDOWN_MIN` dakika alım yok.
- Günlük zarar limiti `MAX_DAILY_LOSS_USDT` dolunca o gün yeni alım yok.
- Stop-loss/hedef borsada emir olarak değil, **bot tarafından** 30 sn'de bir kontrol edilir. Bot kapalıyken çalışmaz.
- Aynı anda iki bot çalışmasın diye 127.0.0.1:47653 portu kilitlenir.

## Telegram
- Her alım/satış anında, her gün `DAILY_REPORT_HOUR` (23:00) günlük özet.
- Komutlar (yalnızca `TELEGRAM_CHAT_ID`'den): `/baslat`, `/durdur`, `/durum`,
  `/hedef <fiyat>` — açık pozisyonun satış hedefini değiştirir. Hedef mevcut fiyatın altındaysa
  önce uyarır, `/hedef <fiyat> evet` ile onay ister. Fiyatın yarısından az / iki katından fazla değerler reddedilir.
  `80.720` gibi binlik noktalı yazım desteklenir.

## Ekran
Her kontrolde konsola (stderr) tek satır canlı durum yazılır: saat, fiyat, pozisyon kâr/zarar,
hedefe ve SL'ye uzaklık. Bu satırlar `bot.log`'a yazılmaz.
Not: Bu bilgisayarda `print()` ile stdout'a yazılanlar pencerede görünmedi, stderr görünüyor — konsol çıktısı için stderr kullan.

## Dosyalar
- `bot.py` — bot. `telegram_test.py` — Telegram token/chat id kurulum yardımcısı. `baslat.bat` — başlatıcı (Python 3.12).
- `.env` — API anahtarları ve ayarlar (**gizli, GitHub'a yüklenmez**, `.gitignore`'da). Şablon: `.env.example`.
- `state.json` (açık pozisyon), `trades.csv` (işlemler), `bot.log` — çalışma dosyaları, GitHub'a yüklenmez.
- GitHub: private repo `neronnuri/Kripto-Bot`, yerel klasör `Desktop\Proje 1 Trader\Kripto Bot`.
  Eski `Desktop\Proje 1 Trader\kripto-bot` klasörü artık kullanılmıyor.

## Çalışma kuralları
- Kod değişikliğinden sonra bot **yeniden başlatılmalı** (pencereyi kapat, `baslat.bat`). Açık pozisyon `state.json`'dan devam eder.
- Botu yeniden başlatmadan önce açık pozisyon olup olmadığını kontrol et; kapalı kaldığı süre kısa olsun.
- `.env` içeriğini asla okuma/yazdırma/commit etme.
- Değişiklikleri sahte bir borsa nesnesiyle test et, sonra commit + push.
- Para çekme izni olmayan, sadece spot işlem izinli API anahtarı kullanılıyor.
