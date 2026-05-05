#include <Arduino.h>

#define BAUD_RATE 500000


// ADC AYARLARI
// 16MHz / 32 prescaler = 500 kHz ADC Clock
// 1 çevrim ~13 clock sürer => ~38461 Hz Örnekleme Hızı
const uint32_t SAMPLE_RATE = 38462;
const uint32_t DURATION_SEC = 7;
const uint32_t TOTAL_SAMPLES = SAMPLE_RATE * DURATION_SEC;       //269234 yaklaşık sample


// RING BUFFER 
// Uno'nun RAM'i (2KB). 512-1024 byte buffer iyi
// Baud rate 500k (50kB/s) > Veri hızı 38k (38kB/s) olduğu için buffer taşmaz
#define BUFFER_SIZE 600 

volatile uint8_t ringBuffer[BUFFER_SIZE];         //volatile : değişken ISR (interrupt) veya donanım tarafından değiştirilebilir, optimize etmemek için
volatile uint16_t head = 0;
volatile uint16_t tail = 0;
volatile uint32_t samplesCounter = 0;
volatile bool capturing = false;

// ADC KESMESİ (INTERRUPT)
// Her ADC okuması bittiğinde bu fonksiyon otomatik çalışır
// Ana döngü ne yaparsa yapsın, burası kaydı durdurmaz
ISR(ADC_vect) {                                                           //Interrupt Service Routine , ADC Vector
  if (!capturing) return;

  // 1. Veriyi oku
  uint8_t val = ADCH;     //8 bit sample verir                            //ADC Data Register High

  // 2. Buffer'a yaz
  uint16_t nextHead = (head + 1);
  if (nextHead >= BUFFER_SIZE) nextHead = 0;

  // Eğer buffer dolmadıysa yaz (Dolarsa veri mecburen atılır ama hız kaymaz, cızırtı olur)
  if (nextHead != tail) {
    ringBuffer[head] = val;
    head = nextHead;
  }

  // 3. Sayaç kontrolü
  samplesCounter++;
  if (samplesCounter >= TOTAL_SAMPLES) {
    capturing = false;
    // ADC Interrupt'ı kapat
    ADCSRA &= ~(1 << ADIE);                                               //ADC Control and Status Register A , ADC Interrupt Enable
  }
}

void start_adc() {                                                                       //interruptlı çalışıyo
  // A0 Pini Giriş
  ADMUX = (1 << REFS0) | (1 << ADLAR); // AVcc ref, 8-bit (Left Adjust), A0             //ADC Multiplexer Selection Register
  
  // ADC Ayarları: ADC Enable, Auto Trigger Enable, ADC Interrupt Enable, Prescaler 32(son ikisi)
  // ADPS2=1, ADPS0=1 => /32
  ADCSRA = (1 << ADEN) | (1 << ADATE) | (1 << ADIE) | (1 << ADPS2) | (1 << ADPS0);       //ADC Control and Status Register A
  
  // Free Running Mode (trigger kaynağı/Sürekli okuma)
  ADCSRB = 0; 
  
  // İlk okumayı başlat
  ADCSRA |= (1 << ADSC);                  //ADC Start Conversion
}


//Veri transferi
void send_header() {
  Serial.write("RAW8\n");                                        //veri formatını bildirdik pcye
  // SR gönderdik (4 byte)
  Serial.write((uint8_t *)&SAMPLE_RATE, 4);                    
  // N gönderdik (4 byte)
  Serial.write((uint8_t *)&TOTAL_SAMPLES, 4);                   
}

void setup() {
  Serial.begin(BAUD_RATE);
  
  // A0 pinini hazırla
  pinMode(A0, INPUT);
}

void loop() {
  // PC'den 'S' komutu bekle
  if (!capturing && Serial.available() > 0) {                        //Kayıt aktif değilse ve Seri porttan veri geldiyse
    char c = Serial.read();
    if (c == 'S') {                                                  //PC tarafı S  gönderecek
      // Bufferları sıfırla (Önceki kayıt sil)
      head = 0;
      tail = 0;
      samplesCounter = 0;
      
      // Header gönder
      send_header();
      
      // Kaydı başlat (Interrupt devreye girer)
      capturing = true;
      start_adc();
    }
  }

  // Ana döngü: Buffer'da veri varsa PC'ye gönder
  // (Interrupt arkadan doldururken biz buradan boşaltıyoruz)
  if (head != tail) {                                                           //== ise buffer boş
    // Ne kadar veri birikmiş?
    int availableData;
    if (head >= tail) availableData = head - tail;
    else              availableData = BUFFER_SIZE - tail;

    // Tek seferde Serial buffer'ı kadar gönderelim (32 byte ≈ 0.8 ms ses)
    if (availableData > 32) availableData = 32; 

    Serial.write((uint8_t*)&ringBuffer[tail], availableData);                 //tail’dan itibaren, availableData kadar byte, Ham 8-bit audio gönderdik

    tail += availableData;
    if (tail >= BUFFER_SIZE) tail = 0;
  }
}