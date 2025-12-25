from PIL import Image, ImageTk
import tkinter as tk
from tkinter import messagebox
import pygame
import os

# ===================== PATH HELPER =====================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def asset_path(*parts):
    return os.path.join(BASE_DIR, "assets", *parts)

# ===================== DATA & KONFIGURASI =====================

RAW_MAP = [
    "1101111111111111111111111",
    "1100111111111111111000001",
    "1100000011000000000011101",
    "1111111000011111111111101",
    "1111111111111000000000001",
    "1111000001111011111111111",
    "1111011000000011111111111",
    "1111011111111111111111111",
    "1100011100000001111111111",
    "1101111101100000000000001",
    "1100000001100001111111101",
    "1111111111100001111111101",
    "1111000000111111111100001",
    "1111011110110000001101111",
    "1000011110000111100001111",
    "1001111111111111111111111",
    "1011000000000001110000000",
    "1000011111111100000111111",
    "1111111111111111111111111",
]

ROWS = len(RAW_MAP)
COLS = len(RAW_MAP[0])
DUNGEON_MAP = [[int(c) for c in row] for row in RAW_MAP]

# ==================== GATE YANG TERKUNCI ====================

LOCKED_TILES = {
    (2, 7): "door1",
    (2, 17): "door2",
    (4, 20): "door3",
    (6, 8): "door4",
    (8, 11): "door5",
    (14, 18): "door6",
    (12, 9): "door7",
    (17, 1): "door8",
    (16, 10): "door9",
    (16, 24): "door10",
}

# ===================== INPUT SOAL-SOAL KUIS =====================

QUIZ_CONFIG = {
    "door1":  {"img": asset_path("kuis", "soal1.png"),  "answer": "C", "trigger": (2, 6)},
    "door2":  {"img": asset_path("kuis", "soal2.png"),  "answer": "E", "trigger": (2, 16)},
    "door3":  {"img": asset_path("kuis", "soal3.png"),  "answer": "C", "trigger": (4, 21)},
    "door4":  {"img": asset_path("kuis", "soal4.png"),  "answer": "E", "trigger": (6, 9)},
    "door5":  {"img": asset_path("kuis", "soal5.png"),  "answer": "A", "trigger": (8, 10)},
    "door6":  {"img": asset_path("kuis", "soal6.png"),  "answer": "B", "trigger": (14, 19)},
    "door7":  {"img": asset_path("kuis", "soal7.png"),  "answer": "B", "trigger": (13, 9)},
    "door8":  {"img": asset_path("kuis", "soal8.png"),  "answer": "B", "trigger": (16, 1)},
    "door9":  {"img": asset_path("kuis", "soal9.png"),  "answer": "C", "trigger": (16, 9)},
    "door10": {"img": asset_path("kuis", "soal10.png"), "answer": "B", "trigger": (16, 23)},
}

ZOOM = 2.5
BASE_TILE = 32
TILE = int(BASE_TILE * ZOOM)
MAX_ATTEMPT = 2

def grid_to_pixel(row, col):
    x = col * TILE + TILE // 2
    y = row * TILE + TILE // 2
    return x, y

# ===================== SOUND =====================

