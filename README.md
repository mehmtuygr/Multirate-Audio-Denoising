# Multirate-Audio-Denoising

Arduino (Uno/CH340) + mikrofon devresinden **yüksek örnekleme hızlı ham ses** alıp, PC tarafında **multirate sinyal işleme** (Butterworth low-pass + decimation) ile **cızırtı / beyaz gürültüyü azaltan** bir DSP projesi.

> Arduino, 8-bit ham örnekleri seri porttan gönderir. Python scripti bu veriyi alır, normalize eder, low-pass filtreden geçirir ve decimation uygulayıp WAV çıktısı üretir.

---

## İçerik (Repo Dosyaları)

- `mic_multirate.ino`  
  Arduino tarafı: ADC free-running + ISR ile örnekleme, ring buffer, seri port üzerinden ham veri aktarımı.

- `MultirateAudioDenoising.py`  
  PC tarafı: seri porttan ham veriyi çekme, WAV kaydetme, low-pass filtre + decimation.

---

## Sistem Nasıl Çalışıyor?

### 1) Arduino Tarafı (Kayıt + Aktarım)
- **Baud rate:** `500000`
- **Örnekleme:** ADC free-running mod + `ISR(ADC_vect)`  
- **Veri formatı:** 8-bit (`ADCH`, 0–255)
- **Protokol:**
  1. PC, Arduino’ya `S` karakteri gönderir (kayıt başlat).
  2. Arduino önce bir header yollar:
     - `"RAW8\n"` (magic)
     - 4 byte: sample rate (uint32, little-endian)
     - 4 byte: toplam örnek sayısı N (uint32, little-endian)
  3. Ardından **N byte** ham ses verisini yollar.


### 2) Python Tarafı (Multirate İşleme)
- Seri porttan header + ham veri okunur.
- Ham 8-bit veri `[-1, +1]` aralığına normalize edilir.
- **Butterworth low-pass** uygulanır (cutoff: **4 kHz**, order: **4**).
- **Decimation:** `DECIM_FACTOR = 10` (her 10 örnekten 1’i tutulur).
- Çıktılar:
  - `original.wav` (ham kayıt)
  - `processed_multirate.wav` (filtre + decimation sonrası)

---

## Gereksinimler

- Arduino IDE (veya PlatformIO) — `mic_multirate.ino` yüklemek için
- Python 3.9+ önerilir

Python kütüphaneleri:
- `numpy`
- `pyserial`
- `soundfile`
- `scipy`

Kurulum:
```bash
pip install numpy pyserial soundfile scipy
