import json
import random
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from tkinter import filedialog, messagebox
from updater import check_for_update

import customtkinter as ctk
import numpy as np
import sounddevice as sd
import soundfile as sf
import vlc
import whisper
import yt_dlp

from crawler_core import run_crawler
from ai_director import DreamAIDirector


VIDEOS_DIR = Path("Videos")
AUDIO_DIR = Path("audio")
AUDIO_DIR.mkdir(exist_ok=True)
SETTINGS_FILE = Path("dreamstitch_settings.json")
DREAM_INDEX_FILE = Path("dream_index.json")
DREAM_RENDER_DIR = Path("dream_renders")
DREAM_RENDER_DIR.mkdir(exist_ok=True)

VIDEO_EXTENSIONS = [".mp4", ".mkv", ".webm", ".mov"]

DEFAULT_SEGMENT_SECONDS = 8
DEFAULT_SEGMENTS_PER_DREAM = 8
DEFAULT_VOICE_SECONDS = 6
SAMPLE_RATE = 44100


class DreamStitchApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("DreamStitch")
        self.geometry("1240x900")
        self.minsize(1100, 780)

        # Theme palette
        self.primary_bg = "#101014"
        self.secondary_bg = "#1A1A22"
        self.panel_bg = "#242430"
        self.accent_color = "#00E5FF"
        self.hover_color = "#00AFC2"
        self.purple = "#7C3CFF"
        self.purple_hover = "#9B66FF"
        self.green = "#35FF8B"
        self.red = "#FF335C"
        self.amber = "#FFC857"
        self.text_color = "#EEEEEE"
        self.placeholder_color = "#7B7B88"
        self.configure(fg_color=self.primary_bg)

        # Runtime settings
        self.videos_dir = VIDEOS_DIR
        self.segment_seconds = DEFAULT_SEGMENT_SECONDS
        self.segments_per_dream = DEFAULT_SEGMENTS_PER_DREAM
        self.voice_seconds = DEFAULT_VOICE_SECONDS
        self.videos_per_keyword = 2
        self.max_vault_downloads = 500
        self.live_searches_per_term = 2
        self.use_live_mode = False
        self.hybrid_mode = True
        self.cache_live_clips = False  # Placeholder for later
        self.use_ffmpeg_stitching = True
        self.transition_seconds = 0.75
        self.render_width = 960
        self.render_height = 540

        # State
        self.videos = []
        self.is_playing = False
        self.is_syncing = False
        self.audio_level = 0.0
        self.audio_stream = None
        self.whisper_model = None
        self.ai_director = DreamAIDirector()
        self.last_ai_result = None
        self.settings_panel_visible = False
        self.static_visual_active = False
        self.static_audio_active = False
        self.static_audio_stream = None

        self.vlc_instance = vlc.Instance(
            "--no-video-title-show",
            "--quiet",
        )
        self.player = self.vlc_instance.media_player_new()

        self.load_settings()
        self.build_gui()
        self.scan_videos()
        self.load_whisper_thread()

    # ------------------------------------------------------------------
    # UI HELPERS
    def make_button(self, parent, text, command, color=None, hover=None, text_color=None, width=150):
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            width=width,
            fg_color=color or self.accent_color,
            hover_color=hover or self.hover_color,
            text_color=text_color or self.primary_bg,
            corner_radius=18,
            border_width=2,
            border_color="#5FFFFF" if color in (None, self.accent_color) else color,
            font=("Consolas", 14, "bold"),
        )

    def build_gui(self):
        ctk.set_appearance_mode("dark")

        header = ctk.CTkFrame(self, fg_color=self.primary_bg)
        header.pack(fill="x", padx=14, pady=(10, 0))

        ctk.CTkLabel(
            header,
            text="DreamStitch",
            font=("Consolas", 34, "bold"),
            text_color=self.accent_color,
        ).pack(side="left", padx=8)

        self.menu_button = ctk.CTkButton(
            header,
            text="☰",
            width=48,
            height=38,
            fg_color=self.panel_bg,
            hover_color=self.accent_color,
            text_color=self.text_color,
            corner_radius=10,
            border_width=1,
            border_color=self.accent_color,
            font=("Consolas", 22, "bold"),
            command=self.toggle_settings_panel,
        )
        self.menu_button.pack(side="right", padx=8)

        self.mode_label = ctk.CTkLabel(
            header,
            text="LOCAL VAULT",
            font=("Consolas", 13, "bold"),
            text_color=self.green,
        )
        self.mode_label.pack(side="right", padx=12)

        self.mood_entry = ctk.CTkEntry(
            self,
            width=900,
            height=42,
            placeholder_text="Type or speak a mood: eerie nostalgic chaotic jazz dream...",
            fg_color=self.secondary_bg,
            border_color=self.accent_color,
            text_color=self.text_color,
            placeholder_text_color=self.placeholder_color,
            corner_radius=12,
            font=("Consolas", 16),
        )
        self.mood_entry.pack(pady=10)

        preset_frame = ctk.CTkFrame(self, fg_color=self.secondary_bg, corner_radius=14)
        preset_frame.pack(pady=6)

        presets = [
            "eerie nostalgic",
            "chaotic funny weird",
            "lonely night rain",
            "jazz dream calm",
            "analog horror retro",
            "liminal empty surreal",
        ]

        for i, preset in enumerate(presets):
            ctk.CTkButton(
                preset_frame,
                text=preset,
                width=150,
                command=lambda p=preset: self.set_preset(p),
                fg_color=self.panel_bg,
                hover_color=self.accent_color,
                text_color=self.text_color,
                corner_radius=14,
                border_width=1,
                border_color="#3A3A48",
                font=("Consolas", 12, "bold"),
            ).grid(row=0, column=i, padx=5, pady=7)

        button_frame = ctk.CTkFrame(self, fg_color=self.secondary_bg, corner_radius=14)
        button_frame.pack(pady=8)

        self.scan_button = self.make_button(button_frame, "◈ SCAN VAULT", self.scan_videos, color="#1E7F46", hover="#35FF8B", text_color="#FFFFFF")
        self.scan_button.grid(row=0, column=0, padx=7, pady=8)

        self.mic_button = self.make_button(button_frame, "〰 MIC SIGNAL", self.toggle_mic, color="#244CFF", hover="#5F7DFF", text_color="#FFFFFF")
        self.mic_button.grid(row=0, column=1, padx=7, pady=8)

        self.voice_button = self.make_button(button_frame, "◉ CAPTURE VOICE", self.record_voice_thread, color="#FF8C00", hover="#FFC857", text_color="#101014", width=170)
        self.voice_button.grid(row=0, column=2, padx=7, pady=8)

        self.generate_button = self.make_button(button_frame, "◆ GENERATE DREAM", self.start_dream_thread, color=self.accent_color, hover="#6EFFFF", text_color="#101014", width=190)
        self.generate_button.grid(row=0, column=3, padx=7, pady=8)

        self.live_button = self.make_button(button_frame, "☁ LIVE DREAM", self.start_live_dream_thread, color=self.purple, hover=self.purple_hover, text_color="#FFFFFF", width=160)
        self.live_button.grid(row=0, column=4, padx=7, pady=8)

        self.stop_button = self.make_button(button_frame, "■ STOP SIGNAL", self.stop_dream, color=self.red, hover="#FF6684", text_color="#FFFFFF", width=160)
        self.stop_button.grid(row=0, column=5, padx=7, pady=8)

        self.crawl_button = self.make_button(button_frame, "🕷 CRAWL WEB", self.crawl_vault_thread, color="#6A00FF", hover="#8A2BE2", text_color="#FFFFFF", width=160)
        self.crawl_button.grid(row=0, column=6, padx=7, pady=8)

        self.status_label = ctk.CTkLabel(
            self,
            text="Ready.",
            text_color=self.text_color,
            font=("Consolas", 14),
        )
        self.status_label.pack(pady=8)

        self.wave_canvas = ctk.CTkCanvas(
            self,
            width=980,
            height=92,
            bg=self.secondary_bg,
            highlightthickness=0,
        )
        self.wave_canvas.pack(pady=8)

        self.recipe_box = ctk.CTkTextbox(
            self,
            width=980,
            height=130,
            fg_color=self.secondary_bg,
            text_color=self.text_color,
            border_color=self.accent_color,
            border_width=1,
            corner_radius=10,
            font=("Consolas", 12),
        )
        self.recipe_box.pack(pady=8)
        self.recipe_box.insert("1.0", "Dream recipe will appear here...")
        self.recipe_box.configure(state="disabled")

        self.video_panel = ctk.CTkFrame(
            self,
            width=960,
            height=540,
            fg_color="#050508",
            border_color=self.accent_color,
            border_width=1,
            corner_radius=12,
        )
        self.video_panel.pack(pady=8)
        self.video_panel.pack_propagate(False)

        self.video_placeholder = ctk.CTkLabel(
            self.video_panel,
            text="Dream signal waiting...",
            text_color=self.placeholder_color,
            font=("Consolas", 15, "italic"),
        )
        self.video_placeholder.place(relx=0.5, rely=0.5, anchor="center")

        self.video_static_canvas = ctk.CTkCanvas(
            self.video_panel,
            width=960,
            height=540,
            bg="#050508",
            highlightthickness=0,
        )
        self.video_static_canvas.place_forget()

        self.build_settings_panel()

    def build_settings_panel(self):
        self.settings_panel = ctk.CTkFrame(
            self,
            width=340,
            fg_color=self.panel_bg,
            border_color=self.accent_color,
            border_width=1,
            corner_radius=12,
        )

        ctk.CTkLabel(
            self.settings_panel,
            text="☰ SETTINGS",
            font=("Consolas", 20, "bold"),
            text_color=self.accent_color,
        ).pack(padx=14, pady=(14, 8), anchor="w")

        self.video_dir_entry = self.add_labeled_entry(
            "Vault folder",
            str(self.videos_dir),
        )
        ctk.CTkButton(
            self.settings_panel,
            text="📁 Browse Vault Folder",
            command=self.browse_video_dir,
            fg_color=self.accent_color,
            hover_color=self.hover_color,
            text_color=self.primary_bg,
            corner_radius=12,
            font=("Consolas", 13, "bold"),
        ).pack(fill="x", padx=14, pady=(4, 12))

        self.segment_entry = self.add_labeled_entry("Segment seconds", str(self.segment_seconds))
        self.segment_count_entry = self.add_labeled_entry("Segments per dream", str(self.segments_per_dream))
        self.max_download_entry = self.add_labeled_entry("Max vault downloads", str(self.max_vault_downloads))
        self.videos_per_keyword_entry = self.add_labeled_entry("Videos per crawl keyword", str(self.videos_per_keyword))

        ctk.CTkLabel(
            self.settings_panel,
            text="Signal modes",
            text_color=self.accent_color,
            font=("Consolas", 15, "bold"),
        ).pack(padx=14, pady=(12, 2), anchor="w")

        ctk.CTkButton(
            self.settings_panel,
            text="⬇ Check for Updates",
            command=self.check_for_updates_thread,
            fg_color=self.purple,
            hover_color=self.purple_hover,
            text_color="#FFFFFF",
            corner_radius=12,
            font=("Consolas", 13, "bold"),
        ).pack(fill="x", padx=14, pady=(4, 10))

        self.cloud_switch = ctk.CTkSwitch(
            self.settings_panel,
            text="☁ Live cloud mode",
            command=self.toggle_cloud_mode,
            onvalue=True,
            offvalue=False,
            text_color=self.text_color,
            fg_color="#3A3A48",
            progress_color=self.purple,
            button_color=self.text_color,
            button_hover_color=self.accent_color,
            font=("Consolas", 13),
        )
        if self.use_live_mode:
            self.cloud_switch.select()
        else:
            self.cloud_switch.deselect()
        self.cloud_switch.pack(padx=14, pady=(8, 4), anchor="w")

        self.hybrid_switch = ctk.CTkSwitch(
            self.settings_panel,
            text="◇ Hybrid local + live",
            command=self.toggle_hybrid_mode,
            onvalue=True,
            offvalue=False,
            text_color=self.text_color,
            fg_color="#3A3A48",
            progress_color=self.green,
            button_color=self.text_color,
            button_hover_color=self.accent_color,
            font=("Consolas", 13),
        )
        if self.hybrid_mode:
            self.hybrid_switch.select()
        else:
            self.hybrid_switch.deselect()
        self.hybrid_switch.pack(padx=14, pady=4, anchor="w")

        self.cache_switch = ctk.CTkSwitch(
            self.settings_panel,
            text="💾 Cache live clips later",
            command=self.toggle_cache_live,
            onvalue=True,
            offvalue=False,
            text_color=self.text_color,
            fg_color="#3A3A48",
            progress_color=self.amber,
            button_color=self.text_color,
            button_hover_color=self.accent_color,
            font=("Consolas", 13),
        )
        if self.cache_live_clips:
            self.cache_switch.select()
        else:
            self.cache_switch.deselect()
        self.cache_switch.pack(padx=14, pady=4, anchor="w")

        ctk.CTkButton(
            self.settings_panel,
            text="Apply Settings",
            command=self.apply_settings,
            fg_color=self.green,
            hover_color="#75FFAF",
            text_color=self.primary_bg,
            corner_radius=12,
            font=("Consolas", 13, "bold"),
        ).pack(fill="x", padx=14, pady=(16, 10))

        ctk.CTkLabel(
            self.settings_panel,
            text="Live mode streams temporary web signals.\nLocal vault mode uses downloaded memory.",
            text_color=self.placeholder_color,
            font=("Consolas", 11),
            justify="left",
        ).pack(padx=14, pady=(4, 14), anchor="w")

        self.settings_panel.place(relx=1.0, rely=0.095, anchor="ne")
        self.settings_panel.place_forget()

    def add_labeled_entry(self, label, value):
        ctk.CTkLabel(
            self.settings_panel,
            text=label,
            text_color=self.text_color,
            font=("Consolas", 13),
        ).pack(padx=14, pady=(8, 2), anchor="w")
        entry = ctk.CTkEntry(
            self.settings_panel,
            fg_color=self.secondary_bg,
            border_color="#3A3A48",
            text_color=self.text_color,
            placeholder_text_color=self.placeholder_color,
            font=("Consolas", 12),
        )
        entry.insert(0, value)
        entry.pack(fill="x", padx=14, pady=(0, 4))
        return entry

    # ------------------------------------------------------------------
    # SETTINGS
    def load_settings(self):
        """Load saved DreamStitch settings if they exist."""
        if not SETTINGS_FILE.exists():
            return

        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            self.videos_dir = Path(data.get("videos_dir", str(self.videos_dir)))
            self.segment_seconds = int(data.get("segment_seconds", self.segment_seconds))
            self.segments_per_dream = int(data.get("segments_per_dream", self.segments_per_dream))
            self.voice_seconds = int(data.get("voice_seconds", self.voice_seconds))
            self.videos_per_keyword = int(data.get("videos_per_keyword", self.videos_per_keyword))
            self.max_vault_downloads = int(data.get("max_vault_downloads", self.max_vault_downloads))
            self.live_searches_per_term = int(data.get("live_searches_per_term", self.live_searches_per_term))
            self.use_live_mode = bool(data.get("use_live_mode", self.use_live_mode))
            self.hybrid_mode = bool(data.get("hybrid_mode", self.hybrid_mode))
            self.cache_live_clips = bool(data.get("cache_live_clips", self.cache_live_clips))
        except Exception:
            # Bad settings should never block the app from opening.
            pass

    def save_settings(self):
        """Persist the current DreamStitch settings to disk."""
        data = {
            "videos_dir": str(self.videos_dir),
            "segment_seconds": self.segment_seconds,
            "segments_per_dream": self.segments_per_dream,
            "voice_seconds": self.voice_seconds,
            "videos_per_keyword": self.videos_per_keyword,
            "max_vault_downloads": self.max_vault_downloads,
            "live_searches_per_term": self.live_searches_per_term,
            "use_live_mode": self.use_live_mode,
            "hybrid_mode": self.hybrid_mode,
            "cache_live_clips": self.cache_live_clips,
        }
        try:
            SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            self.safe_status(f"Could not save settings: {e}")

    def toggle_settings_panel(self):
        if self.settings_panel_visible:
            self.settings_panel.place_forget()
            self.settings_panel_visible = False
        else:
            self.video_dir_entry.delete(0, "end")
            self.video_dir_entry.insert(0, str(self.videos_dir))
            self.settings_panel.place(relx=1.0, rely=0.095, anchor="ne")
            self.settings_panel_visible = True

    def browse_video_dir(self):
        directory = filedialog.askdirectory(initialdir=str(self.videos_dir))
        if directory:
            self.videos_dir = Path(directory)
            self.video_dir_entry.delete(0, "end")
            self.video_dir_entry.insert(0, directory)
            self.scan_videos()
            self.save_settings()
            self.safe_status(f"Vault folder set: {directory}")

    def apply_settings(self):
        try:
            possible_dir = Path(self.video_dir_entry.get().strip() or "Videos")
            self.videos_dir = possible_dir
            self.segment_seconds = max(2, int(self.segment_entry.get().strip()))
            self.segments_per_dream = max(1, int(self.segment_count_entry.get().strip()))
            self.max_vault_downloads = max(1, int(self.max_download_entry.get().strip()))
            self.videos_per_keyword = max(1, int(self.videos_per_keyword_entry.get().strip()))
            self.scan_videos()
            self.save_settings()
            self.update_mode_label()
            self.safe_status("Settings applied and saved.")
        except Exception as e:
            self.safe_status(f"Settings error: {e}")

    def toggle_cloud_mode(self):
        self.use_live_mode = bool(self.cloud_switch.get())
        self.update_mode_label()
        self.save_settings()
        self.safe_status("Live cloud mode enabled." if self.use_live_mode else "Local vault mode enabled.")

    def toggle_hybrid_mode(self):
        self.hybrid_mode = bool(self.hybrid_switch.get())
        self.save_settings()
        self.safe_status("Hybrid mode enabled." if self.hybrid_mode else "Hybrid mode disabled.")

    def toggle_cache_live(self):
        self.cache_live_clips = bool(self.cache_switch.get())
        self.save_settings()
        self.safe_status("Live clip caching marked for later." if self.cache_live_clips else "Live clip caching disabled.")

    def update_mode_label(self):
        if self.use_live_mode and self.hybrid_mode:
            self.mode_label.configure(text="HYBRID SIGNAL", text_color=self.amber)
        elif self.use_live_mode:
            self.mode_label.configure(text="LIVE CLOUD", text_color=self.purple_hover)
        else:
            self.mode_label.configure(text="LOCAL VAULT", text_color=self.green)

    # ------------------------------------------------------------------
    # BASIC UTILITIES
    def safe_status(self, text):
        self.after(0, lambda: self.status_label.configure(text=text))

    def set_preset(self, text):
        self.mood_entry.delete(0, "end")
        self.mood_entry.insert(0, text)

    def has_internet(self):
        try:
            urllib.request.urlopen("https://www.youtube.com", timeout=5)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # CRAWLER
    def crawl_vault_thread(self):
        if self.is_syncing:
            self.status_label.configure(text="Crawler is already running.")
            return
        threading.Thread(target=self.crawl_vault, daemon=True).start()

    def crawl_vault(self):
        self.is_syncing = True
        self.after(0, lambda: self.crawl_button.configure(state="disabled", text="Crawling..."))

        if not self.has_internet():
            self.safe_status("No internet connection. Using local vault.")
            self.is_syncing = False
            self.after(0, lambda: self.crawl_button.configure(state="normal", text="🕷 CRAWL WEB"))
            return

        try:
            run_crawler(
                videos_dir=self.videos_dir,
                videos_per_keyword=self.videos_per_keyword,
                max_total_downloads=self.max_vault_downloads,
                status_callback=self.safe_status,
            )
            self.after(0, self.scan_videos)
            self.safe_status("Crawl complete.")
        except Exception as e:
            self.safe_status(f"Crawl failed: {e}")

        self.is_syncing = False
        self.after(0, lambda: self.crawl_button.configure(state="normal", text="🕷 CRAWL WEB"))

    # ------------------------------------------------------------------
    # WHISPER + MIC
    def load_whisper_thread(self):
        threading.Thread(target=self.load_whisper, daemon=True).start()

    def load_whisper(self):
        self.safe_status("Loading Whisper voice model...")
        try:
            self.whisper_model = whisper.load_model("base")
            self.safe_status("Whisper loaded. Ready.")
        except Exception as e:
            self.safe_status(f"Whisper failed to load: {e}")

    def toggle_mic(self):
        if self.audio_stream is None:
            self.start_audio_stream()
            self.mic_button.configure(text="〰 STOP MIC")
        else:
            self.stop_audio_stream()
            self.mic_button.configure(text="〰 MIC SIGNAL")

    def start_audio_stream(self):
        def audio_callback(indata, frames, time_info, status):
            volume = np.linalg.norm(indata) * 10
            self.audio_level = min(volume, 1.0)

        self.audio_stream = sd.InputStream(channels=1, callback=audio_callback, samplerate=SAMPLE_RATE)
        self.audio_stream.start()
        self.animate_waveform()

    def stop_audio_stream(self):
        if self.audio_stream:
            self.audio_stream.stop()
            self.audio_stream.close()
            self.audio_stream = None

    def animate_waveform(self):
        self.wave_canvas.delete("all")
        width = 980
        height = 92
        mid_y = height // 2
        points = []

        for x in range(0, width, 8):
            noise = random.uniform(-1, 1)
            amp = 8 + self.audio_level * 40
            y = mid_y + noise * amp
            points.append((x, y))

        for i in range(len(points) - 1):
            self.wave_canvas.create_line(points[i][0], points[i][1], points[i + 1][0], points[i + 1][1], fill=self.accent_color, width=2)

        if self.audio_stream is not None:
            self.after(40, self.animate_waveform)

    def record_voice_thread(self):
        threading.Thread(target=self.record_voice, daemon=True).start()

    def record_voice(self):
        if self.whisper_model is None:
            self.safe_status("Whisper is still loading. Try again in a moment.")
            return

        self.safe_status(f"Recording voice for {self.voice_seconds} seconds...")
        audio = sd.rec(int(self.voice_seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="float32")
        sd.wait()

        audio_path = AUDIO_DIR / "voice_input.wav"
        sf.write(audio_path, audio, SAMPLE_RATE)
        self.safe_status("Transcribing voice...")

        try:
            result = self.whisper_model.transcribe(str(audio_path))
            text = result.get("text", "").strip().lower()
            if text:
                self.after(0, lambda: self.mood_entry.delete(0, "end"))
                self.after(0, lambda: self.mood_entry.insert(0, text))
                self.safe_status(f"Heard: {text}")
            else:
                self.safe_status("No speech detected.")
        except Exception as e:
            self.safe_status(f"Transcription failed: {e}")

    # ------------------------------------------------------------------
    # VIDEO SCANNING + LOCAL DREAM
    def scan_videos(self):
        self.videos_dir.mkdir(exist_ok=True, parents=True)
        self.videos = [file for file in self.videos_dir.rglob("*") if file.suffix.lower() in VIDEO_EXTENSIONS]
        self.build_dream_index()
        self.status_label.configure(text=f"Found {len(self.videos)} video files in vault.")

    def build_dream_index(self):
        """Create a small DreamStitch-owned metadata index for local videos.

        This does not rely on YouTube JSON. It gives the future AI director
        a clean local memory file to read later.
        """
        index = []
        for video in self.videos:
            category = self.detect_category(video)
            tags = sorted(set([category] + [w for w in video.stem.lower().replace("_", " ").replace("-", " ").split() if len(w) > 2]))
            index.append({
                "file": str(video),
                "name": video.name,
                "source": "local",
                "category": category,
                "dream_tags": tags[:24],
                "energy": self.estimate_energy_from_tags(tags),
                "weirdness": self.estimate_weirdness_from_tags(tags),
                "last_used": None,
            })

        try:
            DREAM_INDEX_FILE.write_text(json.dumps(index, indent=2), encoding="utf-8")
        except Exception:
            pass

    def estimate_energy_from_tags(self, tags):
        text = " ".join(tags)
        if any(w in text for w in ["chaotic", "meme", "ytp", "glitch", "fast"]):
            return "high"
        if any(w in text for w in ["rain", "jazz", "ambient", "calm", "forest", "ocean"]):
            return "low"
        return "medium"

    def estimate_weirdness_from_tags(self, tags):
        text = " ".join(tags)
        score = 0.35
        for word in ["weird", "surreal", "dreamcore", "backrooms", "uncanny", "glitch", "analog", "vhs", "ytp"]:
            if word in text:
                score += 0.08
        return round(min(score, 1.0), 2)

    def start_dream_thread(self):
        if self.is_playing:
            return
        threading.Thread(target=self.generate_dream, daemon=True).start()

    def start_live_dream_thread(self):
        if self.is_playing:
            return
        threading.Thread(target=self.generate_live_dream, daemon=True).start()

    def stop_dream(self):
        self.is_playing = False
        self.stop_waiting_static()
        self.player.stop()
        self.status_label.configure(text="Stopped.")

    def generate_dream(self):
        if self.use_live_mode:
            self.generate_live_dream()
            return

        if not self.videos:
            self.safe_status("No videos found in vault.")
            return

        self.is_playing = True
        mood = self.mood_entry.get().strip().lower()
        expanded_moods = self.expand_mood_words(mood)

        ai_result = self.get_ai_dream_direction(mood, expanded_moods)
        expanded_moods = ai_result.get("tags", expanded_moods)

        if ai_result.get("source") == "local_ai":
            self.safe_status(f"AI Director active: {ai_result.get('summary', '')}")
            recipe_source = "local vault + AI director"
        else:
            self.safe_status(f"Tuning into: {mood or 'random dream'}")
            recipe_source = "local vault + Python rules"

        selected_videos = self.pick_videos(expanded_moods)
        self.update_recipe(mood, expanded_moods, selected_videos, source=recipe_source)

        # Preferred path: render the selected fragments into one continuous
        # temporary MP4 with FFmpeg, then play that single file in VLC. While
        # that render is happening, DreamStitch shows/listens like it is tuning
        # into a signal instead of sitting on a dead waiting screen.
        if self.use_ffmpeg_stitching and self.ffmpeg_available():
            stitched_path = None
            try:
                self.start_waiting_static("Scanning dream frequencies...")
                stitched_path = self.render_stitched_dream(selected_videos)
            finally:
                self.stop_waiting_static()

            if stitched_path and stitched_path.exists() and self.is_playing:
                self.safe_status(f"Signal acquired: {stitched_path.name}")
                self.play_tuning_tone(duration=0.18, frequency=880)
                self.safe_status(f"Playing stitched dream: {stitched_path.name}")
                self.play_rendered_dream(stitched_path)
                self.is_playing = False
                self.player.stop()
                self.safe_status("Dream ended.")
                return

            self.safe_status("FFmpeg stitch failed. Falling back to live segment playback.")
        elif self.use_ffmpeg_stitching:
            self.safe_status("FFmpeg not found. Falling back to live segment playback.")

        self.signal_tuning_sequence()

        for index, video_path in enumerate(selected_videos, start=1):
            if not self.is_playing:
                break

            category = self.detect_category(video_path)
            self.safe_status(f"Dream {index}/{len(selected_videos)} [{category}]: {video_path.name}")
            self.play_video_segment(video_path)

        self.is_playing = False
        self.player.stop()
        self.safe_status("Dream ended.")

    # ------------------------------------------------------------------
    # LIVE CLOUD MODE
    def generate_live_dream(self):
        if not self.has_internet():
            self.safe_status("No internet connection. Falling back to local vault.")
            self.generate_dream_local_fallback()
            return

        self.is_playing = True
        mood = self.mood_entry.get().strip().lower()
        expanded_moods = self.expand_mood_words(mood)
        search_terms = self.make_search_terms(mood, expanded_moods)

        self.safe_status("Searching live cloud signal...")
        candidates = self.get_live_video_candidates(search_terms)

        if not candidates:
            self.safe_status("No live signal found. Falling back to local vault.")
            self.generate_dream_local_fallback()
            return

        # Live mode now uses the same FFmpeg dream idea as local mode.
        # To keep it fast, we only resolve enough live stream candidates for the
        # requested dream instead of building a huge candidate pool.
        selected = candidates[: self.segments_per_dream]
        self.update_recipe(mood, expanded_moods, selected, source="live cloud + ffmpeg")

        if self.use_ffmpeg_stitching and self.ffmpeg_available():
            stitched_path = None
            try:
                self.start_waiting_static("Locking onto live dream signal...")
                stitched_path = self.render_stitched_live_dream(selected)
            finally:
                self.stop_waiting_static()

            if stitched_path and stitched_path.exists() and self.is_playing:
                self.safe_status(f"Live signal acquired: {stitched_path.name}")
                self.play_tuning_tone(duration=0.18, frequency=880)
                self.safe_status(f"Playing stitched live dream: {stitched_path.name}")
                self.play_rendered_dream(stitched_path)
                self.is_playing = False
                self.player.stop()
                self.safe_status("Live dream ended.")
                return

            self.safe_status("Live FFmpeg stitch failed. Falling back to stream playback.")
        elif self.use_ffmpeg_stitching:
            self.safe_status("FFmpeg not found. Falling back to stream playback.")

        self.signal_tuning_sequence()

        for index, item in enumerate(selected, start=1):
            if not self.is_playing:
                break
            title = item.get("title", "live signal")
            self.safe_status(f"Live dream {index}/{len(selected)}: {title[:90]}")
            self.play_stream_segment(item.get("stream_url") or item.get("url"))

        self.is_playing = False
        self.player.stop()
        self.safe_status("Live dream ended.")

    def generate_dream_local_fallback(self):
        self.use_live_mode = False
        self.update_mode_label()
        self.generate_dream()

    def get_live_video_candidates(self, search_terms):
        candidates = []
        target_count = max(1, int(self.segments_per_dream))
        terms_to_search = search_terms[:5]

        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "noplaylist": True,
            "ignoreerrors": True,
            # 480p keeps live FFmpeg rendering much faster while still looking
            # good inside the 960x540 DreamStitch viewport.
            "format": "best[height<=480][ext=mp4]/best[height<=480]/best",
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                for term in terms_to_search:
                    if len(candidates) >= target_count:
                        break

                    # Search fewer results per term for speed. The goal is not a
                    # giant crawl here; it is to quickly resolve enough live
                    # signals to render a dream.
                    query = f"ytsearch{max(1, min(self.live_searches_per_term, 2))}:{term}"
                    self.safe_status(f"Live search: {term}")
                    info = ydl.extract_info(query, download=False)
                    entries = info.get("entries", []) if info else []

                    for entry in entries:
                        if not entry or len(candidates) >= target_count:
                            continue

                        duration = entry.get("duration") or 0
                        if duration and duration < max(20, self.segment_seconds + 4):
                            continue

                        stream_url = entry.get("url")
                        if not stream_url:
                            continue

                        title = entry.get("title", "untitled signal")
                        candidates.append({
                            "title": title,
                            "stream_url": stream_url,
                            "webpage_url": entry.get("webpage_url"),
                            "duration": duration,
                            "search_term": term,
                            "category": self.detect_category_from_text(title + " " + term),
                        })
        except Exception as e:
            self.safe_status(f"Live search failed: {e}")

        random.shuffle(candidates)
        return candidates

    def make_search_terms(self, mood, expanded_moods):
        if mood:
            base = [mood]
        else:
            base = ["liminal dreamcore", "empty mall at night", "analog vhs ambience"]

        terms = list(base)
        phrase_map = {
            "lonely": ["empty city at night", "lonely train ride", "rainy parking lot ambience"],
            "nostalgic": ["90s mall footage", "old vhs commercial", "mallsoft ambience"],
            "weird": ["weirdcore footage", "surreal found footage", "uncanny video"],
            "scary": ["analog horror ambience", "eerie hallway vhs", "abandoned building night"],
            "calm": ["smooth jazz night drive", "rainy window ambience", "quiet forest dusk"],
            "jazz": ["smooth jazz live", "late night jazz club", "Sade live"],
            "dream": ["dreamcore video", "liminal space footage", "surreal dreamlike short film"],
            "retro": ["vaporwave visuals", "windows 95 aesthetic", "retro computer graphics"],
            "glitch": ["glitch art video", "datamosh video", "crt static footage"],
            "interesting": ["surreal short film", "strange public access television", "odd retro commercial"],
            "disconnected": ["liminal office footage", "empty shopping mall", "analog found footage"],
            "familiar": ["nostalgic home video vhs", "suburban street at night", "old camcorder footage"],
            "uncanny": ["uncanny footage", "liminal hallway", "strange found footage"],
        }
        for word in expanded_moods:
            if word in phrase_map:
                terms.extend(phrase_map[word])
            else:
                terms.append(f"{word} ambience")

        # de-dupe while preserving order, then limit
        final_terms = []
        for term in terms:
            term = term.strip()
            if term and term not in final_terms:
                final_terms.append(term)
        return final_terms[:10]

    # ------------------------------------------------------------------
    # MOOD + SCORING
    def expand_mood_words(self, mood_text):
        """Expand user input into DreamStitch-friendly tags.

        This is still not the full AI director. It is a stronger bridge
        between a plain search bar and real language understanding.
        Vague words are translated into useful visual buckets/search ideas.
        """
        raw = mood_text.strip().lower() if mood_text else ""
        words = raw.split() if raw else []

        synonym_map = {
            "sad": ["lonely", "night", "rain", "jazz"],
            "alone": ["lonely", "empty", "liminal", "night"],
            "lonely": ["empty", "night", "rain", "train", "liminal"],
            "weird": ["surreal", "strange", "uncanny", "ytp", "glitch"],
            "funny": ["ytp", "chaotic", "meme"],
            "nostalgic": ["retro", "vhs", "jazz", "mall", "90s"],
            "calm": ["jazz", "nature", "rain", "ambient"],
            "scary": ["eerie", "dark", "vhs", "surreal", "analog"],
            "dream": ["surreal", "liminal", "soft", "nature"],
            "dreamy": ["dreamcore", "surreal", "soft", "liminal"],
            "confused": ["glitch", "chaotic", "surreal", "ytp"],
            "hopeful": ["nature", "jazz", "soft", "morning"],
            "interesting": ["surreal", "public", "access", "odd", "retro", "uncanny", "experimental"],
            "cool": ["retro", "city", "night", "vaporwave", "tech"],
            "disconnected": ["liminal", "empty", "office", "mall", "night", "analog"],
            "familiar": ["nostalgic", "home", "vhs", "suburb", "mall"],
            "home": ["vhs", "suburb", "bedroom", "window", "rain"],
            "empty": ["liminal", "mall", "hallway", "office", "parking"],
            "beautiful": ["nature", "ocean", "sunset", "city", "soft"],
        }

        phrase_triggers = {
            "not home": ["uncanny", "suburb", "liminal", "vhs"],
            "parallel universe": ["liminal", "surreal", "backrooms", "analog", "empty"],
            "feels fake": ["uncanny", "simulation", "glitch", "surreal"],
            "old internet": ["retro", "tech", "windows", "web", "flash"],
            "at night": ["night", "rain", "street", "drive"],
        }

        expanded = list(words)
        for phrase, tags in phrase_triggers.items():
            if phrase in raw:
                expanded.extend(tags)

        for word in words:
            if word in synonym_map:
                expanded.extend(synonym_map[word])

        # remove tiny filler words that do not help matching/searching
        filler = {"i", "im", "i'm", "am", "feel", "feeling", "like", "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "it", "its", "is", "that", "this", "somewhere"}
        cleaned = []
        for item in expanded:
            item = item.strip().lower()
            if item and item not in filler and item not in cleaned:
                cleaned.append(item)
        return cleaned

    def detect_category(self, video_path):
        return self.detect_category_from_text(video_path.name.lower())

    def detect_category_from_text(self, text):
        name = text.lower()
        categories = {
            "jazz": ["jazz", "lindsey", "saxophone", "lounge", "webster", "sade"],
            "ytp": ["ytp", "youtube poop", "sentence", "meme", "chaotic"],
            "liminal": ["mall", "liminal", "hallway", "backrooms", "empty"],
            "vhs": ["vhs", "training", "corporate", "broadcast", "public access", "analog"],
            "night": ["night", "rain", "fog", "street", "drive"],
            "nature": ["forest", "ocean", "snow", "mountain", "beach"],
            "tech": ["windows", "computer", "retro", "internet", "technology"],
            "surreal": ["dreamcore", "weirdcore", "surreal", "uncanny", "strange", "glitch"],
        }
        for category, words in categories.items():
            if any(word in name for word in words):
                return category
        return "unknown"

    def score_video(self, video_path, mood_words):
        name = video_path.name.lower()
        category = self.detect_category(video_path)
        score = random.random()
        for word in mood_words:
            if word in name:
                score += 5
        category_mood_map = {
            "eerie": ["liminal", "night", "vhs", "surreal"],
            "nostalgic": ["vhs", "tech", "jazz", "liminal"],
            "chaotic": ["ytp", "surreal"],
            "funny": ["ytp"],
            "calm": ["jazz", "nature", "night"],
            "weird": ["surreal", "ytp", "vhs"],
            "dream": ["surreal", "liminal", "jazz", "nature"],
            "jazz": ["jazz"],
            "analog": ["vhs", "tech"],
            "lonely": ["liminal", "night", "nature"],
            "sad": ["night", "jazz", "nature"],
            "retro": ["vhs", "tech", "ytp"],
            "internet": ["ytp", "tech", "surreal"],
            "soft": ["jazz", "nature"],
            "dark": ["night", "vhs", "surreal"],
            "glitch": ["surreal", "ytp", "tech"],
        }
        for mood in mood_words:
            if mood in category_mood_map and category in category_mood_map[mood]:
                score += 4
        return score

    def build_dream_arc_rules(self, mood_words):
        """Choose a loose emotional/visual arc for the dream.

        This is the first version of the Dream Director.
        Later, a small local LLM can generate or modify this arc,
        but regular Python rules are better for the foundation because
        they are fast, predictable, and easy to debug.
        """
        text = " ".join(mood_words)

        if any(w in text for w in ["calm", "jazz", "soft", "nature", "rain", "peaceful"]):
            return ["jazz", "night", "nature", "liminal", "vhs", "jazz"]

        if any(w in text for w in ["chaotic", "funny", "ytp", "meme", "confused", "absurd"]):
            return ["vhs", "ytp", "surreal", "tech", "ytp", "liminal"]

        if any(w in text for w in ["scary", "eerie", "dark", "analog", "horror", "creepy"]):
            return ["liminal", "vhs", "night", "surreal", "vhs", "unknown"]

        if any(w in text for w in ["lonely", "alone", "empty", "disconnected", "lost"]):
            return ["night", "liminal", "vhs", "surreal", "nature", "jazz"]

        if any(w in text for w in ["nostalgic", "retro", "home", "familiar", "old", "memory"]):
            return ["vhs", "tech", "liminal", "jazz", "surreal", "night"]

        if any(w in text for w in ["parallel", "fake", "simulation", "uncanny", "dreamcore", "weirdcore"]):
            return ["liminal", "surreal", "tech", "vhs", "night", "unknown"]

        return ["liminal", "vhs", "surreal", "night", "jazz", "unknown"]

    def get_ai_dream_direction(self, mood_text, fallback_tags):
        """Ask the optional local GGUF AI Director for tags + dream arc.

        If the AI model is missing, llama-cpp-python is not installed, or the
        model returns bad JSON, this safely falls back to the existing Python
        rules. This keeps DreamStitch usable even when the AI layer is not ready.
        """
        fallback_arc = self.build_dream_arc_rules(fallback_tags)

        try:
            result = self.ai_director.analyze_mood(
                mood_text=mood_text,
                fallback_tags=fallback_tags,
                fallback_arc=fallback_arc,
            )
        except Exception as e:
            result = {
                "tags": fallback_tags,
                "arc": fallback_arc,
                "source": "python_rules",
                "summary": f"AI Director error. Using Python rules. Reason: {e}",
            }

        self.last_ai_result = result
        return result

    def build_dream_arc(self, mood_words):
        """Return the active dream arc.

        The local AI Director gets first chance to shape the arc. If it is not
        available, this returns the older rule-based arc.
        """
        mood_text = self.mood_entry.get().strip().lower() if hasattr(self, "mood_entry") else ""
        ai_result = self.get_ai_dream_direction(mood_text, mood_words)
        return ai_result.get("arc", self.build_dream_arc_rules(mood_words))

    def pick_videos(self, mood_words):
        """Pick videos using mood scoring plus a Dream Director arc.

        Old behavior: choose mostly from top-scored clips.
        New behavior: score clips, build a category arc, then choose clips
        that fit the arc while avoiding too much repetition.
        """
        scored = []

        for video in self.videos:
            scored.append({
                "video": video,
                "category": self.detect_category(video),
                "score": self.score_video(video, mood_words),
            })

        scored.sort(key=lambda item: item["score"], reverse=True)
        candidate_pool = scored[:140]

        dream_arc = self.build_dream_arc(mood_words)

        selected = []
        used_categories = {}

        # Follow the intended dream arc first.
        for desired_category in dream_arc:
            possible = [
                item for item in candidate_pool
                if item["category"] == desired_category
                and item["video"] not in selected
                and used_categories.get(item["category"], 0) < 2
            ]

            # If the exact category is missing, fall back to any strong candidate
            # while still avoiding too much category repetition.
            if not possible:
                possible = [
                    item for item in candidate_pool
                    if item["video"] not in selected
                    and used_categories.get(item["category"], 0) < 2
                ]

            if not possible:
                break

            chosen = random.choice(possible[:12])
            selected.append(chosen["video"])
            used_categories[chosen["category"]] = used_categories.get(chosen["category"], 0) + 1

            if len(selected) >= self.segments_per_dream:
                break

        # Fill any remaining slots if the arc was shorter than the configured
        # number of dream segments.
        while len(selected) < self.segments_per_dream:
            remaining = [
                item for item in candidate_pool
                if item["video"] not in selected
            ]

            if not remaining:
                break

            chosen = random.choice(remaining[:20])
            selected.append(chosen["video"])

        return selected

    # ------------------------------------------------------------------
    # FFMPEG STITCHING
    def ffmpeg_available(self):
        return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None

    def get_media_duration(self, video_path):
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
            if result.returncode == 0:
                return max(0.0, float(result.stdout.strip() or 0))
        except Exception:
            pass
        return 0.0

    def media_has_audio(self, video_path):
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=index",
                "-of", "csv=p=0",
                str(video_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
            return result.returncode == 0 and bool(result.stdout.strip())
        except Exception:
            return False

    def render_segment_for_stitch(self, video_path, output_path):
        duration = self.get_media_duration(video_path)
        segment_seconds = max(2, int(self.segment_seconds))

        if duration > segment_seconds + 2:
            max_start = max(0, int(duration - segment_seconds - 1))
            start_time = random.randint(0, max_start)
        else:
            start_time = 0

        vf = (
            f"scale={self.render_width}:{self.render_height}:force_original_aspect_ratio=increase,"
            f"crop={self.render_width}:{self.render_height},"
            "fps=30,setsar=1,format=yuv420p"
        )

        if self.media_has_audio(video_path):
            cmd = [
                "ffmpeg", "-y",
                "-hide_banner", "-loglevel", "error",
                "-ss", str(start_time),
                "-i", str(video_path),
                "-t", str(segment_seconds),
                "-map", "0:v:0",
                "-map", "0:a:0",
                "-vf", vf,
                "-af", f"aresample=44100,apad,atrim=0:{segment_seconds}",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "128k",
                "-shortest",
                str(output_path),
            ]
        else:
            cmd = [
                "ffmpeg", "-y",
                "-hide_banner", "-loglevel", "error",
                "-ss", str(start_time),
                "-i", str(video_path),
                "-f", "lavfi",
                "-t", str(segment_seconds),
                "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                "-t", str(segment_seconds),
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-vf", vf,
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "128k",
                "-shortest",
                str(output_path),
            ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            self.safe_status(f"Segment render failed: {video_path.name[:60]}")
            return False
        return output_path.exists()

    def render_live_stream_for_stitch(self, item, output_path):
        """Render a short normalized fragment from a live yt-dlp stream URL.

        This avoids downloading whole videos. FFmpeg grabs only the short piece
        DreamStitch needs, normalizes it to the local render size, and saves a
        temporary MP4 that can be crossfaded with the rest of the dream.
        """
        stream_url = item.get("stream_url") or item.get("url") or item.get("webpage_url")
        if not stream_url:
            return False

        segment_seconds = max(2, int(self.segment_seconds))
        title = item.get("title", "live signal")

        vf = (
            f"scale={self.render_width}:{self.render_height}:force_original_aspect_ratio=increase,"
            f"crop={self.render_width}:{self.render_height},"
            "fps=30,setsar=1,format=yuv420p"
        )

        # Most YouTube streams include audio, but the fallback below keeps the
        # final crossfade pipeline stable if FFmpeg cannot map an audio stream.
        cmd = [
            "ffmpeg", "-y",
            "-hide_banner", "-loglevel", "error",
            "-i", str(stream_url),
            "-t", str(segment_seconds),
            "-map", "0:v:0",
            "-map", "0:a:0?",
            "-vf", vf,
            "-af", f"aresample=44100,apad,atrim=0:{segment_seconds}",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "24",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            str(output_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and output_path.exists():
            # If the optional audio map produced a silent/no-audio file, rebuild
            # with a generated silent audio bed so acrossfade never breaks.
            if self.media_has_audio(output_path):
                return True

        silent_cmd = [
            "ffmpeg", "-y",
            "-hide_banner", "-loglevel", "error",
            "-i", str(stream_url),
            "-f", "lavfi",
            "-t", str(segment_seconds),
            "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", str(segment_seconds),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "24",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            str(output_path),
        ]

        result = subprocess.run(silent_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            self.safe_status(f"Live fragment render failed: {title[:60]}")
            return False
        return output_path.exists()

    def crossfade_segment_files(self, segment_paths, final_path):
        if not segment_paths:
            return None

        if len(segment_paths) == 1:
            shutil.copy2(segment_paths[0], final_path)
            return final_path

        transition = max(0.15, min(float(self.transition_seconds), self.segment_seconds / 2))
        step = self.segment_seconds - transition

        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
        for segment in segment_paths:
            cmd.extend(["-i", str(segment)])

        filter_parts = []
        last_v = "0:v"
        last_a = "0:a"

        for i in range(1, len(segment_paths)):
            v_out = f"v{i}"
            a_out = f"a{i}"
            offset = step * i
            filter_parts.append(
                f"[{last_v}][{i}:v]xfade=transition=fade:duration={transition}:offset={offset}[{v_out}]"
            )
            filter_parts.append(
                f"[{last_a}][{i}:a]acrossfade=d={transition}:c1=tri:c2=tri[{a_out}]"
            )
            last_v = v_out
            last_a = a_out

        cmd.extend([
            "-filter_complex", ";".join(filter_parts),
            "-map", f"[{last_v}]",
            "-map", f"[{last_a}]",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            str(final_path),
        ])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            self.safe_status("Crossfade render failed.")
            return None

        return final_path if final_path.exists() else None

    def render_stitched_live_dream(self, selected_items):
        if not selected_items:
            return None

        stamp = int(time.time())
        temp_dir = DREAM_RENDER_DIR / f"live_temp_{stamp}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        final_path = DREAM_RENDER_DIR / f"live_dream_{stamp}.mp4"

        try:
            segment_paths = []
            for index, item in enumerate(selected_items, start=1):
                if not self.is_playing:
                    return None

                title = item.get("title", "live signal")
                category = item.get("category", "live")
                self.safe_status(f"Rendering live fragment {index}/{len(selected_items)} [{category}]...")
                segment_path = temp_dir / f"live_segment_{index:02d}.mp4"

                if self.render_live_stream_for_stitch(item, segment_path):
                    segment_paths.append(segment_path)
                else:
                    self.safe_status(f"Skipping weak live fragment: {title[:55]}")

            if not segment_paths:
                return None

            self.safe_status("Crossfading live dream fragments...")
            return self.crossfade_segment_files(segment_paths, final_path)
        finally:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass


    def render_stitched_dream(self, selected_videos):
        if not selected_videos:
            return None

        stamp = int(time.time())
        temp_dir = DREAM_RENDER_DIR / f"temp_{stamp}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        final_path = DREAM_RENDER_DIR / f"dream_{stamp}.mp4"

        try:
            segment_paths = []
            for index, video_path in enumerate(selected_videos, start=1):
                if not self.is_playing:
                    return None
                category = self.detect_category(video_path)
                self.safe_status(f"Rendering fragment {index}/{len(selected_videos)} [{category}]...")
                segment_path = temp_dir / f"segment_{index:02d}.mp4"
                if self.render_segment_for_stitch(video_path, segment_path):
                    segment_paths.append(segment_path)

            if not segment_paths:
                return None

            if len(segment_paths) == 1:
                shutil.copy2(segment_paths[0], final_path)
                return final_path

            self.safe_status("Crossfading dream fragments...")
            transition = max(0.15, min(float(self.transition_seconds), self.segment_seconds / 2))
            step = self.segment_seconds - transition

            cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
            for segment in segment_paths:
                cmd.extend(["-i", str(segment)])

            filter_parts = []
            last_v = "0:v"
            last_a = "0:a"

            for i in range(1, len(segment_paths)):
                v_out = f"v{i}"
                a_out = f"a{i}"
                offset = step * i
                filter_parts.append(
                    f"[{last_v}][{i}:v]xfade=transition=fade:duration={transition}:offset={offset}[{v_out}]"
                )
                filter_parts.append(
                    f"[{last_a}][{i}:a]acrossfade=d={transition}:c1=tri:c2=tri[{a_out}]"
                )
                last_v = v_out
                last_a = a_out

            filter_complex = ";".join(filter_parts)
            cmd.extend([
                "-filter_complex", filter_complex,
                "-map", f"[{last_v}]",
                "-map", f"[{last_a}]",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                str(final_path),
            ])

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                self.safe_status("Crossfade render failed.")
                return None

            return final_path if final_path.exists() else None
        finally:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass


    # ------------------------------------------------------------------
    # WAITING STATIC / SIGNAL SEARCH
    def start_waiting_static(self, status_text="Tuning dream signal..."):
        """Show animated static in the video panel and loop a quiet static bed."""
        self.safe_status(status_text)
        self.static_visual_active = True
        self.static_audio_active = True

        self.after(0, self._show_video_static_canvas)
        self.after(0, self.animate_video_static)
        self.start_static_audio_loop()

    def stop_waiting_static(self):
        """Stop the render-wait static cleanly before playback begins."""
        self.static_visual_active = False
        self.static_audio_active = False
        self.stop_static_audio_loop()
        self.after(0, self._hide_video_static_canvas)

    def _show_video_static_canvas(self):
        try:
            self.video_placeholder.place_forget()
            self.video_static_canvas.lift()
            self.video_static_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        except Exception:
            pass

    def _hide_video_static_canvas(self):
        try:
            self.video_static_canvas.place_forget()
        except Exception:
            pass

    def animate_video_static(self):
        if not self.static_visual_active:
            return

        try:
            canvas = self.video_static_canvas
            canvas.delete("all")
            width = max(1, self.video_panel.winfo_width())
            height = max(1, self.video_panel.winfo_height())

            # Coarse horizontal static bands are much lighter than drawing every
            # pixel, but still read as analog snow/tuning noise.
            for y in range(0, height, 3):
                shade = random.randint(15, 230)
                color = f"#{shade:02x}{shade:02x}{shade:02x}"
                jitter = random.randint(-18, 18)
                canvas.create_line(jitter, y, width + jitter, y + random.randint(-1, 1), fill=color)

            # Add occasional scanline blocks/glitches so the wait has motion.
            for _ in range(20):
                x = random.randint(0, width)
                y = random.randint(0, height)
                w = random.randint(8, 70)
                h = random.randint(2, 14)
                shade = random.randint(40, 255)
                color = f"#{shade:02x}{shade:02x}{shade:02x}"
                canvas.create_rectangle(x, y, min(width, x + w), min(height, y + h), fill=color, outline="")

            if random.random() < 0.35:
                canvas.create_text(
                    width // 2,
                    height // 2,
                    text="SEARCHING DREAM SIGNAL",
                    fill=self.accent_color,
                    font=("Consolas", 22, "bold"),
                )

            self.after(45, self.animate_video_static)
        except Exception:
            self.after(80, self.animate_video_static)

    def start_static_audio_loop(self):
        if self.static_audio_stream is not None:
            return

        try:
            phase = {"value": 0.0}

            def callback(outdata, frames, time_info, status):
                if not self.static_audio_active:
                    outdata[:] = np.zeros((frames, 1), dtype=np.float32)
                    return

                t = (np.arange(frames, dtype=np.float32) + phase["value"]) / SAMPLE_RATE
                phase["value"] += frames

                # White noise + a quiet drifting tuning tone. Keep it low so it
                # adds atmosphere without becoming annoying.
                noise = np.random.normal(0, 0.045, frames).astype(np.float32)
                drift = 145 + 35 * np.sin(2 * np.pi * 0.17 * t)
                tone = np.sin(2 * np.pi * drift * t).astype(np.float32) * 0.025
                audio = np.clip(noise + tone, -0.12, 0.12).reshape(-1, 1)
                outdata[:] = audio

            self.static_audio_stream = sd.OutputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                callback=callback,
            )
            self.static_audio_stream.start()
        except Exception as e:
            self.static_audio_stream = None
            self.safe_status(f"Static audio unavailable: {e}")

    def stop_static_audio_loop(self):
        stream = self.static_audio_stream
        self.static_audio_stream = None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # DREAM PRESENTATION
    def update_recipe(self, original_mood, expanded_moods, selected_items, source="local vault"):
        lines = []
        lines.append(f"Source: {source}")
        lines.append(f"Input: {original_mood or 'random'}")
        lines.append(f"Expanded mood tags: {', '.join(expanded_moods) if expanded_moods else 'random'}")
        lines.append("")
        lines.append("Selected dream sequence:")

        for i, item in enumerate(selected_items, start=1):
            if isinstance(item, Path):
                lines.append(f"{i}. [{self.detect_category(item)}] {item.name[:90]}")
            else:
                title = item.get("title", "live signal")
                category = item.get("category", "live")
                term = item.get("search_term", "")
                lines.append(f"{i}. [{category}] {title[:75]}  <{term}>")

        self.after(0, lambda: self._set_recipe_text("\n".join(lines)))

    def _set_recipe_text(self, text):
        self.recipe_box.configure(state="normal")
        self.recipe_box.delete("1.0", "end")
        self.recipe_box.insert("1.0", text)
        self.recipe_box.configure(state="disabled")

    def signal_tuning_sequence(self):
        self.safe_status("Scanning dream frequencies...")
        self.play_tuning_tone(duration=0.8)
        self.static_tuning_effect(short=False)
        self.safe_status("Signal acquired.")
        self.play_tuning_tone(duration=0.18, frequency=880)

    def play_tuning_tone(self, duration=0.5, frequency=220):
        try:
            t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
            sweep = np.sin(2 * np.pi * (frequency + 80 * np.sin(2 * np.pi * 3 * t)) * t)
            noise = np.random.normal(0, 0.03, sweep.shape)
            audio = (sweep * 0.12 + noise).astype(np.float32)
            sd.play(audio, SAMPLE_RATE)
            sd.wait()
        except Exception:
            pass

    def static_tuning_effect(self, short=False):
        frames = 12 if short else 36
        self.safe_status("Analog tuning...")
        for _ in range(frames):
            self.wave_canvas.delete("all")
            width = 980
            height = 92
            for y in range(0, height, 4):
                shade = random.randint(80, 255)
                color = f"#{shade:02x}{shade:02x}{shade:02x}"
                self.wave_canvas.create_line(0, y, width, y + random.randint(-2, 2), fill=color)
            time.sleep(0.03)

    def attach_player_to_panel(self):
        """Attach VLC to the CustomTkinter video panel on Windows/Linux/macOS."""
        self.update_idletasks()
        handle = self.video_panel.winfo_id()

        try:
            if sys.platform.startswith("win"):
                self.player.set_hwnd(handle)
            elif sys.platform == "darwin":
                self.player.set_nsobject(handle)
            else:
                self.player.set_xwindow(handle)
        except Exception:
            # If attachment fails, VLC may open its own window. The app should
            # still keep running rather than crashing.
            pass

    def fit_video_to_panel(self):
        """Force VLC to fill the DreamStitch video box cleanly."""
        try:
            self.update_idletasks()
            width = max(1, self.video_panel.winfo_width())
            height = max(1, self.video_panel.winfo_height())

            # Scale 0 lets VLC calculate the correct panel-sized scale.
            self.player.video_set_scale(0)

            # Match the panel shape. Your panel is 960x540, so this is usually
            # 16:9, but reading the real widget size makes it more reliable.
            self.player.video_set_aspect_ratio(f"{width}:{height}")
        except Exception:
            pass

    def wait_for_video_ready(self, timeout=1.25):
        """Give VLC a short moment to load metadata without creating a long seam."""
        start = time.time()
        while time.time() - start < timeout and self.is_playing:
            state = self.player.get_state()
            if state in (vlc.State.Playing, vlc.State.Paused):
                return True
            time.sleep(0.03)
        return False

    def play_rendered_dream(self, dream_path):
        self.stop_waiting_static()
        self.video_placeholder.place_forget()

        media = self.vlc_instance.media_new(str(dream_path))
        self.player.set_media(media)
        self.attach_player_to_panel()

        self.player.play()
        self.wait_for_video_ready(timeout=2.0)
        self.fit_video_to_panel()
        self.after(150, self.fit_video_to_panel)
        self.after(500, self.fit_video_to_panel)

        while self.is_playing:
            state = self.player.get_state()
            if state in (vlc.State.Ended, vlc.State.Error, vlc.State.Stopped):
                break
            self.fit_video_to_panel()
            time.sleep(0.25)

    def play_video_segment(self, video_path):
        self.stop_waiting_static()
        self.video_placeholder.place_forget()

        media = self.vlc_instance.media_new(str(video_path))
        self.player.set_media(media)
        self.attach_player_to_panel()

        self.player.play()
        self.wait_for_video_ready()

        # Apply fitting a few times because VLC often ignores sizing until after
        # the first frames/metadata arrive.
        self.fit_video_to_panel()
        self.after(150, self.fit_video_to_panel)
        self.after(400, self.fit_video_to_panel)

        duration_ms = self.player.get_length()
        if duration_ms and duration_ms > self.segment_seconds * 1000 + 1500:
            max_start = duration_ms - (self.segment_seconds * 1000) - 500
            start_time = random.randint(0, max(0, max_start))
            self.player.set_time(start_time)

        start = time.time()
        while time.time() - start < self.segment_seconds and self.is_playing:
            self.fit_video_to_panel()
            time.sleep(0.25)

        # Stop only at the very end of the segment. The next segment starts
        # immediately in generate_dream(), which feels more like stitching than
        # the old stop/static/start rhythm.
        self.player.stop()

    def play_stream_segment(self, stream_url):
        if not stream_url:
            return

        self.stop_waiting_static()
        self.video_placeholder.place_forget()

        media = self.vlc_instance.media_new(stream_url)
        self.player.set_media(media)
        self.attach_player_to_panel()

        self.player.play()
        self.wait_for_video_ready(timeout=2.0)

        self.fit_video_to_panel()
        self.after(150, self.fit_video_to_panel)
        self.after(400, self.fit_video_to_panel)

        start = time.time()
        while time.time() - start < self.segment_seconds and self.is_playing:
            self.fit_video_to_panel()
            time.sleep(0.25)

        self.player.stop()

    def check_for_updates_thread(self):
        threading.Thread(target=self.check_for_updates, daemon=True).start()

    def check_for_updates(self):
        try:
            self.safe_status("Checking for DreamStitch updates...")
            result = check_for_update(status_callback=self.safe_status)

            message = result.get("message", "Update check finished.")

            if result.get("updated"):
                self.after(0, lambda: messagebox.showinfo(
                    "DreamStitch Updated",
                    message + "\n\nClose and reopen DreamStitch."
                ))
            else:
                self.after(0, lambda: messagebox.showinfo(
                    "DreamStitch Updates",
                    message
                ))

            self.safe_status(message)

        except Exception as e:
            error = f"Update check failed: {e}"
            self.safe_status(error)
            self.after(0, lambda: messagebox.showerror("Update Failed", error))


if __name__ == "__main__":
    app = DreamStitchApp()
    app.mainloop()
