import os
import json
import random
import requests
import array
from pydub import AudioSegment

# ==============================================================================
# 1. CONFIGURAÇÃO E AMBIENTE
# ==============================================================================

# Identifica diretórios dinamicamente
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR) # Sobe um nível para achar a raiz
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.json")

def load_config():
    """Carrega as configurações do JSON central."""
    if not os.path.exists(CONFIG_PATH):
        # Fallback: Tenta achar na mesma pasta se não estiver na estrutura de projeto
        local_config = os.path.join(SCRIPT_DIR, "config.json")
        if os.path.exists(local_config):
            with open(local_config, 'r', encoding='utf-8') as f: return json.load(f)
            
        print(f"[ERRO CRÍTICO] config.json não encontrado em: {CONFIG_PATH}")
        exit(1)
    
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

# Carrega a configuração global
CONFIG = load_config()

# Define caminhos
ASSETS_DIR = os.path.join(PROJECT_ROOT, CONFIG['paths']['assets_dir'])
OUTPUT_FILENAME = "tempestade_5min_5.1.flac"
OUTPUT_PATH = os.path.join(SCRIPT_DIR, OUTPUT_FILENAME)

# IDs do Freesound
RAIN_ID = "243628"      
THUNDER_ID = "101667"   

# Parâmetros da Cena
DURATION_MINUTES = 5
TOTAL_MS = DURATION_MINUTES * 60 * 1000   
FADE_IN_MS = 2 * 60 * 1000                
FADE_OUT_MS = 30 * 1000                   
THUNDER_START = FADE_IN_MS                
THUNDER_END = TOTAL_MS - FADE_OUT_MS  

# ==============================================================================
# 2. FUNÇÕES AUXILIARES
# ==============================================================================

def download_smart(sound_id, filename_base):
    """Baixa OGG ou MP3 dependendo do config.json."""
    fmt = CONFIG['freesound']['default_format'] # "ogg" ou "mp3"
    filename = f"{filename_base}.{fmt}"
    filepath = os.path.join(ASSETS_DIR, filename)

    if os.path.exists(filepath):
        print(f"[CACHE] Asset pronto: {filename}")
        return filepath

    print(f"[DOWNLOAD] Baixando ID {sound_id} em {fmt.upper()}...")
    url_info = f"https://freesound.org/apiv2/sounds/{sound_id}/?token={CONFIG['freesound']['api_key']}"
    
    try:
        data = requests.get(url_info).json()
        
        # Tenta pegar o formato preferido, se falhar, tenta MP3
        key_name = f"preview-hq-{fmt}"
        if key_name not in data['previews']:
            print(f"[AVISO] Formato {fmt} indisponível, baixando MP3...")
            key_name = 'preview-hq-mp3'

        download_url = data['previews'][key_name]
        
        with open(filepath, 'wb') as f:
            f.write(requests.get(download_url).content)
        print(f"[SUCESSO] Salvo em: {filepath}")
        return filepath
    except Exception as e:
        print(f"[ERRO] Falha no download: {e}")
        return None

# ==============================================================================
# 3. GERAÇÃO DA TEMPESTADE
# ==============================================================================

