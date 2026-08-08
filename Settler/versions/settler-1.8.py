#!/usr/bin/env python3
"""Settler — CachyOS Post-Install Setup GUI"""

# === VERSIONING / ARCHIVE POLICY ===
# Old versions are kept in versions/ directory.
# When preparing a new release:
#   1. cp settler.py versions/settler-X.Y.py
#   2. Edit settler.py
#   3. Bump VERSION constant
#   4. Test
#
# Current live version is always settler.py in this directory.
# Symlinks (e.g. on Pulpit) point here.

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Gdk', '4.0')
gi.require_version('GdkPixbuf', '2.0')

from gi.repository import Gtk, Adw, GLib, Gdk, Gio, GdkPixbuf
import subprocess
import threading
import shutil
import tempfile
import stat
import re
import os
import glob
import sys
import pwd

# ──────────────────────────────────────────────────────────────
# WERSJA
# ──────────────────────────────────────────────────────────────

VERSION = "1.8"

# ──────────────────────────────────────────────────────────────
# CSS GLOBALNY
# ──────────────────────────────────────────────────────────────

GLOBAL_CSS = """
/* Base background using the theme variable.
   @define-color from ~/.config/gtk-4.0/gtk.css controls the system.
   Custom choices override via high priority provider.
   Prevents bleed by forcing the value.
*/
window,
window.background,
.background,
adw-application-window,
adw-application-window.background,
adw-overlay-split-view,
adw-toolbar-view,
overlay-split-view,
toolbar-view,
headerbar,
preferencespage,
adw-preferences-page,
clamp,
adw-clamp,
scrolledwindow,
viewport,
box,
grid,
.settler-root,
.settler-bg {
    background-color: @window_bg_color !important;
    background-image: none !important;
    box-shadow: none;
}

.settler-root {
    background-color: @window_bg_color !important;
    background-image: none !important;
}

.settler-bg {
    background-color: @window_bg_color !important;
    background-image: none !important;
}

.color-btn {
    min-width: 44px; min-height: 44px;
    border-radius: 22px;
    padding: 0;
    border: 3px solid transparent;
}
.color-btn:hover { border-color: white; }
.color-btn:checked { border-color: white; box-shadow: 0 0 0 2px black; }
.acc-blue        { background: #3584e4; }
.acc-teal        { background: #2190a4; }
.acc-green       { background: #3a944a; }
.acc-yellow      { background: #c88800; }
.acc-orange      { background: #e66100; }
.acc-red         { background: #e01b24; }
.acc-pink        { background: #d56199; }
.acc-purple      { background: #9141ac; }
.acc-slate       { background: #6f8396; }
.acc-navy        { background: #1a3a5c; }
.acc-cyan        { background: #00acc1; }
.acc-lime        { background: #7cb342; }
.acc-magenta2    { background: #d81b60; }
.acc-gold        { background: #f9a825; }
.acc-brown       { background: #6d4c41; }
.acc-indigo      { background: #3949ab; }
.acc-sea         { background: #00897b; }
.acc-deeppurple  { background: #6b21a8; }

.wp-thumb {
    border-radius: 8px;
    border: 3px solid transparent;
}
.wp-thumb:hover { border-color: @accent_color; }

.nav-row { padding: 4px 8px; border-radius: 6px; }
.nav-row:selected { background: @accent_bg_color; }

.tag-pacman { background: @blue_3; color: white; border-radius: 4px; padding: 2px 6px; font-size: 0.7em; }
.tag-aur    { background: @purple_3; color: white; border-radius: 4px; padding: 2px 6px; font-size: 0.7em; }
.installed-badge { background: @green_3; color: white; border-radius: 4px; padding: 2px 6px; font-size: 0.7em; }
"""

# ──────────────────────────────────────────────────────────────
# DANE
# ──────────────────────────────────────────────────────────────

PROGRAMS = [
    {"name": "Steam",             "pkg": "steam",                      "desc": "Platforma gamingowa Valve",           "source": "pacman"},
    {"name": "Brave Browser",     "pkg": "brave-bin",                  "desc": "Przeglądarka skupiona na prywatności","source": "aur"},
    {"name": "Firefox",           "pkg": "firefox",                    "desc": "Przeglądarka Mozilla",               "source": "pacman"},
    {"name": "VLC",               "pkg": "vlc",                        "desc": "Odtwarzacz multimedialny",           "source": "pacman"},
    {"name": "Discord",           "pkg": "discord",                    "desc": "Komunikator głosowy i tekstowy",     "source": "pacman"},
    {"name": "Spotify",           "pkg": "spotify",                    "desc": "Streaming muzyki",                   "source": "aur"},
    {"name": "OBS Studio",        "pkg": "obs-studio",                 "desc": "Nagrywanie i streaming",             "source": "pacman"},
    {"name": "GIMP",              "pkg": "gimp",                       "desc": "Edytor grafiki rastrowej",           "source": "pacman"},
    {"name": "Kdenlive",          "pkg": "kdenlive",                   "desc": "Edytor wideo",                       "source": "pacman"},
    {"name": "VS Code",           "pkg": "visual-studio-code-bin",     "desc": "Edytor kodu Microsoft",              "source": "aur"},
    {"name": "Heroic Games",      "pkg": "heroic-games-launcher-bin",  "desc": "Launcher Epic Games / GOG",          "source": "aur"},
    {"name": "Lutris",            "pkg": "lutris",                     "desc": "Manager gier Linux",                 "source": "pacman"},
    {"name": "ProtonUp-Qt",       "pkg": "protonup-qt",                "desc": "Manager wersji GE-Proton",           "source": "aur"},
    {"name": "LibreOffice",       "pkg": "libreoffice-fresh",          "desc": "Pakiet biurowy open source",         "source": "pacman"},
    {"name": "btop",              "pkg": "btop",                       "desc": "Monitor systemu (terminal)",         "source": "pacman"},
    {"name": "Ardour",            "pkg": "ardour",                     "desc": "DAW — Digital Audio Workstation",    "source": "pacman"},
    {"name": "Mixxx",             "pkg": "mixxx",                      "desc": "Oprogramowanie DJ",                  "source": "pacman"},
    {"name": "Firestorm",         "pkg": "firestorm-bin",              "desc": "Przeglądarka Second Life",           "source": "aur"},
    {"name": "OpenRGB",           "pkg": "openrgb",                    "desc": "Kontrola podświetlenia RGB",         "source": "aur"},
    {"name": "Flatpak",           "pkg": "flatpak",                    "desc": "System pakietów sandboxed",          "source": "pacman"},
    {"name": "GameMode",          "pkg": "gamemode",                   "desc": "Optymalizacja systemu dla gier",     "source": "pacman"},
    {"name": "MangoHud",          "pkg": "mangohud",                   "desc": "Overlay FPS/GPU/CPU w grach",        "source": "pacman"},
    {"name": "Wine",              "pkg": "wine",                       "desc": "Uruchamianie programów Windows",     "source": "pacman"},
    {"name": "Winetricks",        "pkg": "winetricks",                 "desc": "Skrypty konfiguracji Wine",          "source": "pacman"},
    {"name": "Oversteer",         "pkg": "oversteer",                  "desc": "Konfiguracja kierownicy Logitech",   "source": "aur"},
]

EXTENSIONS = [
    {"uuid": "user-theme@gnome-shell-extensions.gcampax.github.com",     "name": "User Themes",         "desc": "Własne motywy Shell",           "active": True},
    {"uuid": "show-desktop-button@amivaleo",                              "name": "Show Desktop Button", "desc": "Przycisk pokaż pulpit",         "active": True},
    {"uuid": "ding@rastersoft.com",                                       "name": "Desktop Icons NG",    "desc": "Ikony na pulpicie",              "active": True},
    {"uuid": "burn-my-windows@schneegans.github.com",                     "name": "Burn My Windows",     "desc": "Animacje otwierania okien",      "active": True},
    {"uuid": "lockkeys@vaina.lt",                                         "name": "Lock Keys",           "desc": "Wskaźnik Caps/Num Lock",        "active": True},
    {"uuid": "auto-move-windows@gnome-shell-extensions.gcampax.github.com","name":"Auto Move Windows",   "desc": "Auto-przenoszenie okien",        "active": True},
    {"uuid": "freon@UshakovVasilii_Github.yahoo.com",                     "name": "Freon",               "desc": "Temperatury w topbarze",         "active": True},
    {"uuid": "trayIconsReloaded@selfmade.pl",                             "name": "Tray Icons Reloaded", "desc": "Ikony w zasobniku systemowym",  "active": True},
    {"uuid": "ddterm@amezin.github.com",                                  "name": "ddterm",              "desc": "Dropdown terminal",              "active": True},
    {"uuid": "vertical-workspaces@G-dH.github.com",                      "name": "Vertical Workspaces", "desc": "Pionowe przestrzenie robocze",  "active": True},
    {"uuid": "EasyScreenCast@iacopodeenosee.gmail.com",                   "name": "EasyScreenCast",      "desc": "Nagrywanie ekranu",              "active": True},
    {"uuid": "gnome-ui-tune@itstime.tech",                                "name": "GNOME UI Tune",       "desc": "Poprawki UI GNOME",              "active": True},
    {"uuid": "advanced-weather@sanjai.com",                               "name": "Advanced Weather",    "desc": "Pogoda w topbarze",              "active": True},
    {"uuid": "reboottouefi@ubaygd.com",                                   "name": "Reboot to UEFI",      "desc": "Restart do UEFI z menu",        "active": True},
    {"uuid": "ShutdownTimer@deminder",                                    "name": "Shutdown Timer",      "desc": "Timer wyłączenia komputera",    "active": True},
    {"uuid": "gamemodeshellextension@trsnaqe.com",                        "name": "GameMode Shell",      "desc": "Integracja GameMode w Shell",    "active": True},
    {"uuid": "compiz-windows-effect@hermes83.github.com",                 "name": "Compiz Effect",       "desc": "Efekty galaretki okien",        "active": True},
    {"uuid": "system-rpg@conan513",                                       "name": "System RPG",          "desc": "Grywalizacja systemu",           "active": True},
    {"uuid": "fq@megh",                                                   "name": "fq",                  "desc": "Rozszerzenie fq",                "active": True},
    {"uuid": "blur-my-shell@aunetx",                                      "name": "Blur My Shell",       "desc": "Rozmycie tła Shell",             "active": False},
    {"uuid": "weatheroclock@CleoMenezesJr.github.io",                     "name": "Weather O'Clock",     "desc": "Zegar z pogodą",                 "active": False},
    {"uuid": "dash-to-dock@micxgx.gmail.com",                             "name": "Dash to Dock",        "desc": "Dock na wzór macOS",             "active": False},
    {"uuid": "dash-to-panel@jderose9.github.com",                         "name": "Dash to Panel",       "desc": "Pasek zadań Windows-like",      "active": False},
]