class SoundManager:
    def __init__(self):
        pygame.mixer.init()
        music_dir = asset_path("music")

        self.sounds = {
            "bs_menu":    os.path.join(music_dir, "bs_menu.mp3"),
            "bs_dungeon": os.path.join(music_dir, "bs_dungeon.mp3"),
            "correct":    os.path.join(music_dir, "correct.mp3"),
            "wrong":      os.path.join(music_dir, "wrong.mp3"),
            "win":        os.path.join(music_dir, "win.mp3"),
            "quiz":       os.path.join(music_dir, "quiz.mp3"),
            "start":      os.path.join(music_dir, "start.mp3"),
            "walk":       os.path.join(music_dir, "walk.mp3"),
            "score_p50":  os.path.join(music_dir, "score_p50.mp3"),
            "score_u50":  os.path.join(music_dir, "score_u50.mp3"),
        }

        self._cache = {}
        self.walk_channel = pygame.mixer.Channel(1)

    def play_bgm(self, name, volume=0.4):
        path = self.sounds.get(name)
        if not path:
            return
        pygame.mixer.music.load(path)
        pygame.mixer.music.set_volume(volume)
        pygame.mixer.music.play(loops=-1)

    def stop_bgm(self):
        pygame.mixer.music.stop()

    def switch_bgm(self, name, volume=0.4):
        self.stop_bgm()
        self.play_bgm(name, volume)

    def play_sfx(self, name, volume=None):
        path = self.sounds.get(name)
        if not path:
            return

        if name not in self._cache:
            self._cache[name] = pygame.mixer.Sound(path)
        snd = self._cache[name]

        if volume is None:
            if name == "correct":
                volume = 1.0
            elif name == "wrong":
                volume = 0.8
            elif name == "win":
                volume = 1.0
            elif name in ("score_p50", "score_u50"):
                volume = 0.8
            else:
                volume = 0.5

        snd.set_volume(volume)
        snd.play()

    def start_walk(self, volume=1.0):
        path = self.sounds.get("walk")
        if not path:
            return
        if "walk" not in self._cache:
            self._cache["walk"] = pygame.mixer.Sound(path)
        snd = self._cache["walk"]
        snd.set_volume(volume)
        if not self.walk_channel.get_busy():
            self.walk_channel.play(snd, loops=-1)

    def stop_walk(self):
        if self.walk_channel:
            self.walk_channel.stop()

# ===================== MAP & GAMEPLAY =====================

