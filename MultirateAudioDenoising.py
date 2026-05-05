import time
import struct
from pathlib import Path

import numpy as np
import serial
from serial.tools import list_ports
import soundfile as sf
from scipy.signal import butter, lfilter

#  AYARLAR 
DURATION_SEC = 6.0
TARGET_BAUD = 500000
SAFE_OPEN_BAUD = 9600
PORT_HINT = "CH340"    

# Multirate Ayarları
DECIM_FACTOR = 10      # 10 örnekten 1'ini alacağız
LOWPASS_CUTOFF_HZ = 4000.0
FILTER_ORDER = 4

OUT_DIR = Path(__file__).resolve().parent
ORIGINAL_WAV = OUT_DIR / "original.wav"
PROCESSED_WAV = OUT_DIR / "processed_multirate.wav"

def pick_port() -> str:
    """Otomatik port seçimi"""
    ports = list(list_ports.comports())
    if not ports:
        raise RuntimeError("Hiç COM port görünmüyor. Arduino takılı mı?")
    
    print("Bulunan Portlar:")
    for p in ports:
        print(f" - {p.device}: {p.description}")
        
    # İpucu kelimesini içeren portu ara
    for p in ports:
        desc = (p.description or "").upper()
        if PORT_HINT.upper() in desc:
            return p.device
            
    return ports[0].device

def open_serial_stable(port: str, baud: int) -> serial.Serial:
    print(f"[serial] {port} portu {baud} baud ile açılıyor...")
    # Önce güvenli hızda açıp reset atıyoruz
    s = serial.Serial(port, SAFE_OPEN_BAUD, timeout=3)
    time.sleep(2.0) # Arduino reset beklemesi
    
    try:
        s.setDTR(False)
        s.setRTS(False)
    except:
        pass
    s.reset_input_buffer()

    # Hedef hıza geçiş
    s.baudrate = baud
    time.sleep(0.1)
    s.reset_input_buffer()
    return s

def read_exact(ser: serial.Serial, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = ser.read(n - len(buf))
        if not chunk:
            break
        buf.extend(chunk)
    return bytes(buf)

def capture_from_arduino(port: str) -> tuple[np.ndarray, int]:
    ser = open_serial_stable(port, TARGET_BAUD)
    try:
        print("[capture] 'S' komutu gönderiliyor...")
        ser.write(b"S")
        ser.flush()

        # Header okuma
        magic = read_exact(ser, 5)
        if magic != b"RAW8\n":
            raise RuntimeError(f"Beklenen header gelmedi. Gelen: {magic}")

        hdr = read_exact(ser, 8) # SR(4 byte) + N(4 byte)
        if len(hdr) != 8:
            raise RuntimeError("Header eksik.")

        sr, n = struct.unpack("<II", hdr)
        duration = n / sr
        print(f"[capture] Arduino bildirdi: SR={sr} Hz, Toplam {n} byte (~{duration:.2f} sn)")
        
        start_t = time.time()
        data = read_exact(ser, n)
        elapsed = time.time() - start_t
        
        print(f"[capture] Veri alındı. Geçen süre: {elapsed:.2f} sn (Hedef: {duration:.2f} sn)")
        
        if abs(elapsed - duration) > 2.0:
            print("[UYARI] Kayıt süresi beklenenden çok farklı! Baud rate darboğazı olabilir.")

        if len(data) != n:
            print(f"[warn] Eksik veri: {len(data)}/{n}")

        u8 = np.frombuffer(data, dtype=np.uint8)
        return u8, int(sr)
    finally:
        ser.close()

def u8_to_float32(u8: np.ndarray) -> np.ndarray:
    # 0..255 -> -1.0..+1.0
    return (u8.astype(np.float32) - 128.0) / 128.0

def butter_lowpass_filter(data, cutoff, fs, order=5):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    y = lfilter(b, a, data)
    return y

def main():
    port = pick_port()
    
    # 1. KAYIT : Arduino'dan Raw veri al
    raw_u8, sr = capture_from_arduino(port)
    
    # Float dönüşümü
    x = u8_to_float32(raw_u8)
    
    # Original Dosyayı Kaydet 
    sf.write(ORIGINAL_WAV, x, sr, subtype="FLOAT")
    print(f"\n[1] Original ses kaydedildi: {ORIGINAL_WAV}")
    print(f"    SR: {sr} Hz, Örnek Sayısı: {len(x)}")

    # 2. MULTIRATE İŞLEMİ
    print("\n[2] Multirate İşlemi Başlıyor...")
    print(f"    - LowPass Filtre: {LOWPASS_CUTOFF_HZ} Hz (Butterworth)")
    print(f"    - Decimation Factor: {DECIM_FACTOR} (Her 10 örnekten 1'i)")

    # Filtrele (Gürültü azaltma)
    x_filtered = butter_lowpass_filter(x, LOWPASS_CUTOFF_HZ, sr, order=FILTER_ORDER)
    
    # Decimate (Örnek atma / Downsampling)
    y = x_filtered[::DECIM_FACTOR]
    new_sr = int(sr / DECIM_FACTOR)

    # İşlenmiş Dosyayı Kaydet
    sf.write(PROCESSED_WAV, y, new_sr, subtype="FLOAT")
    print(f"[OK] İşlem tamamlandı: {PROCESSED_WAV}")
    print(f"     Yeni SR: {new_sr} Hz")
    print(f"     Yeni Boyut: {len(y)} örnek")

if __name__ == "__main__":
    main()