ICON_THEMES = [
    {"name": "Adwaita (domyślny)",  "pkg": None,                          "value": "Adwaita"},
    {"name": "Papirus",             "pkg": "papirus-icon-theme",          "value": "Papirus"},
    {"name": "Papirus Dark",        "pkg": "papirus-icon-theme",          "value": "Papirus-Dark"},
    {"name": "Papirus Light",       "pkg": "papirus-icon-theme",          "value": "Papirus-Light"},
    {"name": "Tela",                "pkg": "tela-icon-theme-git",         "value": "Tela"},
    {"name": "Tela Dark",           "pkg": "tela-icon-theme-git",         "value": "Tela-dark"},
    {"name": "Tela Blue",           "pkg": "tela-icon-theme-git",         "value": "Tela-blue"},
    {"name": "Numix Circle",        "pkg": "numix-circle-icon-theme-git", "value": "Numix-Circle"},
    {"name": "Flat Remix Blue",     "pkg": "flat-remix",                  "value": "Flat-Remix-Blue"},
    {"name": "Flat Remix Green",    "pkg": "flat-remix",                  "value": "Flat-Remix-Green"},
    {"name": "Flat Remix Red",      "pkg": "flat-remix",                  "value": "Flat-Remix-Red"},
    {"name": "Candy Icons",         "pkg": "candy-icons-git",             "value": "candy-icons"},
    {"name": "Reversal Blue",       "pkg": "reversal-icon-theme-git",     "value": "Reversal-blue"},
    {"name": "Fluent Dark",         "pkg": "fluent-icon-theme-git",       "value": "Fluent-dark"},
    {"name": "Fluent Light",        "pkg": "fluent-icon-theme-git",       "value": "Fluent"},
    {"name": "Yaru",                "pkg": "yaru-gtk-theme",              "value": "Yaru"},
    {"name": "WhiteSur Icons",      "pkg": "whitesur-icon-theme",         "value": "WhiteSur"},
    {"name": "WhiteSur Icons Dark", "pkg": "whitesur-icon-theme",         "value": "WhiteSur-dark"},
]

CURSOR_THEMES = [
    {"name": "Adwaita (domyślny)",       "pkg": None,                  "value": "Adwaita"},
    {"name": "Bibata Modern Classic",    "pkg": "bibata-cursor-theme", "value": "Bibata-Modern-Classic"},
    {"name": "Bibata Modern Ice",        "pkg": "bibata-cursor-theme", "value": "Bibata-Modern-Ice"},
    {"name": "Bibata Modern Amber",      "pkg": "bibata-cursor-theme", "value": "Bibata-Modern-Amber"},
    {"name": "Bibata Original Classic",  "pkg": "bibata-cursor-theme", "value": "Bibata-Original-Classic"},
    {"name": "Oreo Blue",                "pkg": "oreo-cursors-git",    "value": "oreo_blue_cursors"},
    {"name": "Oreo Pink",                "pkg": "oreo-cursors-git",    "value": "oreo_pink_cursors"},
    {"name": "Oreo White",               "pkg": "oreo-cursors-git",    "value": "oreo_white_cursors"},
    {"name": "Oreo Red",                 "pkg": "oreo-cursors-git",    "value": "oreo_red_cursors"},
    {"name": "Vimix",                    "pkg": "vimix-cursors",       "value": "Vimix-cursors"},
    {"name": "Vimix White",              "pkg": "vimix-cursors",       "value": "Vimix-white-cursors"},
    {"name": "Breeze",                   "pkg": "breeze",              "value": "breeze_cursors"},
    {"name": "Capitaine",                "pkg": "capitaine-cursors",   "value": "capitaine-cursors"},
    {"name": "Nordzy",                   "pkg": "nordzy-cursors-git",  "value": "Nordzy-cursors"},
    {"name": "phinger",                  "pkg": "phinger-cursors",     "value": "phinger-cursors"},
    {"name": "Simp1e",                   "pkg": "simp1e-cursors",      "value": "Simp1e"},
    {"name": "macOS Monterey",           "pkg": "macos-monterey-cursors", "value": "macOS Monterey"},
]

GTK_THEMES = [
    {"name": "Adwaita (domyślny)",  "pkg": None,                        "shell": "",                          "gtk": "Adwaita"},
    {"name": "Adwaita Dark",        "pkg": None,                        "shell": "",                          "gtk": "Adwaita-dark"},
    {"name": "WhiteSur Light",      "pkg": "whitesur-gtk-theme",        "shell": "WhiteSur-Light",            "gtk": "WhiteSur-Light"},
    {"name": "WhiteSur Dark",       "pkg": "whitesur-gtk-theme",        "shell": "WhiteSur-Dark",             "gtk": "WhiteSur-Dark"},
    {"name": "Orchis Light",        "pkg": "orchis-theme",              "shell": "Orchis",                    "gtk": "Orchis"},
    {"name": "Orchis Dark",         "pkg": "orchis-theme",              "shell": "Orchis-Dark",               "gtk": "Orchis-Dark"},
    {"name": "Colloid Light",       "pkg": "colloid-gtk-theme-git",     "shell": "Colloid",                   "gtk": "Colloid"},
    {"name": "Colloid Dark",        "pkg": "colloid-gtk-theme-git",     "shell": "Colloid-Dark",              "gtk": "Colloid-Dark"},
    {"name": "Marble Light",        "pkg": "marble-shell-theme-git",    "shell": "Marble-light",              "gtk": "adw-gtk3"},
    {"name": "Marble Dark",         "pkg": "marble-shell-theme-git",    "shell": "Marble-dark",               "gtk": "adw-gtk3-dark"},
    {"name": "Tokyonight Dark",     "pkg": "tokyonight-gtk-theme-git",  "shell": "Tokyonight-Dark-BL",        "gtk": "Tokyonight-Dark-BL"},
    {"name": "Catppuccin Mocha",    "pkg": "catppuccin-gtk-theme-mocha","shell": "catppuccin-mocha-blue-dark","gtk": "catppuccin-mocha-blue-dark"},
    {"name": "Gruvbox Dark",        "pkg": "gruvbox-gtk-theme",         "shell": "gruvbox-dark",              "gtk": "gruvbox-dark"},
    {"name": "Nordic",              "pkg": "nordic-theme",              "shell": "Nordic",                    "gtk": "Nordic"},
]

ACCENT_COLORS = [
    # Tylko oficjalne akcenty systemowe (gsettings + Shell + wszystkie app)
    {"name": "Niebieski",      "css": "acc-blue",        "value": "blue",   "hex": "#3584e4", "official": True},
    {"name": "Turkusowy",      "css": "acc-teal",        "value": "teal",   "hex": "#2190a4", "official": True},
    {"name": "Zielony",        "css": "acc-green",       "value": "green",  "hex": "#3a944a", "official": True},
    {"name": "Żółty",          "css": "acc-yellow",      "value": "yellow", "hex": "#c88800", "official": True},
    {"name": "Pomarańczowy",   "css": "acc-orange",      "value": "orange", "hex": "#e66100", "official": True},
    {"name": "Czerwony",       "css": "acc-red",         "value": "red",    "hex": "#e01b24", "official": True},
    {"name": "Różowy",         "css": "acc-pink",        "value": "pink",   "hex": "#d56199", "official": True},
    {"name": "Fioletowy",      "css": "acc-purple",      "value": "purple", "hex": "#9141ac", "official": True},
    {"name": "Szary",          "css": "acc-slate",       "value": "slate",  "hex": "#6f8396", "official": True},
]

NAV_ITEMS = [
    ("Programy",     "application-x-executable-symbolic",       "programs"),
    ("Wygląd",       "preferences-desktop-appearance-symbolic",  "appearance"),
    ("System",       "preferences-system-symbolic",              "system"),
    ("Gaming",       "applications-games-symbolic",              "gaming"),
    ("Rozszerzenia", "application-x-addon-symbolic",             "extensions"),
    ("Keyd",         "input-keyboard-symbolic",                  "keyd"),
]

# ──────────────────────────────────────────────────────────────
# NARZĘDZIA
# ──────────────────────────────────────────────────────────────

def is_pkg_installed(pkg):
    r = subprocess.run(['pacman', '-Q', pkg], capture_output=True)
    return r.returncode == 0

