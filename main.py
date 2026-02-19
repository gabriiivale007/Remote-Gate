import machine
import time
from lib import cc1101
import json

class GateCloner:
    def __init__(self, spi_bus, cs_pin, data_pin):
        # Inizializzazione hardware
        self.spi = spi_bus
        self.cs = machine.Pin(cs_pin, machine.Pin.OUT, value=1)
        self.data_pin = machine.Pin(data_pin, machine.Pin.IN) # GDO0
        self.radio = cc1101.CC1101(self.spi, self.cs)
        
    def setup_radio(self):
        """Configura la radio per 433.92MHz OOK"""
        self.radio.set_base_frequency_hertz(433920000)
        self.radio.set_modulation_format(cc1101.ModulationFormat.ASK_OOK)
        self.radio.set_symbol_rate_baud(2400)
        # GDO0 deve riflettere lo stato della portante (TX/RX)
        self.radio._write_reg(0x02, 0x0D) 
        print("Radio configurata su 433.92MHz")

    def sniff(self, timeout_ms=5000):
        """Rileva e cattura i timing del segnale"""
        print(f"In ascolto per {timeout_ms/1000} secondi...")
        start_wait = time.ticks_ms()
        
        # Aspetta segnale alto
        while self.data_pin.value() == 0:
            if time.ticks_diff(time.ticks_ms(), start_wait) > timeout_ms:
                print("Timeout: nessun segnale rilevato.")
                return None
        
        durations = []
        last_tick = time.ticks_us()
        current_state = 1
        
        # Cattura per 600ms (abbastanza per catturare più frame del telecomando)
        capture_start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), capture_start) < 600:
            val = self.data_pin.value()
            if val != current_state:
                now = time.ticks_us()
                durations.append(time.ticks_diff(now, last_tick))
                last_tick = now
                current_state = val
        
        print(f"Segnale catturato! {len(durations)} impulsi.")
        return durations

    def save_to_file(self, data, filename):
        """Salva i timing in formato JSON"""
        try:
            with open(filename, "w") as f:
                json.dump(data, f)
            print(f"Dati salvati in: {filename}")
        except Exception as e:
            print(f"Errore nel salvataggio: {e}")

    def play(self, filename):
        """Legge il file e riproduce il segnale"""
        try:
            with open(filename, "r") as f:
                durations = json.load(f)
            
            print(f"Riproduzione di {filename}...")
            # Configura il pin come uscita per trasmettere
            tx_pin = machine.Pin(4, machine.Pin.OUT)
            
            # Metti la radio in modalità TX
            self.radio._write_reg(0x35, 0x00) # STX command
            
            # Riproduce la sequenza di impulsi
            state = True
            for d in durations:
                tx_pin.value(1 if state else 0)
                time.sleep_us(d)
                state = not state
            
            tx_pin.value(0)
            self.radio._write_reg(0x36, 0x00) # SIDLE (stop TX)
            print("Riproduzione completata.")
            
            # Ritorna in modalità input
            self.data_pin = machine.Pin(4, machine.Pin.IN)
        except Exception as e:
            print(f"Errore nella riproduzione: {e}")

# --- ESEMPIO DI UTILIZZO ---

# Configura SPI come da tua tabella
spi = machine.SPI(1, baudrate=1000000, sck=machine.Pin(12), mosi=machine.Pin(11), miso=machine.Pin(13))

# Crea l'oggetto (CS=10, GDO0=4)
cloner = GateCloner(spi, 10, 4)
cloner.setup_radio()

# 1. SNIFF E SALVA
segnale = cloner.sniff()
if segnale:
    cloner.save_to_file(segnale, "cancello_casa.json")

# 2. RIPRODUCI (Scommenta sotto per testare l'apertura)
# time.sleep(2)
# cloner.play("cancello_casa.json")