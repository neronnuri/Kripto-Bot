# Kripto Bot

Binance spot hesabında BTC/USDT al-sat yapan, işlemleri Telegram'dan bildiren basit bir Python botu.

- Al → fiyat hedef yüzdeye çıkınca sat → fiyat son satışın altına düşünce tekrar al
- İsteğe bağlı stop-loss ve günlük zarar limiti
- Telegram bildirimleri ve komutları: `/baslat`, `/durdur`, `/durum`, `/hedef <fiyat>`
- `PAPER=true` ile gerçek emir göndermeden simülasyon

Kurulum adımları için: [KURULUM.md](KURULUM.md)

## ⚠️ Yasal uyarı — yatırım tavsiyesi değildir

**Burada yer alan bilgi, kod ve ayarlar yatırım danışmanlığı kapsamında değildir ve yatırım tavsiyesi
niteliği taşımaz.** Yatırım danışmanlığı hizmeti; aracı kurumlar, portföy yönetim şirketleri ve
mevduat kabul etmeyen bankalar ile müşteri arasında imzalanacak yatırım danışmanlığı sözleşmesi
çerçevesinde verilmektedir. Bu proje herhangi bir kişiye özel değildir; mali durumunuza, risk ve
getiri tercihlerinize uygun olmayabilir.

- Bu bot yalnızca **eğitim ve kişisel deneme** amacıyla paylaşılmıştır.
- Kripto paralar çok oynaktır; **yatırdığınız paranın tamamını kaybedebilirsiniz.** Kâr garantisi yoktur.
- Örnek ayarlardaki işlem tutarı, kâr hedefi (`TAKE_PROFIT_PCT`), **stop-loss oranı (`STOP_LOSS_PCT`)**
  ve günlük zarar limiti yalnızca örnektir. **Bu değerleri kendi risk durumunuza göre kendiniz belirleyin.**
- Önce `PAPER=true` (simülasyon) ile deneyin, gerçek parayla küçük tutarlardan başlayın.
- Stop-loss borsada emir olarak değil bot tarafından takip edilir; bot ya da bilgisayar kapalıyken çalışmaz.
- Yazılım "olduğu gibi" sunulur; hatalardan, kesintilerden veya oluşabilecek zararlardan geliştirici
  sorumlu tutulamaz. Botu kullanan herkes tüm sorumluluğu kabul etmiş sayılır.
- API anahtarınızda **para çekme iznini asla açmayın** ve anahtarlarınızı kimseyle paylaşmayın.

> **Not:** This project is for educational purposes only and is **not financial advice**.
> Use at your own risk; you may lose all funds you trade with.