def gsettings_get(schema, key):
    r = subprocess.run(['gsettings', 'get', schema, key], capture_output=True, text=True)
    return r.stdout.strip().strip("'")

def gsettings_set(schema, key, value):
    subprocess.run(['gsettings', 'set', schema, key, value])

def get_wallpapers():
    paths = []
    dirs = [
        '/usr/share/backgrounds',
        '/usr/share/wallpapers',
        os.path.expanduser('~/.local/share/backgrounds'),
        os.path.expanduser('~/Pictures'),
        os.path.expanduser('~/Pictures/Wallpapers'),
    ]
    exts = ['*.jpg', '*.jpeg', '*.png', '*.webp', '*.JPG', '*.PNG']
    seen = set()
    for d in dirs:
        if os.path.exists(d):
            for ext in exts:
                for p in glob.glob(os.path.join(d, '**', ext), recursive=True):
                    if p not in seen:
                        seen.add(p)
                        paths.append(p)
    return sorted(paths)

# ──────────────────────────────────────────────────────────────
# DIALOG HASŁA
# ──────────────────────────────────────────────────────────────

class AskPasswordDialog(Adw.Dialog):
    """Graficzny dialog prośby o hasło sudo."""
    def __init__(self, callback):
        super().__init__()
        self.set_title("Uwierzytelnienie")
        self.set_content_width(380)
        self.callback = callback
        self._password = None

        tv = Adw.ToolbarView()
        hb = Adw.HeaderBar()
        tv.add_top_bar(hb)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        vbox.set_margin_top(20)
        vbox.set_margin_bottom(20)
        vbox.set_margin_start(20)
        vbox.set_margin_end(20)

        icon = Gtk.Image.new_from_icon_name('dialog-password-symbolic')
        icon.set_pixel_size(48)
        vbox.append(icon)

        title = Gtk.Label(label="Wymagane hasło sudo")
        title.add_css_class('title-2')
        vbox.append(title)

        subtitle = Gtk.Label(label="Podaj hasło użytkownika aby zainstalować pakiety.")
        subtitle.add_css_class('dim-label')
        subtitle.set_wrap(True)
        subtitle.set_max_width_chars(40)
        vbox.append(subtitle)

        self.entry = Gtk.PasswordEntry()
        self.entry.set_show_peek_icon(True)
        self.entry.set_placeholder_text("Hasło...")
        self.entry.connect('activate', self._on_ok)
        vbox.append(self.entry)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button(label="Anuluj")
        cancel_btn.connect('clicked', lambda _: self.close())
        btn_box.append(cancel_btn)

        ok_btn = Gtk.Button(label="OK")
        ok_btn.add_css_class('suggested-action')
        ok_btn.connect('clicked', self._on_ok)
        btn_box.append(ok_btn)

        vbox.append(btn_box)
        tv.set_content(vbox)
        self.set_child(tv)

        GLib.idle_add(self.entry.grab_focus)

    def _on_ok(self, *_):
        self._password = self.entry.get_text()
        self.close()
        if self._password is not None:
            self.callback(self._password)


# ──────────────────────────────────────────────────────────────
# DIALOG INSTALACJI
# ──────────────────────────────────────────────────────────────

class InstallDialog(Adw.Dialog):
    def __init__(self, commands, title="Instalacja", parent=None):
        super().__init__()
        self.set_title(title)
        self.set_content_width(640)
        self.set_content_height(480)
        self.commands = commands
        self._parent = parent
        self._sudo_password = None

        tv = Adw.ToolbarView()
        hb = Adw.HeaderBar()
        tv.add_top_bar(hb)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.set_margin_top(12)
        vbox.set_margin_bottom(12)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)

        self.status = Gtk.Label(label="Inicjalizacja…")
        self.status.set_halign(Gtk.Align.START)
        self.status.add_css_class('heading')
        vbox.append(self.status)

        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)
        self.progress.set_text("0 / 0")
        vbox.append(self.progress)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        self.output = Gtk.TextView()
        self.output.set_editable(False)
        self.output.set_monospace(True)
        self.output.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.buf = self.output.get_buffer()
        scroll.set_child(self.output)
        vbox.append(scroll)

        self.close_btn = Gtk.Button(label="Zamknij")
        self.close_btn.add_css_class('suggested-action')
        self.close_btn.set_sensitive(False)
        self.close_btn.connect('clicked', lambda *_: self.close())
        vbox.append(self.close_btn)

        tv.set_content(vbox)
        self.set_child(tv)

        # Sprawdź czy komendy wymagają sudo
        needs_sudo = any(
            'pkexec' in cmd or 'sudo' in cmd
            for _, cmd in commands
        )
        if needs_sudo:
            GLib.idle_add(self._ask_password)
        else:
            threading.Thread(target=self._run, args=(None,), daemon=True).start()

    def _ask_password(self):
        pwd_dialog = AskPasswordDialog(self._start_with_password)
        pwd_dialog.present(self._parent)

    def _start_with_password(self, password):
        self._sudo_password = password
        threading.Thread(target=self._run, args=(password,), daemon=True).start()

    def _run(self, password):
        # Tworzymy tymczasowy skrypt askpass jeśli jest hasło
        askpass_path = None
        env = os.environ.copy()
        if password:
            fd, askpass_path = tempfile.mkstemp(suffix='.sh', prefix='settler_')
            with os.fdopen(fd, 'w') as f:
                safe_pw = password.replace("'", "'\\''")
                f.write(f"#!/bin/sh\nprintf '%s\\n' '{safe_pw}'\n")
            os.chmod(askpass_path, stat.S_IRWXU)
            env['SUDO_ASKPASS'] = askpass_path

        try:
            total = len(self.commands)
            for i, (label, cmd) in enumerate(self.commands):
                GLib.idle_add(self.status.set_text, f"[{i+1}/{total}] {label}")
                GLib.idle_add(self.progress.set_text, f"{i+1} / {total}")

                # Zamień pkexec na sudo --askpass
                if 'pkexec' in cmd and password:
                    cmd = ['sudo', '--askpass'] + [c for c in cmd if c != 'pkexec']

                GLib.idle_add(self._append, f"\n$ {' '.join(cmd)}\n")
                try:
                    proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        env=env,
                        text=False
                    )
                    for raw_line in proc.stdout:
                        try:
                            line = raw_line.decode('utf-8', errors='replace')
                        except Exception:
                            line = str(raw_line)
                        GLib.idle_add(self._append, line)
                    proc.wait()
                except Exception as e:
                    GLib.idle_add(self._append, f"[BŁĄD] {e}\n")
                GLib.idle_add(self.progress.set_fraction, (i + 1) / total)
        finally:
            if askpass_path and os.path.exists(askpass_path):
                os.unlink(askpass_path)

        GLib.idle_add(self.status.set_text, "✓ Zakończono!")
        GLib.idle_add(self._append, "\n✓ Wszystkie operacje zakończone.\n")
        GLib.idle_add(self.close_btn.set_sensitive, True)

    def _append(self, text):
        it = self.buf.get_end_iter()
        self.buf.insert(it, text)
        adj = self.output.get_vadjustment()
        GLib.idle_add(adj.set_value, adj.get_upper())
        return False

# ──────────────────────────────────────────────────────────────
# STRONA: PROGRAMY
# ──────────────────────────────────────────────────────────────

class ProgramsPage(Adw.PreferencesPage):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.checks = {}
        self.set_title("Programy")
        self.set_icon_name("application-x-executable-symbolic")

        group = Adw.PreferencesGroup()
        group.set_title("Wybierz programy do zainstalowania")
        group.set_description("Zaznaczone zostaną zainstalowane. Już zainstalowane są wyszarzone.")

        for prog in PROGRAMS:
            row = Adw.ActionRow()
            row.set_title(prog['name'])

            installed = is_pkg_installed(prog['pkg'])
            badge = Gtk.Label()
            badge.set_margin_start(6)
            badge.set_valign(Gtk.Align.CENTER)

            if installed:
                badge.set_label("✓")
                badge.add_css_class('installed-badge')
                row.set_subtitle(prog['desc'])
            else:
                src_class = 'tag-pacman' if prog['source'] == 'pacman' else 'tag-aur'
                tag = Gtk.Label(label=prog['source'])
                tag.add_css_class(src_class)
                tag.set_valign(Gtk.Align.CENTER)
                row.add_suffix(tag)
                row.set_subtitle(prog['desc'])

            check = Gtk.CheckButton()
            check.set_active(not installed)
            check.set_sensitive(not installed)
            self.checks[prog['pkg']] = (check, prog['source'])

            row.add_suffix(badge if installed else check)
            if not installed:
                row.set_activatable_widget(check)
            group.add(row)

        self.add(group)

        btn_group = Adw.PreferencesGroup()
        install_row = Adw.ActionRow()
        install_row.set_title("Zainstaluj zaznaczone programy")
        install_row.set_subtitle("pacman dla oficjalnych, paru dla AUR")
        btn = Gtk.Button(label="Zainstaluj zaznaczone")
        btn.add_css_class('suggested-action')
        btn.set_valign(Gtk.Align.CENTER)
        btn.connect('clicked', self.on_install)
        install_row.add_suffix(btn)
        btn_group.add(install_row)
        self.add(btn_group)

    def on_install(self, _):
        pacman_pkgs, aur_pkgs = [], []
        for pkg, (check, source) in self.checks.items():
            if check.get_active():
                (pacman_pkgs if source == 'pacman' else aur_pkgs).append(pkg)

        if not pacman_pkgs and not aur_pkgs:
            return

        cmds = []
        if pacman_pkgs:
            cmds.append(("Instalacja (pacman)", ['pkexec', 'pacman', '-S', '--noconfirm'] + pacman_pkgs))
        if aur_pkgs:
            cmds.append(("Instalacja AUR (paru)", ['paru', '-S', '--noconfirm'] + aur_pkgs))

        d = InstallDialog(cmds, 'Instalacja programów', parent=self.win)
        d.present(self.win)