def generate_storm():
    # 1. Preparação
    os.makedirs(ASSETS_DIR, exist_ok=True)
    rain_path = download_smart(RAIN_ID, "chuva")
    thunder_path = download_smart(THUNDER_ID, "trovao")

    if not rain_path or not thunder_path:
        print("[ABORTAR] Falha ao carregar assets.")
        return

    print("\n[*] Processando áudio (Isso leva alguns segundos)...")

    # 2. Carregar e Converter para MONO + 48kHz
    # Importante: Padronizar sample rate evita erros de clock no receiver
    rain_source = AudioSegment.from_file(rain_path).set_channels(1).set_frame_rate(48000)
    thunder_source = AudioSegment.from_file(thunder_path).set_channels(1).set_frame_rate(48000)
    
    # 3. Criar Base de Chuva
    print("    -> Criando loop de chuva...")
    loops_needed = (TOTAL_MS // len(rain_source)) + 1
    rain_long = (rain_source * loops_needed)[:TOTAL_MS]
    
    # Fades e Volume
    rain_long = rain_long.fade_in(FADE_IN_MS).fade_out(FADE_OUT_MS)
    rain_long = rain_long - 3  # -3dB para dar headroom aos raios

    # 4. Separar Canais 5.1
    ch_FL = rain_long      
    ch_FR = rain_long      
    ch_C  = rain_long - 3  # Centro um pouco mais baixo
    ch_SL = rain_long - 2  # Surrounds
    ch_SR = rain_long - 2  
    ch_LFE = rain_long.low_pass_filter(120) - 5 # Subwoofer só com graves

    # 5. Inserir Trovões Dinâmicos
    print("    -> Calculando tempestade...")
    thunder_loud = thunder_source + 5
    current_time = THUNDER_START
    
    thunder_log = [] # Para salvar nos metadados

    while current_time < THUNDER_END:
        interval = random.randint(10000, 25000)
        current_time += interval
        if current_time >= THUNDER_END: break

        # Sorteia canal (0=FL, 1=FR, 2=C, 4=SL, 5=SR)
        target = random.choice([0, 1, 2, 4, 5])
        pos_map = {0:"Esq-Frente", 1:"Dir-Frente", 2:"Centro", 4:"Esq-Fundo", 5:"Dir-Fundo"}
        
        timestamp_str = f"{int(current_time/1000)}s"
        thunder_log.append(f"{timestamp_str}({pos_map[target]})")
        
        print(f"       ⚡ Raio em {timestamp_str} na posição: [{pos_map[target]}]")

        if target == 0: ch_FL = ch_FL.overlay(thunder_loud, position=current_time)
        elif target == 1: ch_FR = ch_FR.overlay(thunder_loud, position=current_time)
        elif target == 2: ch_C  = ch_C.overlay(thunder_loud, position=current_time)
        elif target == 4: ch_SL = ch_SL.overlay(thunder_loud, position=current_time)
        elif target == 5: ch_SR = ch_SR.overlay(thunder_loud, position=current_time)
        
        # Subwoofer recebe impacto extra
        ch_LFE = ch_LFE.overlay(thunder_loud.low_pass_filter(100) + 3, position=current_time)

    # ==============================================================================
    # 4. ALINHAMENTO BINÁRIO (Fix Essencial)
    # ==============================================================================
    print("[*] Realizando alinhamento binário de amostras...")
    channels = [ch_FL, ch_FR, ch_C, ch_LFE, ch_SL, ch_SR]
    
    raw_samples_list = [ch.get_array_of_samples() for ch in channels]
    max_samples = max(len(s) for s in raw_samples_list)
    
    final_channels = []
    for i, samples in enumerate(raw_samples_list):
        if len(samples) < max_samples:
            padding = array.array(samples.typecode, [0] * (max_samples - len(samples)))
            samples.extend(padding)
        
        new_ch = AudioSegment(
            data=samples.tobytes(),
            sample_width=channels[0].sample_width,
            frame_rate=channels[0].frame_rate,
            channels=1
        )
        final_channels.append(new_ch)

    # ==============================================================================
    # 5. EXPORTAÇÃO COM METADADOS
    # ==============================================================================
    print("[*] Aplicando metadados e exportando...")
    
    final_tags = CONFIG['metadata'].copy()
    
    # Adiciona detalhes da execução atual
    final_tags.update({
        "title": "Tempestade Tropical 5.1 (Procedural)",
        "tracknumber": "03",
        "comment": "Generated by Python Script (5minrain.py)",
        "description": f"Log de Raios: {', '.join(thunder_log)}",
        "date": "2026"
    })

    mix = AudioSegment.from_mono_audiosegments(
        final_channels[0], final_channels[1], final_channels[2], 
        final_channels[3], final_channels[4], final_channels[5]
    )
    
    mix.export(OUTPUT_PATH, format="flac", tags=final_tags)
    print(f"[SUCESSO] Arquivo salvo em: {OUTPUT_PATH}")
    print(f"Raio-X: {len(thunder_log)} raios cairam nesta simulação.")

if __name__ == "__main__":
    generate_storm()