class MapView(tk.Frame):
    def __init__(self, master, sound_manager, back_to_menu_callback):
        super().__init__(master, bg="black")

        self.master = master
        self.sound = sound_manager
        self.back_to_menu_callback = back_to_menu_callback
        self.pack(fill="both", expand=True)

        self.score = 0
        self.quiz_active = False
        self.unlocked = set()
        self.passed_doors = set()

        # total waktu semua kuis (detik)
        self.total_quiz_time_used = 0
        # waktu awal tiap soal (untuk hitung durasi soal)
        self.current_quiz_start_time = 0

        # state overlay kuis & hasil
        self.quiz_image_id = None
        self.quiz_dim_id = None
        self.quiz_img_tk = None
        self.current_quiz_door = None
        self.quiz_attempts_left = 0

        self.result_frame = None
        self.result_img_tk = None

        # ====== TIMER QUIZ ======
        self.quiz_time_left = 0
        self.quiz_timer_id = None
        self.timer_label_id = None

        raw_map_img = Image.open(asset_path("map", "map.jpeg"))
        new_w = int(raw_map_img.width * ZOOM)
        new_h = int(raw_map_img.height * ZOOM)
        self.map_img = raw_map_img.resize((new_w, new_h), Image.BILINEAR)
        self.map_tk = ImageTk.PhotoImage(self.map_img)
        self.w, self.h = self.map_img.size

        self.view_w = 800
        self.view_h = 600
        self.master.geometry(f"{self.view_w}x{self.view_h}")

        self.canvas = tk.Canvas(
            self, width=self.view_w, height=self.view_h, highlightthickness=0
        )
        self.canvas.pack()
        self.canvas.create_image(0, 0, image=self.map_tk, anchor="nw")
        self.canvas.image = self.map_tk
        self.canvas.config(scrollregion=(0, 0, self.w, self.h))

        # ======= desain karakter =======
        base_size = 22
        char_size = int(base_size * ZOOM)
        size = (char_size, char_size)

        def load_char(filename):
            path = asset_path("character", filename)
            img = Image.open(path).resize(size, Image.BILINEAR)
            return ImageTk.PhotoImage(img)

        self.frames_right = [
            load_char("walk_right1.png"),
            load_char("walk_right2.png"),
            load_char("walk_right3.png"),
            load_char("walk_right4.png"),
        ]
        self.frames_left = [
            load_char("walk_left1.png"),
            load_char("walk_left2.png"),
            load_char("walk_left3.png"),
            load_char("walk_left4.png"),
        ]
        self.frames_updown = [
            load_char("down1.png"),
            load_char("down2.png"),
        ]
        self.frame_idle = load_char("diam1.png")

        self.current_frames = self.frames_updown
        self.current_index = 0

        self.row = 0
        self.col = 2
        self.x, self.y = grid_to_pixel(self.row, self.col)

        self.player = self.canvas.create_image(
            self.x, self.y, image=self.frame_idle, anchor="center"
        )

        # ====== HUD SCORE ======
        x_hud = self.canvas.canvasx(10)
        y_hud = self.canvas.canvasy(10)
        self.score_text_id = self.canvas.create_text(
            x_hud,
            y_hud,
            text=f"SCORE: {self.score}",
            font=("Times New Roman", 20, "bold"),
            fill="#F7DEDE",
            anchor="nw",
        )

        self.canvas.bind("<Button-1>", self.on_click)

        # ====== perintah tombol gerak =======
        for widget in (self.master, self.canvas):
            widget.bind("<Up>", self.move_up)
            widget.bind("<Down>", self.move_down)
            widget.bind("<Left>", self.move_left)
            widget.bind("<Right>", self.move_right)

    # ---------- util ----------

    def on_click(self, event):
        print("klik di:", event.x, event.y)

    def can_move(self, r, c):
        if not (0 <= r < ROWS and 0 <= c < COLS):
            return False
        if DUNGEON_MAP[r][c] == 1:
            return False

        key = (r, c)
        door = LOCKED_TILES.get(key)
        if door:
            if door not in self.unlocked:
                print("Gerbang", door, "masih terkunci!")
                return False
            if door in self.passed_doors:
                print("Gerbang", door, "tertutup lagi!")
                return False

        return True

    def update_score_display(self):
        if self.score_text_id:
            x_hud = self.canvas.canvasx(10)
            y_hud = self.canvas.canvasy(10)
            self.canvas.coords(self.score_text_id, x_hud, y_hud)
            self.canvas.itemconfig(self.score_text_id, text=f"SCORE: {self.score}")

    def update_camera(self):
        target_x = self.x - self.view_w // 2
        target_y = self.y - self.view_h // 2

        target_x = max(0, min(self.w - self.view_w, target_x))
        target_y = max(0, min(self.h - self.view_h, target_y))

        if self.w > 0:
            self.canvas.xview_moveto(target_x / self.w)
        if self.h > 0:
            self.canvas.yview_moveto(target_y / self.h)

        self.update_score_display()

    def next_frame(self):
        self.current_index = (self.current_index + 1) % len(self.current_frames)
        self.canvas.itemconfig(self.player, image=self.current_frames[self.current_index])

    def update_player_pos(self):
        self.x, self.y = grid_to_pixel(self.row, self.col)
        self.canvas.coords(self.player, self.x, self.y)
        self.next_frame()
        self.update_camera()
        self.check_events()

    # ======= Mengatur gerakan karakter =======

    def move_up(self, event):
        if self.quiz_active or self.result_frame:
            return
        nr, nc = self.row - 1, self.col
        if self.can_move(nr, nc):
            self.current_frames = self.frames_updown
            old_row, old_col = self.row, self.col
            self.row, self.col = nr, nc
            self.after_move(old_row, old_col)

    def move_down(self, event):
        if self.quiz_active or self.result_frame:
            return
        nr, nc = self.row + 1, self.col
        if self.can_move(nr, nc):
            self.current_frames = self.frames_updown
            old_row, old_col = self.row, self.col
            self.row, self.col = nr, nc
            self.after_move(old_row, old_col)

    def move_left(self, event):
        if self.quiz_active or self.result_frame:
            return
        nr, nc = self.row, self.col - 1
        if self.can_move(nr, nc):
            self.current_frames = self.frames_left
            old_row, old_col = self.row, self.col
            self.row, self.col = nr, nc
            self.after_move(old_row, old_col)

    def move_right(self, event):
        if self.quiz_active or self.result_frame:
            return
        nr, nc = self.row, self.col + 1
        if self.can_move(nr, nc):
            self.current_frames = self.frames_right
            old_row, old_col = self.row, self.col
            self.row, self.col = nr, nc
            self.after_move(old_row, old_col)

    def after_move(self, old_row, old_col):
        old_key = (old_row, old_col)
        new_key = (self.row, self.col)

        old_door = LOCKED_TILES.get(old_key)
        if old_door and old_door in self.unlocked:
            trig_r, trig_c = QUIZ_CONFIG[old_door]["trigger"]
            if new_key != (trig_r, trig_c):
                self.passed_doors.add(old_door)

        self.update_player_pos()

        if self.sound and not self.quiz_active and not self.result_frame:
            self.sound.play_sfx("walk")

    # ---------- BGM quiz ----------

    def start_quiz_bgm(self):
        if self.sound:
            self.sound.switch_bgm("quiz", volume=1.0)

    def end_quiz_bgm(self):
        if self.sound:
            self.sound.switch_bgm("bs_dungeon", volume=1.0)

    # ---------- TIMER QUIZ ----------

    def start_quiz_timer(self, seconds=30):
        seconds = max(15, min(60, seconds))
        self.quiz_time_left = seconds
        # simpan waktu awal soal ini (buat hitung durasi soal)
        self.current_quiz_start_time = seconds

        if self.quiz_timer_id is not None:
            self.after_cancel(self.quiz_timer_id)
            self.quiz_timer_id = None

        cx = self.canvas.canvasx(self.view_w // 2)
        cy = self.canvas.canvasy(self.view_h // 2) - 250

        time_text = f"TIME: {self.quiz_time_left}s"
        if self.timer_label_id is None:
            self.timer_label_id = self.canvas.create_text(
                cx,
                cy,
                text=time_text,
                font=("Times New Roman", 24, "bold"),
                fill="#F7DEDE"
            )
        else:
            self.canvas.coords(self.timer_label_id, cx, cy)
            self.canvas.itemconfig(self.timer_label_id, text=time_text)

        self.quiz_timer_id = self.after(1000, self.update_quiz_timer)

    def update_quiz_timer(self):
        if not self.quiz_active:
            return

        self.quiz_time_left -= 1

        if self.quiz_time_left <= 0:
            self.quiz_time_left = 0
            if self.timer_label_id is not None:
                self.canvas.itemconfig(self.timer_label_id, text="TIME: 0s")
            self.quiz_timer_id = None
            self.handle_quiz_timeout()
            return

        if self.timer_label_id is not None:
            self.canvas.itemconfig(
                self.timer_label_id,
                text=f"TIME: {self.quiz_time_left}s"
            )

        self.quiz_timer_id = self.after(1000, self.update_quiz_timer)

    def _add_current_quiz_time_to_total(self):
        """Tambah waktu terpakai soal sekarang ke total."""
        # durasi soal = waktu awal - sisa sekarang
        used = self.current_quiz_start_time - self.quiz_time_left
        if used < 0:
            used = 0
        self.total_quiz_time_used += used

    def handle_quiz_timeout(self):
        # timeout = semua kesempatan jawaban hangus (timer cuma 1x)
        self.quiz_attempts_left = 0

        # tambahkan durasi soal ini ke total
        self._add_current_quiz_time_to_total()

        messagebox.showwarning(
            "Waktu Habis",
            "Waktu habis! Kesempatan menjawab sudah habis."
        )

        if self.sound:
            door = self.current_quiz_door
            if door in ("door1", "door2", "door3", "door4"):
                self.sound.play_sfx("score_u50")
            else:
                self.sound.play_sfx("score_p50")

        self.close_quiz_overlay()
        self.show_result_screen()

    # ---------- QUIZ OVERLAY ----------

    def show_quiz_overlay(self, door_name, cfg):
        self.quiz_active = True
        self.current_quiz_door = door_name
        self.quiz_attempts_left = MAX_ATTEMPT  # 2 kali kesempatan jawaban

        if self.sound:
            self.sound.stop_walk()

        x1 = self.canvas.canvasx(0)
        y1 = self.canvas.canvasy(0)
        x2 = self.canvas.canvasx(self.view_w)
        y2 = self.canvas.canvasy(self.view_h)
        self.quiz_dim_id = self.canvas.create_rectangle(
            x1, y1, x2, y2, fill="black", stipple="gray50", outline=""
        )

        try:
            img = Image.open(cfg["img"])
        except Exception as e:
            messagebox.showerror(
                "Error", f"Gagal buka gambar quiz:\n{cfg['img']}\n{e}"
            )
            self.close_quiz_overlay()
            return

        self.quiz_img_tk = ImageTk.PhotoImage(img)

        cx = self.canvas.canvasx(self.view_w // 2)
        cy = self.canvas.canvasy(self.view_h // 2)

        self.quiz_image_id = self.canvas.create_image(
            cx, cy, image=self.quiz_img_tk, anchor="center"
        )

        self.master.bind("<Key>", self.on_quiz_key)

        # timer mulai SEKALI di sini
        self.start_quiz_timer(seconds=30)

    def on_quiz_key(self, event):
        k = event.keysym.upper()
        if k in ("A", "B", "C", "D", "E"):
            self.check_quiz_answer(k)

    def check_quiz_answer(self, answer):
        door = self.current_quiz_door
        if not door:
            return

        correct = QUIZ_CONFIG[door]["answer"]

        # ====== JAWABAN BENAR ======
        if answer == correct:
            # stop timer
            if self.quiz_timer_id is not None:
                self.after_cancel(self.quiz_timer_id)
                self.quiz_timer_id = None

            # tambah durasi soal ini ke total
            self._add_current_quiz_time_to_total()

            if self.sound:
                self.sound.play_sfx("correct")

            self.unlock_door(door)
            self.add_score(10)

            self.close_quiz_overlay()

            if door == "door10":
                if self.sound:
                    self.sound.play_sfx("win")
                self.show_result_screen(from_win=True)
            else:
                self.check_game_finished()

        # ====== JAWABAN SALAH ======
        else:
            self.quiz_attempts_left -= 1
            if self.sound:
                self.sound.play_sfx("wrong")

            # penalti waktu 5 detik
            self.quiz_time_left -= 5
            if self.quiz_time_left < 0:
                self.quiz_time_left = 0

            # update tulisan timer
            if self.timer_label_id is not None:
                self.canvas.itemconfig(
                    self.timer_label_id,
                    text=f"TIME: {self.quiz_time_left}s"
                )

            # kalau sesudah penalti waktunya habis, anggap timeout
            if self.quiz_time_left <= 0:
                self.handle_quiz_timeout()
                return

            # masih ada waktu
            if self.quiz_attempts_left > 0:
                messagebox.showwarning(
                    "Salah",
                    f"Sisa kesempatan: {self.quiz_attempts_left}\n"
                    "Waktu berkurang 5 detik!"
                )
            else:
                if self.sound:
                    if door in ("door1", "door2", "door3", "door4"):
                        self.sound.play_sfx("score_u50")
                    else:
                        self.sound.play_sfx("score_p50")

                # habis kesempatan tapi masih ada waktu → tambahkan durasi soal
                self._add_current_quiz_time_to_total()

                self.close_quiz_overlay()
                self.show_result_screen()

    def close_quiz_overlay(self):
        self.master.unbind("<Key>")

        if self.quiz_image_id is not None:
            self.canvas.delete(self.quiz_image_id)
        if self.quiz_dim_id is not None:
            self.canvas.delete(self.quiz_dim_id)

        self.quiz_image_id = None
        self.quiz_dim_id = None
        self.quiz_img_tk = None
        self.current_quiz_door = None
        self.quiz_active = False

        # stop timer & hapus label timer
        if self.quiz_timer_id is not None:
            self.after_cancel(self.quiz_timer_id)
            self.quiz_timer_id = None

        if self.timer_label_id is not None:
            self.canvas.delete(self.timer_label_id)
            self.timer_label_id = None

        self.quiz_time_left = 0

        self.end_quiz_bgm()

    # ---------- quiz & game state ----------

    def check_events(self):
        if self.quiz_active or self.result_frame:
            return

        for door_name, cfg in QUIZ_CONFIG.items():
            trig_r, trig_c = cfg["trigger"]
            if (self.row, self.col) == (trig_r, trig_c) and door_name not in self.unlocked:
                self.start_quiz_bgm()
                self.show_quiz_overlay(door_name, cfg)
                break

    def unlock_door(self, door_name):
        self.unlocked.add(door_name)

    def add_score(self, value):
        self.score += value
        self.update_score_display()

    def check_game_finished(self):
        all_doors = set(QUIZ_CONFIG.keys())
        if all_doors.issubset(self.unlocked):
            self.show_result_screen()

    def show_result_screen(self, from_win=False):
        if self.quiz_active:
            self.close_quiz_overlay()

        if getattr(self, "sound", None):
            self.sound.stop_bgm()
            if not from_win:
                if self.score >= 50:
                    self.sound.play_sfx("score_p50")
                else:
                    self.sound.play_sfx("score_u50")

        self.quiz_active = True

        if self.score == 100:
            img_path = asset_path("menu", "hasil1.png")
            if not os.path.exists(img_path):
                img_path = asset_path("menu", "hasil2.png")
        else:
            img_path = asset_path("menu", "hasil2.png")

        self.result_frame = tk.Frame(
            self, width=self.view_w, height=self.view_h, bg="black"
        )
        self.result_frame.place(x=0, y=0, width=self.view_w, height=self.view_h)
        self.result_frame.lift()

        try:
            img = Image.open(img_path)
            w, h = img.size

            self.result_img_tk = ImageTk.PhotoImage(img)

            canvas_result = tk.Canvas(
                self.result_frame,
                width=self.view_w,
                height=self.view_h,
                highlightthickness=0,
                bd=0,
            )
            canvas_result.pack(expand=True, fill="both")

            canvas_result.create_image(
                self.view_w // 2,
                self.view_h // 2,
                image=self.result_img_tk,
                anchor="center",
            )
            canvas_result.image = self.result_img_tk

        except Exception as e:
            messagebox.showerror("Error", f"Gagal buka gambar hasil: {e}")
            self.result_frame.destroy()
            return

        # Teks skor akhir
        canvas_result.create_text(
            w // 2,
            h - 80,
            text=f"Score: {self.score}",
            font=("Cascadia Code", 24, "bold"),
            fill="#F8F3D4",
        )

        # Total waktu semua kuis (detik)
        canvas_result.create_text(
            w // 2,
            h - 210,
            text=f"Total waktu kuis: {self.total_quiz_time_used}s",
            font=("Cascadia Code", 20, "bold"),
            fill="#F8F3D4",
        )

        canvas_result.create_text(
            w // 2,
            h - 245,
            text=f"Total IQ: {self.score}",
            font=("Cascadia Code", 24, "bold"),
            fill="#F8F3D4",
        )

        def back_to_menu():
            self.result_frame.destroy()
            self.result_frame = None
            self.destroy()
            if self.sound:
                self.sound.switch_bgm("bs_menu", volume=0.4)
            if callable(self.back_to_menu_callback):
                self.back_to_menu_callback()

        back_button = tk.Button(
            self.result_frame,
            text="BACK TO MENU",
            font=("Times New Roman", 16, "bold"),
            bg="#a97c50",
            fg="#f4edd2",
            border=0,
            cursor="hand2",
            command=back_to_menu,
        )
        back_button.place(x=w // 2 - 90, y=h - 180, width=180, height=40)

# ===================== MAIN GAME =====================

class DungeonGame:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("DUNGEON GAME")
        self.root.configure(bg="black")
        self.root.resizable(False, False)

        self.sound = SoundManager()
        self.sound.play_bgm("bs_menu", volume=0.4)

        self.menu_frame = None
        self.menu_bg_tk = None

        self.show_menu()

    def show_menu(self):
        if self.menu_frame is not None:
            self.menu_frame.destroy()

        menu_bg_img = Image.open(asset_path("menu", "menu.png"))
        self.menu_bg_tk = ImageTk.PhotoImage(menu_bg_img)
        mw, mh = menu_bg_img.size
        self.root.geometry(f"{mw}x{mh}")

        self.menu_frame = tk.Frame(self.root, bg="black")
        self.menu_frame.pack(fill="both", expand=True)

        canvas_menu = tk.Canvas(
            self.menu_frame, width=mw, height=mh,
            highlightthickness=0, bd=0
        )
        canvas_menu.pack(fill="both", expand=True)
        canvas_menu.create_image(0, 0, image=self.menu_bg_tk, anchor="nw")
        canvas_menu.image = self.menu_bg_tk

        info_img = Image.open(asset_path("menu", "info_icon.png")).convert("RGBA")
        info_img = info_img.resize((130, 100), Image.BILINEAR)
        self.info_icon_tk = ImageTk.PhotoImage(info_img)

        def show_info(event=None):
            messagebox.showinfo(
                "TUTORIAL GAME",
                "1. Gunakan tombol arah untuk bergerak.\n"
                "2. Masuki area merah untuk menjawab pertanyaan.\n"
                "3. Jawab dengan tekan huruf A, B, C, D, atau E di keyboard.\n"
                "4. Setiap soal diberi waktu 30 detik, ketika salah 5 detik hangus seketika.",
            )

        info_item = canvas_menu.create_image(
            -5, mh - 105, anchor="nw", image=self.info_icon_tk
        )
        canvas_menu.tag_bind(info_item, "<Button-1>", show_info)

        person_img = Image.open(asset_path("menu", "person_icon.png")).convert("RGBA")
        person_img = person_img.resize((66, 66), Image.BILINEAR)
        self.person_icon_tk = ImageTk.PhotoImage(person_img)

        def nama_pembuat(event=None):
            messagebox.showinfo(
                "MASTERS OF DUNGEON GAME",
                "1. Istu Maya Adelliya (005).\n"
                "2. Sonnya Gratia Plena Leo (138).\n"
                "3. Muhammad Rifky Ihwan (241).",
            )

        person_item = canvas_menu.create_image(
            705, mh - 87, anchor="nw", image=self.person_icon_tk
        )
        canvas_menu.tag_bind(person_item, "<Button-1>", nama_pembuat)

        start_button = tk.Button(
            self.menu_frame,
            text="START",
            font=("Times New Roman", 20, "bold"),
            border=0,
            bg="#a97c50",
            fg="white",
            cursor="hand2",
            command=self.show_map,
        )
        start_button.place(x=340, y=346, width=130, height=55)

        quit_button = tk.Button(
            self.menu_frame,
            text="QUIT",
            font=("Times New Roman", 20, "bold"),
            border=0,
            bg="#a97c50",
            fg="white",
            cursor="hand2",
            command=self.root.destroy,
        )
        quit_button.place(x=340, y=430, width=130, height=55)

    def show_map(self):
        self.sound.play_sfx("start")
        self.sound.switch_bgm("bs_dungeon", volume=0.4)

        if self.menu_frame is not None:
            self.menu_frame.pack_forget()

        self.map_view = MapView(
            self.root, self.sound, back_to_menu_callback=self.show_menu
        )

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    game = DungeonGame()
    game.run()