# ──────────────────────────────────────────────────────────────
# STRONA: WYGLĄD
# ──────────────────────────────────────────────────────────────

class AppearancePage(Adw.PreferencesPage):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.set_title("Wygląd")
        self.set_icon_name("preferences-desktop-appearance-symbolic")

        # ─── Tryb ciemny/jasny ───────────────────
        theme_group = Adw.PreferencesGroup()
        theme_group.set_title("Styl interfejsu")

        dark_row = Adw.SwitchRow()
        dark_row.set_title("Ciemny motyw")
        dark_row.set_subtitle("Przełącza między jasnym a ciemnym")
        color_scheme = gsettings_get('org.gnome.desktop.interface', 'color-scheme')
        dark_row.set_active('dark' in color_scheme)
        dark_row.connect('notify::active', self._toggle_dark)
        theme_group.add(dark_row)
        self.add(theme_group)

        # ─── Kolor wyróżnienia ────────────────────
        accent_group = Adw.PreferencesGroup()
        accent_group.set_title("Kolor wyróżnienia")
        accent_group.set_description(
            "✓ 9 pierwszych kolorów = systemowe (Shell, przełączniki, menu zasilania, wszystkie aplikacje)\n"
            "ℹ Pozostałe + Własny = tylko GTK4 apps (nie Shell)")

        flow = Gtk.FlowBox()
        flow.set_max_children_per_line(10)
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_row_spacing(8)
        flow.set_column_spacing(8)
        flow.set_margin_top(10)
        flow.set_margin_bottom(10)
        flow.set_margin_start(10)
        flow.set_margin_end(10)
        flow.set_homogeneous(True)

        current_accent = gsettings_get('org.gnome.desktop.interface', 'accent-color')
        for ac in ACCENT_COLORS:
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            btn = Gtk.Button()
            btn.add_css_class('color-btn')
            btn.add_css_class(ac['css'])
            btn.set_tooltip_text(ac['name'])
            btn.connect('clicked', self._set_accent, ac)
            lbl = Gtk.Label(label=ac['name'])
            lbl.add_css_class('caption')
            lbl.set_max_width_chars(9)
            vbox.append(btn)
            vbox.append(lbl)
            flow.append(vbox)

        accent_group.set_description("Kolory akcentu systemu — działają w całym GNOME (Shell + aplikacje)")
        accent_group.add(flow)
        self.add(accent_group)

        # ─── Ikony ────────────────────────────────
        icon_group = Adw.PreferencesGroup()
        icon_group.set_title("Motyw ikon")

        self.icon_combo = Adw.ComboRow()
        self.icon_combo.set_title("Pakiet ikon")
        icon_model = Gtk.StringList()
        for t in ICON_THEMES:
            icon_model.append(t['name'])
        self.icon_combo.set_model(icon_model)
        current_icons = gsettings_get('org.gnome.desktop.interface', 'icon-theme')
        for i, t in enumerate(ICON_THEMES):
            if t['value'] == current_icons:
                self.icon_combo.set_selected(i)
                break

        icon_btn = Gtk.Button(label="Zastosuj")
        icon_btn.add_css_class('suggested-action')
        icon_btn.set_valign(Gtk.Align.CENTER)
        icon_btn.connect('clicked', self._apply_icons)
        self.icon_combo.add_suffix(icon_btn)
        icon_group.add(self.icon_combo)
        self.add(icon_group)

        # ─── Kursory ──────────────────────────────
        cursor_group = Adw.PreferencesGroup()
        cursor_group.set_title("Motyw kursora")

        self.cursor_combo = Adw.ComboRow()
        self.cursor_combo.set_title("Kursor myszy")
        cursor_model = Gtk.StringList()
        for t in CURSOR_THEMES:
            cursor_model.append(t['name'])
        self.cursor_combo.set_model(cursor_model)
        current_cursor = gsettings_get('org.gnome.desktop.interface', 'cursor-theme')
        for i, t in enumerate(CURSOR_THEMES):
            if t['value'] == current_cursor:
                self.cursor_combo.set_selected(i)
                break

        cursor_btn = Gtk.Button(label="Zastosuj")
        cursor_btn.add_css_class('suggested-action')
        cursor_btn.set_valign(Gtk.Align.CENTER)
        cursor_btn.connect('clicked', self._apply_cursor)
        self.cursor_combo.add_suffix(cursor_btn)
        cursor_group.add(self.cursor_combo)

        # Rozmiar kursora
        size_row = Adw.ActionRow()
        size_row.set_title("Rozmiar kursora")
        size_row.set_subtitle("px — domyślnie 24")

        size_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        size_box.set_valign(Gtk.Align.CENTER)

        self.cursor_size_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 16, 96, 8)
        self.cursor_size_scale.set_size_request(480, -1)
        self.cursor_size_scale.set_draw_value(True)
        self.cursor_size_scale.set_value_pos(Gtk.PositionType.RIGHT)
        for v in [16, 24, 32, 48, 64, 96]:
            self.cursor_size_scale.add_mark(v, Gtk.PositionType.BOTTOM, str(v))
        try:
            cur_size = int(gsettings_get('org.gnome.desktop.interface', 'cursor-size'))
            self.cursor_size_scale.set_value(cur_size)
        except Exception:
            self.cursor_size_scale.set_value(24)

        size_apply = Gtk.Button(label="Ustaw")
        size_apply.add_css_class('suggested-action')
        size_apply.set_valign(Gtk.Align.CENTER)
        size_apply.connect('clicked', self._apply_cursor_size)

        size_box.append(self.cursor_size_scale)
        size_box.append(size_apply)
        size_row.add_suffix(size_box)
        cursor_group.add(size_row)
        self.add(cursor_group)

        # ─── Powłoka GNOME Shell ────────────────────
        shell_group = Adw.PreferencesGroup()
        shell_group.set_title("Powłoka GNOME (Shell)")
        shell_group.set_description("Wygląd panelu, menu systemowego i powiadomień — wymaga rozszerzenia User Themes")

        self.shell_combo = Adw.ComboRow()
        self.shell_combo.set_title("Motyw Shell")
        shell_model = Gtk.StringList()
        shell_model.append("Domyślny (brak)")
        for t in GTK_THEMES:
            if t['shell']:
                shell_model.append(t['name'])
        self.shell_combo.set_model(shell_model)

        # Wczytaj aktualny motyw Shell
        try:
            current_shell = gsettings_get('org.gnome.shell.extensions.user-theme', 'name')
            if current_shell:
                for i, t in enumerate(GTK_THEMES):
                    if t.get('shell') == current_shell:
                        self.shell_combo.set_selected(i + 1)
                        break
        except Exception:
            pass

        shell_btn = Gtk.Button(label="Zastosuj")
        shell_btn.add_css_class('suggested-action')
        shell_btn.set_valign(Gtk.Align.CENTER)
        shell_btn.connect('clicked', self._apply_shell)
        self.shell_combo.add_suffix(shell_btn)
        shell_group.add(self.shell_combo)
        self.add(shell_group)

        # ─── Tapety ───────────────────────
        self._extra_wp_dirs = []

        wp_group = Adw.PreferencesGroup()
        wp_group.set_title("Tapety")
        wp_group.set_description("Kliknij tapetę żeby ją ustawić jako tło")

        # Skalowanie tapety
        self._wp_scale_options = [
            ("Wypełnij (fill)",          "zoom"),
            ("Dopasuj (fit)",             "scaled"),
            ("Rozciągnij (stretch)",     "stretched"),
            ("Wyśrodkuj (center)",       "centered"),
            ("Kafelkuj (tile)",          "wallpaper"),
            ("Rozciągnij na wszystkie",  "spanned"),
        ]
        scale_row = Adw.ActionRow()
        scale_row.set_title("Skalowanie tapety")
        scale_row.set_subtitle("Sposób dopasowania tapety do ekranu")
        scale_model = Gtk.StringList()
        for name, _ in self._wp_scale_options:
            scale_model.append(name)
        self.wp_scale_combo = Gtk.DropDown(model=scale_model)
        self.wp_scale_combo.set_valign(Gtk.Align.CENTER)
        # Ustaw aktualną wartość
        cur_opt = gsettings_get('org.gnome.desktop.background', 'picture-options')
        for i, (_, val) in enumerate(self._wp_scale_options):
            if val == cur_opt:
                self.wp_scale_combo.set_selected(i)
                break
        self.wp_scale_combo.connect('notify::selected', self._apply_wp_scale)
        scale_row.add_suffix(self.wp_scale_combo)
        wp_group.add(scale_row)

        # Przycisk dodania katalogu
        dir_row = Adw.ActionRow()
        dir_row.set_title("Dodaj katalog z tapetami")
        dir_row.set_subtitle("Skanuje wybrany folder i dodaje miniatury")
        add_dir_btn = Gtk.Button(label="Wybierz katalog")
        add_dir_btn.set_valign(Gtk.Align.CENTER)
        add_dir_btn.set_icon_name('folder-open-symbolic')
        add_dir_btn.connect('clicked', self._pick_wp_dir)
        dir_row.add_suffix(add_dir_btn)
        wp_group.add(dir_row)

        self.wp_flow = Gtk.FlowBox()
        self.wp_flow.set_max_children_per_line(3)
        self.wp_flow.set_min_children_per_line(2)
        self.wp_flow.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.wp_flow.set_row_spacing(8)
        self.wp_flow.set_column_spacing(8)
        self.wp_flow.set_margin_top(10)
        self.wp_flow.set_margin_bottom(10)
        self.wp_flow.set_margin_start(10)
        self.wp_flow.set_margin_end(10)
        self.wp_flow.set_homogeneous(True)
        self.wp_flow.connect('child-activated', self._set_wallpaper)

        wp_scroll = Gtk.ScrolledWindow()
        wp_scroll.set_vexpand(True)
        wp_scroll.set_min_content_height(520)
        wp_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        wp_scroll.set_child(self.wp_flow)

        wp_group.add(wp_scroll)
        self.add(wp_group)

        threading.Thread(target=self._load_wallpapers, daemon=True).start()

    def _toggle_dark(self, row, _):
        val = 'prefer-dark' if row.get_active() else 'prefer-light'
        gsettings_set('org.gnome.desktop.interface', 'color-scheme', val)

    def _apply_icons(self, _):
        t = ICON_THEMES[self.icon_combo.get_selected()]
        cmds = []
        if t['pkg'] and not is_pkg_installed(t['pkg']):
            cmds.append((f"Instalacja {t['pkg']}", ['paru', '-S', '--noconfirm', t['pkg']]))
        cmds.append(("Ustawianie ikon", ['gsettings', 'set',
                     'org.gnome.desktop.interface', 'icon-theme', t['value']]))
        InstallDialog(cmds, 'Ikony', parent=self.win).present(self.win)

    def _apply_cursor(self, _):
        t = CURSOR_THEMES[self.cursor_combo.get_selected()]
        cmds = []
        if t['pkg'] and not is_pkg_installed(t['pkg']):
            cmds.append((f"Instalacja {t['pkg']}", ['paru', '-S', '--noconfirm', t['pkg']]))
        cmds.append(("Ustawianie kursora", ['gsettings', 'set',
                     'org.gnome.desktop.interface', 'cursor-theme', t['value']]))
        InstallDialog(cmds, 'Kursor', parent=self.win).present(self.win)

    def _apply_cursor_size(self, _):
        size = int(self.cursor_size_scale.get_value())
        subprocess.run(['gsettings', 'set', 'org.gnome.desktop.interface',
                        'cursor-size', str(size)])

    def _apply_shell(self, _):
        """Zastosuj motyw GNOME Shell."""
        idx = self.shell_combo.get_selected()
        if idx == 0:
            shell_name = ''
            t = None
        else:
            shell_themes = [t for t in GTK_THEMES if t['shell']]
            if idx - 1 >= len(shell_themes):
                return
            t = shell_themes[idx - 1]
            shell_name = t['shell']

        cmds = []

        # Najpierw upewnij się, że rozszerzenie User Themes jest zainstalowane i włączone.
        # Bez niego schemat "org.gnome.shell.extensions.user-theme" nie istnieje → błąd "Brak schematu".
        gext_ok = bool(shutil.which('gext'))
        if gext_ok:
            try:
                res = subprocess.run(['gnome-extensions', 'list'], capture_output=True, text=True)
                if 'user-theme@gnome-shell-extensions.gcampax.github.com' not in res.stdout:
                    cmds.append(("Instalacja rozszerzenia User Themes", ['gext', 'install', 'user-theme@gnome-shell-extensions.gcampax.github.com']))
            except Exception:
                pass
            cmds.append(("Włączanie User Themes", ['gnome-extensions', 'enable', 'user-theme@gnome-shell-extensions.gcampax.github.com']))
        else:
            # gext nie ma — zainstaluj najpierw, potem rozszerzenie
            cmds.append(("Instalacja gnome-extensions-cli (gext)", ['paru', '-S', '--noconfirm', 'gnome-extensions-cli']))
            cmds.append(("Instalacja rozszerzenia User Themes", ['gext', 'install', 'user-theme@gnome-shell-extensions.gcampax.github.com']))
            cmds.append(("Włączanie User Themes", ['gnome-extensions', 'enable', 'user-theme@gnome-shell-extensions.gcampax.github.com']))

        if t and t.get('pkg') and not is_pkg_installed(t['pkg']):
            cmds.append((f"Instalacja {t['pkg']}", ['paru', '-S', '--noconfirm', t['pkg']]))

        # Sprawdź czy schemat jest już dostępny (zależny od tego czy Shell załadował rozszerzenie)
        schema_available = False
        try:
            schemas = subprocess.run(
                ['gsettings', 'list-schemas'],
                capture_output=True, text=True, timeout=3
            ).stdout
            schema_available = 'org.gnome.shell.extensions.user-theme' in schemas
        except Exception:
            pass

        if schema_available:
            cmds.append(("Motyw GNOME Shell", ['gsettings', 'set', 'org.gnome.shell.extensions.user-theme', 'name', shell_name]))
        else:
            # Rozszerzenie właśnie włączone lub nie było załadowane — gsettings nie zadziała bez restartu Shella
            msg = (f"Rozszerzenie User Themes włączone. "
                   f"Zrestartuj GNOME Shell (Alt+F2 → wpisz 'r' → Enter), "
                   f"a następnie ponownie wybierz motyw '{shell_name or 'domyślny'}' w Settler.")
            cmds.append(("Motyw GNOME Shell — wymagany restart", ['echo', msg]))

        # Zawsze dodaj przypomnienie
        cmds.append(("Przypomnienie", ['echo', 'Jeśli motyw nie działa od razu — zrestartuj GNOME Shell (Alt+F2, r, Enter)']))

        InstallDialog(cmds, 'Motyw Shell', parent=self.win).present(self.win)

    def _pick_wp_dir(self, btn):
        dialog = Gtk.FileDialog()
        dialog.set_title("Wybierz katalog z tapetami")
        dialog.select_folder(self.win, None, self._on_dir_selected)

    def _on_dir_selected(self, dialog, result):
        try:
            folder = dialog.select_folder_finish(result)
            if folder:
                path = folder.get_path()
                if path not in self._extra_wp_dirs:
                    self._extra_wp_dirs.append(path)
                    threading.Thread(
                        target=self._load_from_dir,
                        args=(path,),
                        daemon=True
                    ).start()
        except Exception:
            pass

    def _load_from_dir(self, directory):
        exts = ['*.jpg', '*.jpeg', '*.png', '*.webp', '*.JPG', '*.PNG']
        seen = set()
        for ext in exts:
            for p in glob.glob(os.path.join(directory, '**', ext), recursive=True):
                if p not in seen:
                    seen.add(p)
                    GLib.idle_add(self._add_thumb, p)

    def _load_wallpapers(self):
        wallpapers = get_wallpapers()
        for path in wallpapers[:80]:
            GLib.idle_add(self._add_thumb, path)

    def _add_thumb(self, path):
        try:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 320, 180, True)
            # GTK4.10+: MemoryTexture for modern, fallback for older/deprecated new_for_pixbuf
            try:
                if hasattr(Gdk, 'MemoryTexture'):
                    raw = pb.get_pixels()
                    if pb.get_has_alpha():
                        fmt = getattr(Gdk.MemoryFormat, 'R8G8B8A8_PREMULTIPLIED', Gdk.MemoryFormat.R8G8B8A8)
                    else:
                        fmt = Gdk.MemoryFormat.R8G8B8
                    gbytes = GLib.Bytes.new(raw) if isinstance(raw, (bytes, bytearray, memoryview)) else GLib.Bytes.new(raw.tobytes() if hasattr(raw, 'tobytes') else bytes(raw))
                    tex = Gdk.MemoryTexture.new(
                        pb.get_width(), pb.get_height(), fmt, gbytes, pb.get_rowstride())
                else:
                    tex = Gdk.Texture.new_for_pixbuf(pb)
            except Exception:
                tex = Gdk.Texture.new_for_pixbuf(pb)  # ultimate fallback
            pic = Gtk.Picture.new_for_paintable(tex)
            pic.set_size_request(320, 180)
            pic.set_content_fit(Gtk.ContentFit.COVER)
            pic.add_css_class('wp-thumb')

            frame = Gtk.Frame()
            frame.set_child(pic)
            frame.add_css_class('wp-thumb')

            tooltip = os.path.basename(path)
            frame.set_tooltip_text(tooltip)

            child = Gtk.FlowBoxChild()
            child.set_child(frame)
            child._wp_path = path
            self.wp_flow.append(child)
        except Exception:
            pass
        return False

    def _apply_wp_scale(self, combo, _):
        _, val = self._wp_scale_options[combo.get_selected()]
        gsettings_set('org.gnome.desktop.background', 'picture-options', val)

    def _set_wallpaper(self, flowbox, child):
        path = getattr(child, '_wp_path', None)
        if path:
            uri = f"file://{path}"
            gsettings_set('org.gnome.desktop.background', 'picture-uri', uri)
            gsettings_set('org.gnome.desktop.background', 'picture-uri-dark', uri)
            # Użyj wybranego trybu skalowania
            _, scale_val = self._wp_scale_options[self.wp_scale_combo.get_selected()]
            gsettings_set('org.gnome.desktop.background', 'picture-options', scale_val)

