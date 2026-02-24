import os
import random
import requests
import numpy as np
from pydub import AudioSegment

# CONFIGURAÇÕES DA API
API_KEY = "YOUR_FREESOUND_API_KEY_HERE"
RAIN_ID = "243628"      
THUNDER_ID = "101667"   

# DEFINIÇÃO DE DIRETÓRIOS (Para manter o workspace limpo)
# Pega o diretório exato onde este script .py está salvo
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Volta um nível (..) e entra na pasta 'assets'
ASSETS_DIR = os.path.join(SCRIPT_DIR, "..", "assets")

# Garante que a pasta assets existe antes de tentar salvar algo lá
os.makedirs(ASSETS_DIR, exist_ok=True)

# Caminhos finais dos arquivos de áudio
RAIN_PATH = os.path.join(ASSETS_DIR, "chuva.mp3")
THUNDER_PATH = os.path.join(ASSETS_DIR, "trovao.mp3")

def download_freesound(sound_id, filepath):
    print(f"[*] Buscando o sound ID {sound_id} no Freesound...")
    url = f"https://freesound.org/apiv2/sounds/{sound_id}/?token={API_KEY}"
    try:
        res = requests.get(url).json()
        download_url = res['previews']['preview-hq-mp3']
        audio_data = requests.get(download_url).content
        with open(filepath, 'wb') as f:
            f.write(audio_data)
        print(f"[OK] Salvo em: {filepath}")
    except Exception as e:
        print(f"[Erro] Falha no download: {e}")

def generate_storm_51():
    # 1. Downloads (Verifica se já existem na pasta ../assets)
    if not os.path.exists(RAIN_PATH):
        download_freesound(RAIN_ID, RAIN_PATH)
    if not os.path.exists(THUNDER_PATH):
        download_freesound(THUNDER_ID, THUNDER_PATH)

    print("[*] Carregando e padronizando os áudios (48kHz Mono)...")
    rain = AudioSegment.from_mp3(RAIN_PATH).set_channels(1).set_frame_rate(48000)
    thunder = AudioSegment.from_mp3(THUNDER_PATH).set_channels(1).set_frame_rate(48000)
    
    # Aumentar para 60 segundos (60000 milissegundos)
    rain = rain[:60000]
    samples = np.array(rain.get_array_of_samples(), dtype=np.float64)
    num_samples = len(samples)

    print("[*] Aplicando o efeito de passagem lenta (1 minuto)...")
    z = np.linspace(1.0, -1.0, num_samples)
    gain_front = np.clip(z + 0.3, 0, 1)
    gain_back = np.clip(-z + 0.3, 0, 1)
    gain_lfe = np.maximum(0, 1 - np.abs(z)) * 0.7

    ch_map = [
        samples * gain_front * 0.7, # 0: L
        samples * gain_front * 0.7, # 1: R
        samples * gain_front * 1.0, # 2: C
        samples * gain_lfe,         # 3: LFE
        samples * gain_back * 1.0,  # 4: SL
        samples * gain_back * 1.0   # 5: SR
    ]

    channels = []
    for ch in ch_map:
        channels.append(AudioSegment(
            ch.astype(np.int16).tobytes(), 
            frame_rate=48000, 
            sample_width=2, 
            channels=1
        ))

    storm_51 = AudioSegment.from_mono_audiosegments(*channels)

    print("[*] Inserindo os trovões de fundo aleatórios...")
    silent_thunder = thunder - 120 

    # Mantemos os 3 trovões originais espalhados entre os 5 e os 40 segundos
    for _ in range(3):
        start_ms = random.randint(5000, 40000)
        target_spk = random.choice([0, 1, 4, 5]) 
        
        th_ev = [silent_thunder, silent_thunder, silent_thunder, 
                 silent_thunder, silent_thunder, silent_thunder]
        
        th_ev[target_spk] = thunder + 3  
        th_ev[3] = thunder + 12         
        
        thunder_51 = AudioSegment.from_mono_audiosegments(*th_ev)
        storm_51 = storm_51.overlay(thunder_51, position=start_ms)

    print("[*] Inserindo o impacto do RAIO aos 50 segundos...")
    # O Raio aos 50s (50000 ms) estourando em todas as caixas
    start_lightning = 50000
    lightning_ev = [silent_thunder, silent_thunder, silent_thunder, 
                    silent_thunder, silent_thunder, silent_thunder]
    
    lightning_ev[0] = thunder + 5   # Frontal Esquerda
    lightning_ev[1] = thunder + 5   # Frontal Direita
    lightning_ev[2] = thunder + 6   # Central
    lightning_ev[3] = thunder + 15  # LFE (Força máxima no Subwoofer)
    lightning_ev[4] = thunder + 5   # Traseira Esquerda
    lightning_ev[5] = thunder + 5   # Traseira Direita

    lightning_51 = AudioSegment.from_mono_audiosegments(*lightning_ev)
    storm_51 = storm_51.overlay(lightning_51, position=start_lightning)

    print("[*] Exportando o arquivo FLAC 5.1...")
    # O FLAC final continuará sendo salvo na pasta onde o script está rodando
    output_name = "test_denon_storm_60s.flac"
    storm_51.export(output_name, format="flac")
    print(f"\n[SUCESSO] Arquivo '{output_name}' gerado!")

if __name__ == "__main__":
    generate_storm_51()