# ──────────────────────────────────────────────────────────────
# STRONA: SYSTEM
# ──────────────────────────────────────────────────────────────

class SystemPage(Adw.PreferencesPage):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.set_title("System")
        self.set_icon_name("preferences-system-symbolic")

        # ─── Zasilanie ───────────────────────────
        pw_group = Adw.PreferencesGroup()
        pw_group.set_title("Zasilanie")

        perf_row = Adw.ActionRow()
        perf_row.set_title("Tryb zasilania")
        perf_row.set_subtitle("Wysoka wydajność i pobór energii")
        perf_combo = Gtk.DropDown.new_from_strings(["Wydajność", "Zrównoważone", "Oszczędzanie"])
        perf_combo.set_valign(Gtk.Align.CENTER)
        perf_combo.connect('notify::selected', self._set_perf)
        perf_row.add_suffix(perf_combo)
        pw_group.add(perf_row)

        suspend_row = Adw.SwitchRow()
        suspend_row.set_title("Wyłącz automatyczne usypianie")
        suspend_row.set_subtitle("Na zasilaniu sieciowym")
        s = gsettings_get('org.gnome.settings-daemon.plugins.power', 'sleep-inactive-ac-type')
        suspend_row.set_active(s == 'nothing')
        suspend_row.connect('notify::active', self._toggle_suspend)
        pw_group.add(suspend_row)

        dim_row = Adw.SwitchRow()
        dim_row.set_title("Wyłącz przygaszanie ekranu")
        s2 = gsettings_get('org.gnome.settings-daemon.plugins.power', 'idle-dim')
        dim_row.set_active(s2 == 'false')
        dim_row.connect('notify::active', self._toggle_dim)
        pw_group.add(dim_row)

        lock_row = Adw.SwitchRow()
        lock_row.set_title("Wyłącz automatyczne wygaszenie / blokadę")
        s3 = gsettings_get('org.gnome.desktop.session', 'idle-delay')
        lock_row.set_active(s3 in ('0', 'uint32 0'))
        lock_row.connect('notify::active', self._toggle_screen)
        pw_group.add(lock_row)

        self.add(pw_group)

        # ─── Mysz ─────────────────────────────────
        mouse_group = Adw.PreferencesGroup()
        mouse_group.set_title("Mysz")

        speed_row = Adw.ActionRow()
        speed_row.set_title("Prędkość kursora")
        speed_row.set_subtitle("Wolny ←→ Szybki")
        speed_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -1.0, 1.0, 0.1)
        speed_scale.set_size_request(200, -1)
        speed_scale.set_valign(Gtk.Align.CENTER)
        try:
            speed_scale.set_value(float(gsettings_get('org.gnome.desktop.peripherals.mouse', 'speed')))
        except Exception:
            speed_scale.set_value(0.0)
        speed_scale.connect('value-changed', self._set_mouse_speed)
        speed_row.add_suffix(speed_scale)
        mouse_group.add(speed_row)

        accel_row = Adw.SwitchRow()
        accel_row.set_title("Wyłącz przyspieszenie myszy")
        accel_row.set_subtitle("Flat profile — zalecane dla graczy")
        cur_accel = gsettings_get('org.gnome.desktop.peripherals.mouse', 'accel-profile')
        accel_row.set_active(cur_accel == 'flat')
        accel_row.connect('notify::active', self._toggle_accel)
        mouse_group.add(accel_row)

        scroll_row = Adw.SwitchRow()
        scroll_row.set_title("Tradycyjne przewijanie")
        scroll_row.set_subtitle("Wyłączone = kółko porusza widok w górę/dół")
        cur_scroll = gsettings_get('org.gnome.desktop.peripherals.mouse', 'natural-scroll')
        scroll_row.set_active(cur_scroll == 'false')
        scroll_row.connect('notify::active', self._toggle_scroll)
        mouse_group.add(scroll_row)

        self.add(mouse_group)

        # ─── Okna ─────────────────────────────────
        wm_group = Adw.PreferencesGroup()
        wm_group.set_title("Okna")

        btn_row = Adw.ActionRow()
        btn_row.set_title("Przyciski paska tytułu")
        btn_row.set_subtitle("Minimalizacja + Maksymalizacja po prawej stronie")
        apply_btn = Gtk.Button(label="Zastosuj")
        apply_btn.set_valign(Gtk.Align.CENTER)
        apply_btn.add_css_class('suggested-action')
        apply_btn.connect('clicked', lambda _: gsettings_set(
            'org.gnome.desktop.wm.preferences', 'button-layout', 'appmenu:minimize,maximize,close'))
        btn_row.add_suffix(apply_btn)
        wm_group.add(btn_row)
        self.add(wm_group)

        # ─── Monitor ──────────────────────────────
        mon_group = Adw.PreferencesGroup()
        mon_group.set_title("Monitor")

        mon_row = Adw.ActionRow()
        mon_row.set_title("Xiaomi Mi Monitor — 3440×1440 @ 180Hz HDR")
        mon_row.set_subtitle("Zastosuj konfigurację monitors.xml (DP-1, bt2100)")
        mon_btn = Gtk.Button(label="Zastosuj")
        mon_btn.set_valign(Gtk.Align.CENTER)
        mon_btn.add_css_class('suggested-action')
        mon_btn.connect('clicked', self._apply_monitor)
        mon_row.add_suffix(mon_btn)
        mon_group.add(mon_row)
        self.add(mon_group)

    def _set_perf(self, combo, _):
        profiles = ['performance', 'balanced', 'power-saver']
        try:
            subprocess.run(['powerprofilesctl', 'set', profiles[combo.get_selected()]])
        except Exception:
            pass

    def _toggle_suspend(self, row, _):
        gsettings_set('org.gnome.settings-daemon.plugins.power', 'sleep-inactive-ac-type',
                      'nothing' if row.get_active() else 'suspend')

    def _toggle_dim(self, row, _):
        subprocess.run(['gsettings', 'set', 'org.gnome.settings-daemon.plugins.power',
                        'idle-dim', 'false' if row.get_active() else 'true'])

    def _toggle_screen(self, row, _):
        subprocess.run(['gsettings', 'set', 'org.gnome.desktop.session',
                        'idle-delay', 'uint32 0' if row.get_active() else 'uint32 300'])

    def _set_mouse_speed(self, scale):
        subprocess.run(['gsettings', 'set', 'org.gnome.desktop.peripherals.mouse',
                        'speed', str(round(scale.get_value(), 2))])

    def _toggle_accel(self, row, _):
        gsettings_set('org.gnome.desktop.peripherals.mouse', 'accel-profile',
                      'flat' if row.get_active() else 'default')

    def _toggle_scroll(self, row, _):
        subprocess.run(['gsettings', 'set', 'org.gnome.desktop.peripherals.mouse',
                        'natural-scroll', 'false' if row.get_active() else 'true'])

    def _apply_monitor(self, _):
        config = """<monitors version="2">
  <configuration>
    <layoutmode>logical</layoutmode>
    <logicalmonitor>
      <x>0</x><y>0</y><scale>1</scale><primary>yes</primary>
      <monitor>
        <monitorspec>
          <connector>DP-1</connector>
          <vendor>XMI</vendor>
          <product>Mi monitor</product>
          <serial>5505610025927</serial>
        </monitorspec>
        <mode><width>3440</width><height>1440</height><rate>180.000</rate></mode>
        <colormode>bt2100</colormode>
      </monitor>
    </logicalmonitor>
  </configuration>
</monitors>"""
        monitors_path = os.path.expanduser('~/.config/monitors.xml')
        os.makedirs(os.path.dirname(monitors_path), exist_ok=True)
        with open(monitors_path, 'w') as f:
            f.write(config)

# ──────────────────────────────────────────────────────────────
# STRONA: GAMING
# ──────────────────────────────────────────────────────────────

class GamingPage(Adw.PreferencesPage):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.set_title("Gaming")
        self.set_icon_name("applications-games-symbolic")
        self.checks = {}

        tools_group = Adw.PreferencesGroup()
        tools_group.set_title("Narzędzia gamingowe")

        gaming_pkgs = [
            ("GameMode",         "gamemode",       "Optymalizacja systemu dla gier",      "pacman"),
            ("GameMode 32-bit",  "lib32-gamemode", "Wsparcie gier 32-bit",                "pacman"),
            ("MangoHud",         "mangohud",       "Overlay FPS/GPU/CPU/temp w grach",    "pacman"),
            ("MangoHud 32-bit",  "lib32-mangohud", "Wsparcie gier 32-bit",                "pacman"),
            ("Wine",             "wine",           "Uruchamianie gier i programów Win",   "pacman"),
            ("Wine Mono",        "wine-mono",      "Obsługa .NET w Wine",                 "pacman"),
            ("Winetricks",       "winetricks",     "Skrypty konfiguracji Wine",           "pacman"),
            ("Lutris",           "lutris",         "Manager gier Linux",                  "pacman"),
            ("ProtonUp-Qt",      "protonup-qt",    "Manager wersji GE-Proton",            "aur"),
        ]

        for name, pkg, desc, src in gaming_pkgs:
            row = Adw.ActionRow()
            row.set_title(name)
            row.set_subtitle(desc)
            installed = is_pkg_installed(pkg)
            check = Gtk.CheckButton()
            check.set_active(not installed)
            check.set_sensitive(not installed)
            if installed:
                badge = Gtk.Label(label="✓")
                badge.add_css_class('installed-badge')
                badge.set_valign(Gtk.Align.CENTER)
                row.add_suffix(badge)
            else:
                row.add_suffix(check)
                row.set_activatable_widget(check)
            self.checks[pkg] = (check, src)
            tools_group.add(row)

        install_row = Adw.ActionRow()
        install_row.set_title("Zainstaluj zaznaczone")
        install_btn = Gtk.Button(label="Instaluj")
        install_btn.add_css_class('suggested-action')
        install_btn.set_valign(Gtk.Align.CENTER)
        install_btn.connect('clicked', self._install_tools)
        install_row.add_suffix(install_btn)
        tools_group.add(install_row)
        self.add(tools_group)

        # Steam launch options
        launch_group = Adw.PreferencesGroup()
        launch_group.set_title("Steam Launch Options")
        launch_group.set_description("Dodaj w: PPM na grę → Właściwości → Opcje uruchamiania")

        opts = [
            ("GameMode + MangoHud", "gamemoderun mangohud %command%"),
            ("Tylko GameMode",       "gamemoderun %command%"),
            ("Tylko MangoHud",       "mangohud %command%"),
            ("DXVK Async",           "DXVK_ASYNC=1 %command%"),
            ("NVIDIA API (Proton)",  "PROTON_ENABLE_NVAPI=1 %command%"),
            ("VKD3D dla DX12",       "VKD3D_CONFIG=pipeline_library_log %command%"),
        ]
        for label, opt_str in opts:
            row = Adw.ActionRow()
            row.set_title(label)
            row.set_subtitle(opt_str)
            copy_btn = Gtk.Button()
            copy_btn.set_icon_name('edit-copy-symbolic')
            copy_btn.set_valign(Gtk.Align.CENTER)
            copy_btn.set_tooltip_text("Kopiuj do schowka")
            copy_btn.connect('clicked', self._copy_opt, opt_str)
            row.add_suffix(copy_btn)
            launch_group.add(row)
        self.add(launch_group)

        # Kernel tweaks
        kern_group = Adw.PreferencesGroup()
        kern_group.set_title("Optymalizacja kernela")

        swap_row = Adw.ActionRow()
        swap_row.set_title("vm.swappiness = 10")
        swap_row.set_subtitle("Zmniejsza użycie swap, lepsze dla gamingu (domyślnie 60)")
        swap_btn = Gtk.Button(label="Zastosuj")
        swap_btn.set_valign(Gtk.Align.CENTER)
        swap_btn.connect('clicked', self._set_swappiness)
        swap_row.add_suffix(swap_btn)
        kern_group.add(swap_row)
        self.add(kern_group)

    def _install_tools(self, _):
        pacman, aur = [], []
        for pkg, (check, src) in self.checks.items():
            if check.get_active():
                (pacman if src == 'pacman' else aur).append(pkg)
        cmds = []
        if pacman:
            cmds.append(("Instalacja (pacman)", ['pkexec', 'pacman', '-S', '--noconfirm'] + pacman))
        if aur:
            cmds.append(("Instalacja AUR", ['paru', '-S', '--noconfirm'] + aur))
        if cmds:
            InstallDialog(cmds, 'Gaming Tools', parent=self.win).present(self.win)

    def _copy_opt(self, btn, text):
        clipboard = self.get_display().get_clipboard()
        clipboard.set(text)

    def _set_swappiness(self, _):
        cmds = [("vm.swappiness = 10", ['pkexec', 'bash', '-c',
                 'echo "vm.swappiness=10" > /etc/sysctl.d/99-swappiness.conf && sysctl --system'])]
        InstallDialog(cmds, 'Kernel Tweaks', parent=self.win).present(self.win)

# ──────────────────────────────────────────────────────────────
# STRONA: ROZSZERZENIA
# ──────────────────────────────────────────────────────────────

class ExtensionsPage(Adw.PreferencesPage):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.set_title("Rozszerzenia")
        self.set_icon_name("application-x-addon-symbolic")

        result = subprocess.run(['gnome-extensions', 'list', '--enabled'],
                                capture_output=True, text=True)
        enabled = set(result.stdout.strip().split('\n'))

        # gext info
        tool_group = Adw.PreferencesGroup()
        tool_group.set_title("Narzędzia")

        gext_ok = bool(shutil.which('gext'))
        gext_row = Adw.ActionRow()
        gext_row.set_title("gnome-extensions-cli (gext)")
        gext_row.set_subtitle("✓ Zainstalowany" if gext_ok else "Wymagany do instalacji rozszerzeń z CLI")
        if not gext_ok:
            gext_btn = Gtk.Button(label="Zainstaluj gext")
            gext_btn.add_css_class('suggested-action')
            gext_btn.set_valign(Gtk.Align.CENTER)
            gext_btn.connect('clicked', lambda _: InstallDialog(
                [("Instalacja gext", ['paru', '-S', '--noconfirm', 'gnome-extensions-cli'])],
                "gext").present(self.win))
            gext_row.add_suffix(gext_btn)
        tool_group.add(gext_row)

        install_all_btn = Gtk.Button(label="Zainstaluj wszystkie rozszerzenia")
        install_all_btn.add_css_class('suggested-action')
        install_all_btn.connect('clicked', self._install_all)

        install_row = Adw.ActionRow()
        install_row.set_title("Zainstaluj wszystkie")
        install_row.set_subtitle(f"{len(EXTENSIONS)} rozszerzeń z listy poniżej")
        install_row.add_suffix(install_all_btn)
        tool_group.add(install_row)
        self.add(tool_group)

        # Extensions list
        active_group = Adw.PreferencesGroup()
        active_group.set_title("Aktywne rozszerzenia")

        inactive_group = Adw.PreferencesGroup()
        inactive_group.set_title("Zainstalowane — wyłączone")

        for ext in EXTENSIONS:
            row = Adw.SwitchRow()
            row.set_title(ext['name'])
            row.set_subtitle(ext['desc'])
            row.set_active(ext['uuid'] in enabled)
            row.connect('notify::active', self._toggle, ext['uuid'])
            if ext['active']:
                active_group.add(row)
            else:
                inactive_group.add(row)

        self.add(active_group)
        self.add(inactive_group)

    def _toggle(self, row, _, uuid):
        action = 'enable' if row.get_active() else 'disable'
        subprocess.run(['gnome-extensions', action, uuid], capture_output=True)

    def _install_all(self, _):
        cmds = [(f"Instalacja: {e['name']}", ['gext', 'install', e['uuid']])
                for e in EXTENSIONS]
        InstallDialog(cmds, 'Instalacja rozszerzeń', parent=self.win).present(self.win)

# ──────────────────────────────────────────────────────────────
# STRONA: KEYD
# ──────────────────────────────────────────────────────────────

class KeydPage(Adw.PreferencesPage):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.set_title("Keyd")
        self.set_icon_name("input-keyboard-symbolic")

        # Status
        status_group = Adw.PreferencesGroup()
        status_group.set_title("Status")

        keyd_ok = bool(shutil.which('keyd'))
        svc_status = subprocess.run(['systemctl', 'is-active', 'keyd'],
                                     capture_output=True, text=True).stdout.strip()

        status_row = Adw.ActionRow()
        status_row.set_title("keyd")
        if keyd_ok:
            status_row.set_subtitle(f"✓ Zainstalowany — usługa: {svc_status}")
        else:
            status_row.set_subtitle("✗ Nie zainstalowany")
            install_btn = Gtk.Button(label="Zainstaluj keyd")
            install_btn.add_css_class('suggested-action')
            install_btn.set_valign(Gtk.Align.CENTER)
            install_btn.connect('clicked', self._install)
            status_row.add_suffix(install_btn)
        status_group.add(status_row)
        self.add(status_group)

        # Config
        cfg_group = Adw.PreferencesGroup()
        cfg_group.set_title("Konfiguracja — Razer BlackWidow V4 X")
        cfg_group.set_description("Klawisze M1–M6 mapowane na Ctrl+Shift+1–6")

        rows = [
            ("Urządzenie",    "Razer BlackWidow V4 X",           "ID: 1532:0293"),
            ("M1 → Ctrl+Shift+1", "F13 → C-S-1",                ""),
            ("M2 → Ctrl+Shift+2", "F14 → C-S-2",                ""),
            ("M3 → Ctrl+Shift+3", "F15 → C-S-3",                ""),
            ("M4 → Ctrl+Shift+4", "F16 → C-S-4",                ""),
            ("M5 → Ctrl+Shift+5", "F17 → C-S-5",                ""),
            ("M6 → Ctrl+Shift+6", "F18 → C-S-6",                ""),
        ]
        for title, subtitle, sub2 in rows:
            row = Adw.ActionRow()
            row.set_title(title)
            row.set_subtitle(subtitle + (f"  {sub2}" if sub2 else ""))
            cfg_group.add(row)

        apply_row = Adw.ActionRow()
        apply_row.set_title("Zastosuj konfigurację")
        apply_row.set_subtitle("Zapisuje /etc/keyd/default.conf i restartuje usługę")
        apply_btn = Gtk.Button(label="Zastosuj")
        apply_btn.add_css_class('suggested-action')
        apply_btn.set_valign(Gtk.Align.CENTER)
        apply_btn.connect('clicked', self._apply)
        apply_row.add_suffix(apply_btn)
        cfg_group.add(apply_row)
        self.add(cfg_group)

        # OpenRazer
        razer_group = Adw.PreferencesGroup()
        razer_group.set_title("OpenRazer — wymagany dla klawiszy M")

        razer_ok = is_pkg_installed('openrazer-driver-dkms')
        razer_row = Adw.ActionRow()
        razer_row.set_title("openrazer-meta")
        razer_row.set_subtitle("✓ Zainstalowany" if razer_ok else "Wymagany aby klawisze M były widoczne")
        if not razer_ok:
            razer_btn = Gtk.Button(label="Zainstaluj OpenRazer")
            razer_btn.add_css_class('suggested-action')
            razer_btn.set_valign(Gtk.Align.CENTER)
            razer_btn.connect('clicked', self._install_razer)
            razer_row.add_suffix(razer_btn)
        razer_group.add(razer_row)

        daemon_row = Adw.ActionRow()
        daemon_row.set_title("openrazer-daemon")
        daemon_row.set_subtitle("Włącz usługę i dodaj siebie do grupy openrazer")
        daemon_btn = Gtk.Button(label="Włącz")
        daemon_btn.set_valign(Gtk.Align.CENTER)
        daemon_btn.connect('clicked', self._enable_razer_daemon)
        daemon_row.add_suffix(daemon_btn)
        razer_group.add(daemon_row)
        self.add(razer_group)

    def _install(self, _):
        cmds = [
            ("Instalacja keyd", ['paru', '-S', '--noconfirm', 'keyd']),
            ("Włączanie usługi", ['pkexec', 'systemctl', 'enable', '--now', 'keyd']),
        ]
        InstallDialog(cmds, 'Instalacja keyd', parent=self.win).present(self.win)

    def _apply(self, _):
        config = (
            "[ids]\n1532:0293\n\n[main]\n"
            "f13 = C-S-1\nf14 = C-S-2\nf15 = C-S-3\n"
            "f16 = C-S-4\nf17 = C-S-5\nf18 = C-S-6\n"
        )
        script = f"mkdir -p /etc/keyd && printf '{config}' > /etc/keyd/default.conf && systemctl restart keyd"
        cmds = [("Konfiguracja keyd", ['pkexec', 'bash', '-c', script])]
        InstallDialog(cmds, 'Keyd Config', parent=self.win).present(self.win)

    def _install_razer(self, _):
        cmds = [("Instalacja OpenRazer", ['paru', '-S', '--noconfirm', 'openrazer-meta', 'polychromatic'])]
        InstallDialog(cmds, 'OpenRazer', parent=self.win).present(self.win)

    def _enable_razer_daemon(self, _):
        try:
            user = pwd.getpwuid(os.getuid()).pw_name
        except Exception:
            user = os.environ.get('USER', 'root')
        cmds = [
            ("Dodaj do grupy openrazer", ['pkexec', 'gpasswd', '-a', user, 'openrazer']),
            ("Włącz openrazer-daemon", ['systemctl', '--user', 'enable', '--now', 'openrazer-daemon']),
        ]
        InstallDialog(cmds, 'OpenRazer Daemon', parent=self.win).present(self.win)

# ──────────────────────────────────────────────────────────────
# GŁÓWNE OKNO
# ──────────────────────────────────────────────────────────────

class SettlerWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title(f"Settler {VERSION}")
        self.set_default_size(1140, 780)
        # Apply bg classes directly to window for strongest possible override
        self.add_css_class('settler-root')
        self.add_css_class('settler-bg')

        split = Adw.OverlaySplitView()
        split.set_sidebar_width_fraction(0.21)
        split.set_show_sidebar(True)
        split.set_collapsed(False)
        split.add_css_class('settler-bg')

        # ── Sidebar ──────────────────────
        sb_tv = Adw.ToolbarView()
        sb_tv.add_css_class('settler-bg')
        sb_hb = Adw.HeaderBar()
        sb_hb.set_show_end_title_buttons(False)
        sb_title = Gtk.Label(label=f"Settler {VERSION}")
        sb_title.add_css_class('heading')
        sb_hb.set_title_widget(sb_title)
        sb_tv.add_top_bar(sb_hb)

        self.nav = Gtk.ListBox()
        self.nav.add_css_class('navigation-sidebar')
        self.nav.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.nav.connect('row-selected', self._on_nav)

        for label, icon, page_id in NAV_ITEMS:
            row = Gtk.ListBoxRow()
            row._page_id = page_id
            hb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            hb.set_margin_top(9)
            hb.set_margin_bottom(9)
            hb.set_margin_start(12)
            hb.set_margin_end(12)
            img = Gtk.Image.new_from_icon_name(icon)
            img.set_pixel_size(18)
            hb.append(img)
            lbl = Gtk.Label(label=label)
            lbl.set_halign(Gtk.Align.START)
            lbl.set_hexpand(True)
            hb.append(lbl)
            row.set_child(hb)
            self.nav.append(row)

        sb_scroll = Gtk.ScrolledWindow()
        sb_scroll.set_vexpand(True)
        sb_scroll.set_child(self.nav)
        sb_tv.set_content(sb_scroll)
        split.set_sidebar(sb_tv)

        # ── Content ─────────────────
        ct_tv = Adw.ToolbarView()
        ct_tv.add_css_class('settler-bg')
        ct_hb = Adw.HeaderBar()

        toggle = Gtk.ToggleButton()
        toggle.set_icon_name('sidebar-show-symbolic')
        toggle.set_active(True)
        toggle.set_tooltip_text("Pokaż/ukryj panel boczny")
        toggle.connect('toggled', lambda b: split.set_show_sidebar(b.get_active()))
        ct_hb.pack_start(toggle)
        ct_tv.add_top_bar(ct_hb)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(200)
        self.stack.add_css_class('settler-bg')  # ensure the page container is also solid

        self._pages = {}
        page_classes = [
            ("programs",   ProgramsPage),
            ("appearance", AppearancePage),
            ("system",     SystemPage),
            ("gaming",     GamingPage),
            ("extensions", ExtensionsPage),
            ("keyd",       KeydPage),
        ]
        for page_id, PageClass in page_classes:
            try:
                self._pages[page_id] = PageClass(self)
            except Exception as e:
                import traceback
                traceback.print_exc()
                # Pokaż stronę z błędem zamiast pustego okna
                err_page = Adw.PreferencesPage()
                err_group = Adw.PreferencesGroup()
                err_group.set_title(f"Błąd strony: {page_id}")
                err_row = Adw.ActionRow()
                err_row.set_title(str(e)[:120])
                err_group.add(err_row)
                err_page.add(err_group)
                self._pages[page_id] = err_page
        for page_id, page in self._pages.items():
            self.stack.add_named(page, page_id)

        ct_tv.set_content(self.stack)
        split.set_content(ct_tv)

        # Zawijamy w Box z solidnym tłem — zapobiega przeźroczystości
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.add_css_class('settler-root')
        root.set_vexpand(True)
        root.set_hexpand(True)
        root.append(split)
        self.set_content(root)

        # Select first
        self.nav.select_row(self.nav.get_row_at_index(0))

        # Nuclear option – make absolutely sure the main drawing widgets carry the bg class
        for w in (root, split, sb_tv, ct_tv, self.stack, self.nav):
            if w:
                w.add_css_class('settler-bg')

        # Strong default solid gray provider (prevents bleed)
        solid_bg_provider = Gtk.CssProvider()
        solid_bg_provider.load_from_string("""
            window, .background, adw-application-window,
            .settler-root, .settler-bg,
            overlay-split-view, toolbar-view,
            preferencespage, clamp, scrolledwindow, viewport,
            box, grid {
                background-color: @window_bg_color !important;
                background-image: none !important;
            }
            .settler-root, .settler-bg {
                background-color: @window_bg_color !important;
                background-image: none !important;
            }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            solid_bg_provider,
            2000
        )

    def _on_nav(self, _, row):
        if row:
            self.stack.set_visible_child_name(row._page_id)

# ──────────────────────────────────────────────────────────────
# APLIKACJA
# ──────────────────────────────────────────────────────────────

class SettlerApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.settler.app',
                         flags=Gio.ApplicationFlags.FLAGS_NONE)

    def do_activate(self):
        provider = Gtk.CssProvider()
        provider.load_from_string(GLOBAL_CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_USER
        )

        # Extra early default solid gray force
        early_gray = Gtk.CssProvider()
        early_gray.load_from_string("""
            window, .background, .settler-root, .settler-bg,
            adw-application-window, adw-overlay-split-view, adw-toolbar-view,
            preferencespage, clamp, viewport {
                background-color: @window_bg_color !important;
                background-image: none !important;
            }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), early_gray, 1500
        )

        # Load any previously saved custom window colors (from Appearance page)
        # so "szary / niebieski / whatever" chosen by user applies from the very first launch
        # and works on every tab (not only after visiting "Wygląd").
        css_path = os.path.expanduser('~/.config/gtk-4.0/gtk.css')
        if os.path.exists(css_path):
            saved = {}
            try:
                with open(css_path) as f:
                    for line in f:
                        m = re.match(r'@define-color\s+(\w+)\s+(#[0-9a-fA-F]{6});', line.strip())
                        if m:
                            saved[m.group(1)] = m.group(2)
            except Exception:
                pass

            if saved:
                r = []
                if 'window_bg_color' in saved:
                    c = saved['window_bg_color']
                    r.append(
                        f'window, .background, adw-application-window, .settler-root, .settler-bg, '
                        f'adw-overlay-split-view, adw-toolbar-view, overlay-split-view, toolbar-view, '
                        f'preferencespage, clamp, viewport, box, grid '
                        f'{{ background-color: {c} !important; background-image: none !important; }}'
                    )
                if 'window_fg_color' in saved:
                    c = saved['window_fg_color']
                    r.append(f'.settler-root, .settler-bg {{ color: {c}; }}')

                if r:
                    saved_provider = Gtk.CssProvider()
                    saved_provider.load_from_string('\n'.join(r))
                    Gtk.StyleContext.add_provider_for_display(
                        Gdk.Display.get_default(), saved_provider, 2500
                    )

        win = SettlerWindow(application=self)
        win.set_opacity(1.0)
        win.connect('realize', lambda w: w.set_opacity(1.0))
        win.present()


if __name__ == '__main__':
    app = SettlerApp()
    sys.exit(app.run(sys.argv))
