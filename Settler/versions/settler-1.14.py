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
import time

# ──────────────────────────────────────────────────────────────
# WERSJA
# ──────────────────────────────────────────────────────────────

VERSION = "1.14"

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
.settler-root,
.settler-bg {
    background-color: @window_bg_color !important;
    background-image: none !important;
    box-shadow: none;
}

/* Nie celujemy w box/scrolledwindow/viewport: w GTK 4.22 pole hasła
   ma je w środku i zwija się wtedy do jednej kropki. */
entry, password-entry, textview.text, row.entry {
    min-width: 16em;
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
.tag-flatpak { background: @orange_3; color: white; border-radius: 4px; padding: 2px 6px; font-size: 0.7em; }
.tag-github { background: @green_5; color: white; border-radius: 4px; padding: 2px 6px; font-size: 0.7em; }
.tag-grok   { background: @yellow_5; color: black; border-radius: 4px; padding: 2px 6px; font-size: 0.7em; }
.tag-unavailable { background: @red_3; color: white; border-radius: 4px; padding: 2px 6px; font-size: 0.7em; }
.installed-badge { background: @green_3; color: white; border-radius: 4px; padding: 2px 6px; font-size: 0.7em; }
"""

# ──────────────────────────────────────────────────────────────
# DANE
# ──────────────────────────────────────────────────────────────

# source: pacman | aur | flatpak | github | grok | settler | unavailable
# pkgs: paczki pacman/AUR. prep: paczki dokładane do pacmana przed skryptem GitHub.
# extra: photogimp | openrazer — krok po paczkach.
PROGRAMS = [
    {"id": "brave", "name": "Brave", "group": "Programy", "source": "pacman",
     "pkgs": ["brave-bin"], "desc": "Przeglądarka skupiona na prywatności"},
    {"id": "discord", "name": "Discord", "group": "Programy", "source": "pacman",
     "pkgs": ["discord"], "desc": "Komunikator głosowy i tekstowy"},
    {"id": "spotify", "name": "Spotify", "group": "Programy", "source": "aur",
     "pkgs": ["spotify"], "desc": "Streaming muzyki"},
    {"id": "vscode", "name": "Visual Studio Code", "group": "Programy", "source": "aur",
     "pkgs": ["visual-studio-code-bin"], "desc": "Edytor kodu Microsoft"},
    {"id": "libreoffice", "name": "LibreOffice", "group": "Programy", "source": "pacman",
     "pkgs": ["libreoffice-fresh"], "desc": "Pakiet biurowy"},
    {"id": "vlc", "name": "VLC", "group": "Programy", "source": "pacman",
     "pkgs": ["vlc"], "desc": "Odtwarzacz multimedialny"},
    {"id": "gimp", "name": "GIMP", "group": "Programy", "source": "pacman",
     "pkgs": ["gimp"], "extra": "photogimp",
     "desc": "Edytor grafiki. Lokalny skrót PhotoGIMP uruchamia ten sam program"},
    {"id": "krita", "name": "Krita", "group": "Programy", "source": "pacman",
     "pkgs": ["krita"], "desc": "Rysowanie i malowanie"},
    {"id": "ardour", "name": "Ardour", "group": "Programy", "source": "pacman",
     "pkgs": ["ardour"], "desc": "DAW — nagrywanie i miks"},
    {"id": "mixxx", "name": "Mixxx", "group": "Programy", "source": "pacman",
     "pkgs": ["mixxx"], "desc": "Oprogramowanie DJ"},
    {"id": "lmstudio", "name": "LM Studio", "group": "Programy", "source": "aur",
     "pkgs": ["lmstudio-bin"], "desc": "Lokalne modele językowe"},
    {"id": "warp", "name": "Warp", "group": "Programy", "source": "aur",
     "pkgs": ["warp-terminal-bin"], "desc": "Terminal Warp"},
    {"id": "warp-client", "name": "Cloudflare One Client", "group": "Programy", "source": "pacman",
     "pkgs": ["cloudflare-warp-bin"], "desc": "Klient WARP"},
    {"id": "openrazer", "name": "Polychromatic i OpenRazer", "group": "Programy", "source": "aur",
     "pkgs": ["polychromatic", "openrazer-meta-git"], "extra": "openrazer",
     "desc": "Podświetlenie Razer. Po instalacji przeloguj się, żeby grupy zaczęły działać"},
    {"id": "wivrn", "name": "WiVRn", "group": "Programy", "source": "aur",
     "pkgs": ["wivrn-dashboard", "wivrn-server", "xrizer", "xrizer-common",
              "lib32-wivrn-server", "lib32-xrizer"],
     "desc": "Serwer, panel, xrizer i biblioteki 32-bit. Potem przeloguj się, żeby Steam zobaczył VR"},

    {"id": "gamemode", "name": "GameMode", "group": "Gry", "source": "pacman",
     "pkgs": ["gamemode"], "desc": "Optymalizacja systemu dla gier"},
    {"id": "mangohud", "name": "MangoHud", "group": "Gry", "source": "pacman",
     "pkgs": ["mangohud"], "desc": "Overlay FPS, GPU i CPU"},
    {"id": "wine", "name": "Wine", "group": "Gry", "source": "pacman",
     "pkgs": ["wine"], "desc": "Uruchamianie programów Windows"},
    {"id": "winetricks", "name": "Winetricks", "group": "Gry", "source": "pacman",
     "pkgs": ["winetricks"], "desc": "Skrypty konfiguracji Wine"},
    {"id": "oversteer", "name": "Oversteer", "group": "Gry", "source": "aur",
     "pkgs": ["oversteer"], "desc": "Konfiguracja kierownicy"},
    {"id": "btop", "name": "btop", "group": "Gry", "source": "pacman",
     "pkgs": ["btop"], "desc": "Monitor systemu w terminalu"},
    {"id": "protonup", "name": "ProtonUp-Qt", "group": "Gry", "source": "pacman",
     "pkgs": ["protonup-qt"], "desc": "Manager wersji GE-Proton"},
    {"id": "lutris", "name": "Lutris", "group": "Gry", "source": "pacman",
     "pkgs": ["lutris"], "desc": "Manager gier Linux"},
    {"id": "heroic", "name": "Heroic Games", "group": "Gry", "source": "pacman",
     "pkgs": ["heroic-games-launcher"], "desc": "Launcher Epic Games i GOG"},
    {"id": "steam", "name": "Steam", "group": "Gry", "source": "pacman",
     "pkgs": ["steam"], "desc": "Platforma Valve. Wymaga włączonego repozytorium multilib"},
    {"id": "grok", "name": "Grok Build", "group": "Gry", "source": "grok",
     "prep": ["curl"], "desc": "Oficjalny instalator xAI. Polecenie: grok"},

    {"id": "tuxguitar", "name": "TuxGuitar", "group": "Flatpak", "source": "flatpak",
     "flatpak": "ar.com.tuxguitar.TuxGuitar", "desc": "Edytor tabulatur, Flathub"},
    {"id": "firestorm", "name": "Firestorm Viewer", "group": "Flatpak", "source": "flatpak",
     "flatpak": "org.firestormviewer.FirestormViewer", "desc": "Przeglądarka Second Life, Flathub"},
    {"id": "extension-manager", "name": "Menedżer rozszerzeń", "group": "Flatpak", "source": "flatpak",
     "flatpak": "com.mattjakeman.ExtensionManager", "desc": "Instalacja rozszerzeń GNOME, Flathub"},
    {"id": "wallora", "name": "Wallora 2", "group": "Flatpak", "source": "github",
     "github": "wallora", "prep": ["curl", "flatpak"],
     "desc": "Animowana tapeta. Flatpak z wydań GitHub"},
    {"id": "lustro", "name": "Lustro", "group": "Flatpak", "source": "github",
     "github": "lustro", "prep": ["curl", "flatpak"],
     "desc": "Kopia folderów na drugi dysk. Flatpak z wydań GitHub"},
    {"id": "flatpak-builder", "name": "Flatpak Builder", "group": "Flatpak", "source": "flatpak",
     "flatpak": "org.flatpak.Builder", "desc": "Narzędzie do budowania paczek Flatpak"},

    {"id": "kontur", "name": "Kontur", "group": "GitHub", "source": "github",
     "github": "kontur",
     "prep": ["git", "python", "python-gobject", "gtk4", "libadwaita", "gobject-introspection"],
     "desc": "Motyw GTK. Instalacja z github.com/GorianWaco/kontur"},
    {"id": "perun", "name": "Perun", "group": "GitHub", "source": "github",
     "github": "perun",
     "prep": ["git", "python", "python-gobject", "gtk4", "libadwaita", "python-vdf"],
     "desc": "Instalacja native z github.com/GorianWaco/perun"},
    {"id": "ogniwo", "name": "Ogniwo", "group": "GitHub", "source": "github",
     "github": "ogniwo",
     "prep": ["git", "python-gobject", "python-cairo", "gtk4", "libadwaita", "gtk3", "libnotify"],
     "desc": "Bateria myszy Razer. Instalacja z github.com/GorianWaco/ogniwo"},
    {"id": "razer-reactive", "name": "Razer Reactive", "group": "GitHub", "source": "github",
     "github": "razer", "prep": ["git"],
     "desc": "Instalacja z GitHuba. Skrypt potrzebuje uprawnień i dopisuje grupy"},
    {"id": "lovense", "name": "Lovense Controller", "group": "GitHub", "source": "github",
     "github": "lovense",
     "prep": ["curl", "git", "python", "python-gobject", "gtk4", "python-cairo",
              "gobject-introspection", "bluez", "bluez-utils", "pipewire",
              "pipewire-audio", "libpulse", "pipewire-pulse"],
     "desc": "Instalacja native z github.com/GorianWaco/max2-controller"},
    {"id": "klucznik", "name": "Klucznik", "group": "GitHub", "source": "github",
     "github": "klucznik",
     "prep": ["git", "python", "python-gobject", "python-cairo", "gtk4", "libadwaita"],
     "desc": "Sejf FIDO2 i GNOME Keyring. Instalacja z github.com/GorianWaco/klucznik"},
    {"id": "iskra", "name": "Iskra", "group": "GitHub", "source": "unavailable",
     "desc": "Brak repozytorium. Dysk ze źródłami nie jest podmontowany"},
    {"id": "gitadder", "name": "GITADDER", "group": "GitHub", "source": "github",
     "github": "gitadder",
     "prep": ["git", "github-cli", "python", "python-gobject", "libadwaita", "gtk4"],
     "desc": "Klon z GitHuba, potem lokalny instalator. Logowanie gh zostaje osobno"},
    {"id": "settler", "name": "Settler", "group": "GitHub", "source": "settler",
     "desc": "Ten program. Na nowym systemie wklej komendę z przycisku kopiowania",
     "copy": "curl -fsSL https://raw.githubusercontent.com/GorianWaco/Settler/main/install.sh | bash"},
    {"id": "focusrite", "name": "Focusrite Monitor", "group": "GitHub", "source": "github",
     "github": "focusrite",
     "prep": ["git", "python-gobject", "gtk4", "libadwaita", "gtk3", "alsa-utils", "pipewire-pulse"],
     "desc": "Instalacja użytkownika z github.com/GorianWaco/focusrite-monitor"},
]

EXTENSIONS = [
    {"uuid": "advanced-weather@sanjai.com", "name": "Advanced Weather Companion",
     "desc": "Pogoda w panelu", "active": True},
    {"uuid": "auto-move-windows@gnome-shell-extensions.gcampax.github.com", "name": "Auto Move Windows",
     "desc": "Automatyczne przenoszenie okien", "active": True},
    {"uuid": "blur-my-shell@aunetx", "name": "Blur my Shell",
     "desc": "Rozmycie powłoki", "active": True},
    {"uuid": "burn-my-windows@schneegans.github.com", "name": "Burn My Windows",
     "desc": "Animacje otwierania i zamykania okien", "active": True},
    {"uuid": "compiz-windows-effect@hermes83.github.com", "name": "Compiz windows effect",
     "desc": "Efekt galaretki okien", "active": True},
    {"uuid": "dash-to-panel@jderose9.github.com", "name": "Dash to Panel",
     "desc": "Panel z ulubionymi i oknami", "active": True},
    {"uuid": "ddterm@amezin.github.com", "name": "ddterm",
     "desc": "Terminal wysuwany z panelu", "active": True},
    {"uuid": "ding@rastersoft.com", "name": "Desktop Icons NG (DING)",
     "desc": "Ikony na pulpicie", "active": True},
    {"uuid": "fq@megh", "name": "Force Quit",
     "desc": "Zamykanie zawieszonego okna", "active": True},
    {"uuid": "freon@UshakovVasilii_Github.yahoo.com", "name": "Freon",
     "desc": "Temperatury w panelu", "active": True},
    {"uuid": "gamemodeshellextension@trsnaqe.com", "name": "GameMode Shell Extension",
     "desc": "Wskaźnik GameMode", "active": True},
    {"uuid": "gnome-ui-tune@itstime.tech", "name": "Gnome 4x, 5x UI Improvements",
     "desc": "Poprawki wyglądu GNOME", "active": True},
    {"uuid": "iskra-dropdown@gorian", "name": "Iskra drop-down",
     "desc": "Okno Iskry z panelu. Klon z github.com/GorianWaco/iskra-dropdown",
     "active": True, "source": "github"},
    {"uuid": "show-desktop-button@amivaleo", "name": "Show Desktop Button",
     "desc": "Przycisk pokazania pulpitu", "active": True},
    {"uuid": "trayIconsReloaded@selfmade.pl", "name": "Tray Icons: Reloaded",
     "desc": "Ikony zasobnika", "active": True},
    {"uuid": "user-theme@gnome-shell-extensions.gcampax.github.com", "name": "User Themes",
     "desc": "Własne motywy powłoki", "active": True},
    {"uuid": "vertical-workspaces@G-dH.github.com", "name": "V-Shell",
     "desc": "Pionowy przełącznik przestrzeni roboczych", "active": True},
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

def find_aur_helper():
    for name in ('paru', 'yay'):
        if shutil.which(name):
            return name
    return None

def ensure_aur_helper_cmds():
    """Zainstaluj paru z repo, jeśli nie ma żadnego helpera AUR."""
    if find_aur_helper():
        return []
    return [("Instalacja paru", ['pkexec', 'pacman', '-S', '--noconfirm', 'paru'])]

def aur_install_command(pkgs):
    helper = find_aur_helper() or 'paru'
    return [helper, '-S', '--noconfirm', '--needed'] + list(pkgs)

def cmd_needs_privilege(cmd):
    tokens = list(cmd) if isinstance(cmd, (list, tuple)) else [cmd]
    if any(t in ('pkexec', 'sudo', 'paru', 'yay') for t in tokens):
        return True
    blob = ' '.join(str(t) for t in tokens)
    return 'pkexec' in blob or 'sudo' in blob

def dedupe(items):
    out = []
    for item in items:
        if item not in out:
            out.append(item)
    return out

def flatpak_installed(app_id):
    if not shutil.which('flatpak'):
        return False
    for args in (['flatpak', 'info', '--user', app_id], ['flatpak', 'info', app_id]):
        if subprocess.run(args, capture_output=True).returncode == 0:
            return True
    return False

def flathub_ready():
    if not shutil.which('flatpak'):
        return False
    result = subprocess.run(['flatpak', 'remotes'], capture_output=True, text=True)
    for line in result.stdout.splitlines():
        parts = line.split()
        if parts and parts[0] == 'flathub':
            return True
    return False

def command_exists(name):
    if shutil.which(name):
        return True
    return os.path.isfile(os.path.expanduser(f'~/.local/bin/{name}')) or os.path.isfile(
        os.path.expanduser(f'~/.grok/bin/{name}'))

def photogimp_present():
    path = os.path.expanduser('~/.local/share/applications/gimp.desktop')
    try:
        with open(path, encoding='utf-8', errors='replace') as handle:
            text = handle.read()
    except OSError:
        return False
    return 'PhotoGIMP' in text and 'Icon=photogimp' in text

def is_program_installed(prog):
    source = prog['source']
    if source == 'unavailable':
        return False
    if source == 'settler':
        return True
    if prog.get('extra') == 'photogimp' and not photogimp_present():
        return False
    pkgs = prog.get('pkgs') or []
    if pkgs and not all(is_pkg_installed(pkg) for pkg in pkgs):
        return False
    if source == 'flatpak':
        return flatpak_installed(prog['flatpak'])
    if source == 'grok':
        return command_exists('grok')
    if source == 'github':
        checks = {
            'wallora': lambda: flatpak_installed('org.wallora.Wallora'),
            'lustro': lambda: flatpak_installed('pl.gorian.Lustro'),
            'perun': lambda: command_exists('perun'),
            'kontur': lambda: command_exists('kontur'),
            'ogniwo': lambda: command_exists('ogniwo'),
            'razer': lambda: command_exists('razer-reactive') or command_exists('razer-reactive-gui'),
            'lovense': lambda: command_exists('lovense-controller'),
            'gitadder': lambda: command_exists('gitadder'),
            'focusrite': lambda: command_exists('focusrite-monitor'),
            'klucznik': lambda: command_exists('klucznik'),
        }
        return checks[prog['github']]()
    return True

def source_tag(prog):
    source = prog['source']
    if source == 'unavailable':
        return 'brak', 'tag-unavailable'
    if source == 'settler':
        return 'github', 'tag-github'
    return source, f'tag-{source}'

def tools_missing():
    missing = []
    for pkg in ('git', 'curl', 'base-devel', 'flatpak'):
        if not is_pkg_installed(pkg):
            missing.append(pkg)
    if not find_aur_helper():
        missing.append('paru')
    if not shutil.which('gext'):
        missing.append('gext')
    if not flathub_ready():
        missing.append('Flathub')
    return missing

def tool_setup_commands():
    """git, kompilator AUR, flatpak, Flathub, paru i gext — jeden przycisk na start."""
    cmds = []
    pkgs = [pkg for pkg in ('git', 'curl', 'base-devel', 'flatpak') if not is_pkg_installed(pkg)]
    if not find_aur_helper():
        pkgs.append('paru')
    if pkgs:
        cmds.append(('Narzędzia', ['pkexec', 'pacman', '-S', '--needed', '--noconfirm'] + pkgs))
    cmds.append((
        'Flathub',
        ['bash', '-c',
         'command -v flatpak >/dev/null || { echo "Najpierw musi wejść pakiet flatpak"; exit 1; }\n'
         'flatpak remote-add --user --if-not-exists flathub '
         'https://dl.flathub.org/repo/flathub.flatpakrepo'],
    ))
    if not shutil.which('gext'):
        cmds.append(('gnome-extensions-cli', aur_install_command(['gnome-extensions-cli'])))
    return cmds

SUDO_SHIM = r"""
shim=$(mktemp -d)
trap 'rm -rf "$shim"' EXIT
cat > "$shim/sudo" << 'SHIM'
#!/bin/bash
while [[ $# -gt 0 ]]; do
  case "$1" in
    --) shift; break ;;
    -A|--askpass|-E|--preserve-env|-n|--non-interactive|-S) shift ;;
    *) break ;;
  esac
done
[[ $# -gt 0 ]] || { echo "sudo: brak polecenia" >&2; exit 1; }
exec pkexec "$@"
SHIM
chmod +x "$shim/sudo"
export PATH="$shim:$PATH"
"""

def github_clone_snippet(repo_url, folder):
    return f'''
dest="$HOME/Projekty/{folder}"
case "$dest" in
  "$HOME"/Projekty/*) ;;
  *) echo "Zła ścieżka: $dest" >&2; exit 1 ;;
esac
mkdir -p "$HOME/Projekty"
if [[ -d "$dest/.git" ]]; then
  git -C "$dest" pull --ff-only || echo "Zostawiam lokalną kopię: $dest"
elif [[ -f "$dest/install.sh" ]]; then
  echo "Używam istniejącego katalogu: $dest"
else
  rm -rf "$dest"
  git clone --depth 1 "{repo_url}" "$dest"
fi
'''

def curl_install_script(url, shim=False):
    body = 'set -euo pipefail\n'
    if shim:
        body += SUDO_SHIM + '\n'
    body += f'curl -fsSL "{url}" | bash\n'
    return body

def github_install_script(kind):
    if kind == 'perun':
        return 'set -euo pipefail\n' + github_clone_snippet(
            'https://github.com/GorianWaco/perun.git', 'perun') + '\nbash "$dest/install.sh" --no-deps\n'
    if kind == 'kontur':
        return 'set -euo pipefail\n' + github_clone_snippet(
            'https://github.com/GorianWaco/kontur.git', 'kontur') + '\nbash "$dest/install.sh"\n'
    if kind == 'ogniwo':
        return 'set -euo pipefail\n' + github_clone_snippet(
            'https://github.com/GorianWaco/ogniwo.git', 'ogniwo') + '\nbash "$dest/install.sh"\n'
    if kind == 'gitadder':
        return 'set -euo pipefail\n' + github_clone_snippet(
            'https://github.com/GorianWaco/gitadder.git', 'gitadder') + (
            '\nbash "$dest/install.sh" --no-deps --skip-auth-check\n')
    if kind == 'focusrite':
        return 'set -euo pipefail\n' + github_clone_snippet(
            'https://github.com/GorianWaco/focusrite-monitor.git', 'focusrite-monitor') + (
            '\nbash "$dest/install.sh"\n')
    if kind == 'klucznik':
        return 'set -euo pipefail\n' + github_clone_snippet(
            'https://github.com/GorianWaco/klucznik.git', 'klucznik') + '\nbash "$dest/install.sh"\n'
    if kind == 'razer':
        return 'set -euo pipefail\n' + github_clone_snippet(
            'https://github.com/GorianWaco/Razer-Reactive.git', 'Razer-Reactive') + r'''
exec pkexec env SUDO_USER="$USER" USER="$USER" HOME="$HOME" LOGNAME="$USER" \
  bash -c 'cd "$1" && ./install.sh' settler-razer "$dest"
'''
    if kind == 'lovense':
        return curl_install_script(
            'https://raw.githubusercontent.com/GorianWaco/max2-controller/main/install.sh', shim=True)
    if kind == 'wallora':
        return curl_install_script(
            'https://raw.githubusercontent.com/GorianWaco/wallora-v2/main/install.sh', shim=True)
    if kind == 'lustro':
        return r'''
set -euo pipefail
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
json=$(curl -fsSL https://api.github.com/repos/GorianWaco/lustro/releases/latest)
url=$(printf '%s' "$json" | python3 -c 'import json,sys; rel=json.load(sys.stdin); print(next(a["browser_download_url"] for a in rel["assets"] if str(a.get("name","")).endswith(".flatpak")))')
curl -fsSL -L -o "$tmp/Lustro.flatpak" "$url"
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --user -y "$tmp/Lustro.flatpak"
'''
    if kind == 'grok':
        return 'set -euo pipefail\ncurl -fsSL https://x.ai/cli/install.sh | bash\n'
    raise KeyError(kind)

def photogimp_command():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    icons = os.path.join(root, 'share', 'photogimp')
    script = r'''
set -euo pipefail
src="$1"
dest="$HOME/.local/share/icons/hicolor"
[[ -d "$src" ]] || { echo "Brak ikon PhotoGIMP: $src" >&2; exit 1; }
mkdir -p "$HOME/.local/share/applications" "$dest"
for size in 16x16 32x32 48x48 64x64 128x128 256x256 512x512; do
  mkdir -p "$dest/$size/apps"
  cp -a "$src/$size/photogimp.png" "$dest/$size/apps/photogimp.png"
done
if [[ -f "$src/photogimp.png" ]]; then
  cp -a "$src/photogimp.png" "$dest/photogimp.png"
fi
cat > "$HOME/.local/share/applications/gimp.desktop" << 'EOF'
[Desktop Entry]
Version=1.1
Type=Application
Name=PhotoGIMP
GenericName[pl]=Edytor obrazów
Comment[pl]=Skrót PhotoGIMP uruchamia systemowy GIMP
Icon=photogimp
Exec=gimp %U
TryExec=gimp
Terminal=false
Categories=Graphics;2DGraphics;RasterGraphics;GTK;
StartupNotify=true
StartupWMClass=gimp
EOF
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true
fi
echo "Skrót PhotoGIMP uruchamia systemowy GIMP. Konfiguracja GIMP zostaje bez zmian."
'''
    return ('Skrót PhotoGIMP', ['bash', '-c', script, 'photogimp', icons])

def openrazer_followup():
    user = pwd.getpwuid(os.getuid()).pw_name
    script = r'''
set -euo pipefail
user="$1"
pkexec bash -c 'getent group plugdev >/dev/null && gpasswd -a "$1" plugdev || true; getent group openrazer >/dev/null && gpasswd -a "$1" openrazer || true' settler-openrazer "$user"
systemctl --user enable --now openrazer-daemon || echo "Usługa openrazer-daemon włączy się po przelogowaniu."
echo "Grupy plugdev i openrazer zaczną działać po wylogowaniu i zalogowaniu."
'''
    return ('Grupy OpenRazer', ['bash', '-c', script, 'openrazer', user])

def commands_for_programs(progs):
    pacman, aur, flatpaks = [], [], []
    scripts = []
    extras = []
    for prog in progs:
        source = prog['source']
        if source == 'pacman':
            pacman.extend(prog.get('pkgs') or [])
        elif source == 'aur':
            aur.extend(prog.get('pkgs') or [])
        elif source == 'flatpak':
            flatpaks.append(prog['flatpak'])
        elif source in ('github', 'grok'):
            scripts.append(prog)
        pacman.extend(prog.get('prep') or [])
        if prog.get('extra'):
            extras.append(prog['extra'])

    needs_flatpak = bool(flatpaks) or any(prog.get('github') in ('wallora', 'lustro') for prog in scripts)
    if needs_flatpak and not shutil.which('flatpak'):
        pacman.append('flatpak')
    if scripts and not is_pkg_installed('curl'):
        pacman.append('curl')

    cmds = []
    if aur:
        pkgs = ['base-devel', 'git']
        if not find_aur_helper():
            pkgs.insert(0, 'paru')
        missing = [pkg for pkg in pkgs if pkg != 'paru' and not is_pkg_installed(pkg)]
        if not find_aur_helper():
            missing.insert(0, 'paru')
        if missing:
            cmds.append(('Narzędzia AUR', ['pkexec', 'pacman', '-S', '--needed', '--noconfirm'] + dedupe(missing)))
    pacman = dedupe(pacman)
    aur = dedupe(aur)
    if pacman:
        cmds.append(('Instalacja (pacman)', ['pkexec', 'pacman', '-S', '--needed', '--noconfirm'] + pacman))
    if aur:
        helper = find_aur_helper() or 'paru'
        cmds.append((f'Instalacja AUR ({helper})', aur_install_command(aur)))
    if needs_flatpak:
        cmds.append((
            'Flathub',
            ['bash', '-c',
             'flatpak remote-add --user --if-not-exists flathub '
             'https://dl.flathub.org/repo/flathub.flatpakrepo'],
        ))
    if flatpaks:
        cmds.append(('Flatpak', ['flatpak', 'install', '--user', '-y', 'flathub'] + flatpaks))
    labels = {
        'perun': 'Perun',
        'kontur': 'Kontur',
        'ogniwo': 'Ogniwo',
        'gitadder': 'GITADDER',
        'focusrite': 'Focusrite Monitor',
        'klucznik': 'Klucznik',
        'razer': 'Razer Reactive',
        'lovense': 'Lovense Controller',
        'wallora': 'Wallora 2',
        'lustro': 'Lustro',
        'grok': 'Grok Build',
    }
    for prog in scripts:
        kind = prog.get('github') or 'grok'
        cmds.append((labels[kind], ['bash', '-c', github_install_script(kind)]))
    if 'photogimp' in extras:
        cmds.append(photogimp_command())
    if 'openrazer' in extras:
        cmds.append(openrazer_followup())
    return cmds

def extension_install_commands():
    cmds = []
    if not shutil.which('gext'):
        cmds.extend(tool_setup_commands())
    for ext in EXTENSIONS:
        uuid = ext['uuid']
        name = ext['name']
        if ext.get('source') == 'github':
            clone = github_clone_snippet(
                'https://github.com/GorianWaco/iskra-dropdown.git', 'iskra-dropdown')
            script = f'''
set -euo pipefail
dir="$HOME/.local/share/gnome-shell/extensions/{uuid}"
if [[ -f "$dir/metadata.json" ]]; then
  gnome-extensions enable "{uuid}" || true
  echo "Już zainstalowane: {name}"
else
{clone}
  bash "$dest/install.sh"
fi
'''
        else:
            script = f'''
set -euo pipefail
if gnome-extensions info "{uuid}" >/dev/null 2>&1; then
  echo "Już zainstalowane: {name}"
else
  gext install "{uuid}"
fi
gnome-extensions enable "{uuid}" || gext enable "{uuid}" || echo "Włączy się po wylogowaniu: {name}"
'''
        cmds.append((name, ['bash', '-c', script]))
    return cmds

def wrap_privileged(cmd):
    """paru/yay/sudo → pkexec, żeby GNOME zapytał o FIDO2 zamiast hasła sudo."""
    if not isinstance(cmd, (list, tuple)):
        return cmd
    cmd = list(cmd)
    if not cmd:
        return cmd
    if cmd[0] in ('paru', 'yay'):
        return ['pkexec'] + cmd
    if cmd[0] == 'sudo':
        rest = [c for c in cmd[1:] if c not in ('--askpass', '-S', '-n', '-E')]
        return ['pkexec'] + rest
    return cmd

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
# STEAM — lokalne pliki VDF
# Klucze pochodzą z klienta (steamui.so) i z plików tego konta:
#   sharedconfig  SteamDefaultDialog = #app_games (biblioteka)
#   registry      language
#   config.vdf    ShaderCacheManager/EnableShaderBackgroundProcessing
#                 ShaderCacheManager/DisableShaderCache  ("0" = bufor włączony)
#                 AllowDownloadsDuringGameplay
#   localconfig   system/EnableGameOverlay
#                 system/NetworkingAllowShareIP  0 domyślne, 1 nigdy, 2 znajomi, 3 zawsze
#                 streaming_v2/EnableStreaming
#                 LibraryLowPerfMode, LibraryDisableCommunityContent
#                 GameRecording/BackgroundRecordMode  0 wyłączone, 1 zawsze, 2 ręcznie
# ──────────────────────────────────────────────────────────────

STEAM_START_PAGES = [
    ("Biblioteka", "#app_games"),
    ("Sklep", "#app_store"),
    ("Aktualności", "#app_news"),
    ("Aktywność znajomych", "#steam_menu_friend_activity"),
    ("Społeczność", "#steam_menu_community"),
]

STEAM_LANGUAGES = [
    ("Polski", "polish"),
    ("English", "english"),
    ("Deutsch", "german"),
    ("Français", "french"),
    ("Español", "spanish"),
    ("Español (Latinoamérica)", "latam"),
    ("Italiano", "italian"),
    ("Português", "portuguese"),
    ("Português (Brasil)", "brazilian"),
    ("Nederlands", "dutch"),
    ("Čeština", "czech"),
    ("Magyar", "hungarian"),
    ("Română", "romanian"),
    ("Svenska", "swedish"),
    ("Dansk", "danish"),
    ("Suomi", "finnish"),
    ("Norsk", "norwegian"),
    ("Türkçe", "turkish"),
    ("Русский", "russian"),
    ("Українська", "ukrainian"),
    ("日本語", "japanese"),
    ("한국어", "koreana"),
    ("简体中文", "schinese"),
    ("繁體中文", "tchinese"),
    ("ไทย", "thai"),
    ("Tiếng Việt", "vietnamese"),
    ("Bahasa Indonesia", "indonesian"),
]

STEAM_NETWORKING = [
    ("Domyślne", "0"),
    ("Nigdy", "1"),
    ("Tylko znajomi", "2"),
    ("Zawsze", "3"),
]

STEAM_RECORDING = [
    ("Wyłączone", "0"),
    ("Tylko ręcznie", "2"),
    ("Zawsze w tle", "1"),
]


def steam_is_running():
    for name in ("steam", "steamwebhelper"):
        try:
            result = subprocess.run(["pgrep", "-x", name], capture_output=True)
        except FileNotFoundError:
            return False
        if result.returncode == 0:
            return True
    return False


def steam_layout():
    """Ścieżki natywnego klienta. Puste pola, gdy pliku nie ma."""
    root = os.path.realpath(os.path.expanduser("~/.steam/root"))
    if not os.path.isdir(root):
        root = os.path.realpath(os.path.expanduser("~/.local/share/Steam"))
    if not os.path.isdir(root):
        root = None

    registry = os.path.expanduser("~/.steam/registry.vdf")
    if not os.path.isfile(registry) and root:
        alt = os.path.join(root, "registry.vdf")
        registry = alt if os.path.isfile(alt) else None
    elif not os.path.isfile(registry):
        registry = None

    config = os.path.join(root, "config", "config.vdf") if root else None
    if config and not os.path.isfile(config):
        config = None

    account = None
    newest = -1
    if root:
        user_root = os.path.join(root, "userdata")
        if os.path.isdir(user_root):
            for name in os.listdir(user_root):
                local = os.path.join(user_root, name, "config", "localconfig.vdf")
                if os.path.isfile(local):
                    mtime = os.path.getmtime(local)
                    if mtime >= newest:
                        newest = mtime
                        account = name

    local = shared = None
    if root and account:
        local_path = os.path.join(root, "userdata", account, "config", "localconfig.vdf")
        shared_path = os.path.join(root, "userdata", account, "7", "remote", "sharedconfig.vdf")
        local = local_path if os.path.isfile(local_path) else None
        shared = shared_path if os.path.isfile(shared_path) else None

    return {
        "root": root,
        "account": account,
        "registry": registry,
        "config": config,
        "local": local,
        "shared": shared,
    }


def _vdf_skip(text, index):
    while index < len(text) and text[index] in " \t\r\n":
        index += 1
    return index


def _vdf_string(text, index):
    if index >= len(text) or text[index] != '"':
        raise ValueError("Uszkodzony plik VDF: oczekiwano cudzysłowu")
    index += 1
    start = index
    length = len(text)
    while index < length:
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == '"':
            return text[start:index], start, index, index + 1
        index += 1
    raise ValueError("Uszkodzony plik VDF: niedomknięty napis")


def _vdf_unescape(raw):
    chars = []
    index = 0
    while index < len(raw):
        if raw[index] == "\\" and index + 1 < len(raw):
            chars.append(raw[index + 1])
            index += 2
        else:
            chars.append(raw[index])
            index += 1
    return "".join(chars)


def _vdf_escape(value):
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def _vdf_match_brace(text, open_index):
    index = open_index + 1
    depth = 1
    length = len(text)
    while index < length:
        char = text[index]
        if char == '"':
            _, _, _, index = _vdf_string(text, index)
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    raise ValueError("Uszkodzony plik VDF: niedomknięta sekcja")


def _vdf_block_entries(text, open_index):
    index = open_index + 1
    entries = []
    length = len(text)
    while True:
        index = _vdf_skip(text, index)
        if index >= length:
            raise ValueError("Uszkodzony plik VDF: urwany blok")
        if text[index] == "}":
            return entries, index
        name, _, _, index = _vdf_string(text, index)
        index = _vdf_skip(text, index)
        if index >= length:
            raise ValueError("Uszkodzony plik VDF: urwany klucz")
        if text[index] == "{":
            close = _vdf_match_brace(text, index)
            entries.append({"kind": "sec", "name": name, "open": index, "close": close})
            index = close + 1
        elif text[index] == '"':
            raw, inner_start, inner_end, index = _vdf_string(text, index)
            entries.append({
                "kind": "key",
                "name": name,
                "raw": raw,
                "start": inner_start,
                "end": inner_end,
            })
        else:
            raise ValueError("Uszkodzony plik VDF: przy kluczu " + name)


def _vdf_root_block(text):
    index = _vdf_skip(text, 0)
    name, _, _, index = _vdf_string(text, index)
    index = _vdf_skip(text, index)
    if index >= len(text) or text[index] != "{":
        raise ValueError("Uszkodzony plik VDF: brak głównej sekcji")
    return name, index


def _vdf_locate(text, path):
    """Zwraca blok sekcji albo None, gdy którejś sekcji po drodze nie ma."""
    if not path:
        raise ValueError("Pusta ścieżka sekcji VDF")
    name, open_index = _vdf_root_block(text)
    if name != path[0]:
        return None
    return _vdf_descend(text, open_index, path[1:])


def _vdf_descend(text, open_index, rest):
    entries, close = _vdf_block_entries(text, open_index)
    block = {"open": open_index, "close": close, "entries": entries}
    if not rest:
        return block
    for entry in entries:
        if entry["kind"] == "sec" and entry["name"] == rest[0]:
            return _vdf_descend(text, entry["open"], rest[1:])
    return None


def vdf_get(text, path, key):
    block = _vdf_locate(text, path)
    if not block:
        return None
    for entry in block["entries"]:
        if entry["kind"] == "key" and entry["name"] == key:
            return _vdf_unescape(entry["raw"])
    return None


def _vdf_indent_at(text, index):
    line_start = text.rfind("\n", 0, index) + 1
    end = line_start
    while end < len(text) and text[end] in " \t":
        end += 1
    return text[line_start:end]


def _vdf_render(indent, sections, key, value):
    escaped = _vdf_escape(value)
    if not sections:
        return f'{indent}"{key}"\t\t"{escaped}"\n'
    child = indent + "\t"
    inner = _vdf_render(child, sections[1:], key, value)
    name = sections[0]
    return f'{indent}"{name}"\n{indent}{{\n{inner}{indent}}}\n'


def vdf_set(text, path, key, value):
    """Podmienia jeden klucz. Reszta pliku zostaje bajt w bajt."""
    if not path:
        raise ValueError("Pusta ścieżka sekcji VDF")
    name, open_index = _vdf_root_block(text)
    if name != path[0]:
        raise ValueError("Inna sekcja główna VDF: " + name)

    found = [path[0]]
    node_open = open_index
    missing = path[1:]
    for section in path[1:]:
        entries, _close = _vdf_block_entries(text, node_open)
        match = None
        for entry in entries:
            if entry["kind"] == "sec" and entry["name"] == section:
                match = entry
                break
        if match is None:
            missing = path[len(found):]
            break
        found.append(section)
        node_open = match["open"]
        missing = []

    entries, close = _vdf_block_entries(text, node_open)
    if not missing:
        for entry in entries:
            if entry["kind"] == "key" and entry["name"] == key:
                if _vdf_unescape(entry["raw"]) == str(value):
                    return text
                escaped = _vdf_escape(value)
                return text[:entry["start"]] + escaped + text[entry["end"]:]

    brace_indent = _vdf_indent_at(text, close)
    blob = _vdf_render(brace_indent + "\t", missing, key, value)
    line_start = text.rfind("\n", 0, close) + 1
    return text[:line_start] + blob + text[line_start:]


def read_vdf_key(path, sections, key):
    if not path or not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8", newline="") as handle:
        return vdf_get(handle.read(), sections, key)


def write_vdf_keys(path, changes):
    """changes: lista (sections, key, value). Zapis atomowy, pierwsza kopia .settler.bak."""
    with open(path, encoding="utf-8", newline="") as handle:
        original = handle.read()
    text = original
    for sections, key, value in changes:
        text = vdf_set(text, sections, key, value)
    if text == original:
        return False
    backup = path + ".settler.bak"
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
    temporary = path + ".settler.tmp"
    mode = os.stat(path).st_mode
    try:
        with open(temporary, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.chmod(temporary, stat.S_IMODE(mode))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)
    return True

# ──────────────────────────────────────────────────────────────
# DIALOG HASŁA
# ──────────────────────────────────────────────────────────────

class AskPasswordDialog(Adw.Dialog):
    """Graficzny dialog prośby o hasło sudo."""
    def __init__(self, callback, on_cancel=None):
        super().__init__()
        self.set_title("Uwierzytelnienie")
        self.set_content_width(420)
        self.callback = callback
        self.on_cancel = on_cancel
        self._password = None
        self._resolved = False

        tv = Adw.ToolbarView()
        hb = Adw.HeaderBar()
        tv.add_top_bar(hb)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        vbox.set_margin_top(20)
        vbox.set_margin_bottom(20)
        vbox.set_margin_start(16)
        vbox.set_margin_end(16)

        icon = Gtk.Image.new_from_icon_name('dialog-password-symbolic')
        icon.set_pixel_size(48)
        vbox.append(icon)

        title = Gtk.Label(label="Wymagane hasło sudo")
        title.add_css_class('title-2')
        vbox.append(title)

        subtitle = Gtk.Label(label="Podaj hasło użytkownika aby zainstalować pakiety.")
        subtitle.add_css_class('dim-label')
        subtitle.set_wrap(True)
        subtitle.set_justify(Gtk.Justification.CENTER)
        subtitle.set_max_width_chars(40)
        vbox.append(subtitle)

        group = Adw.PreferencesGroup()
        self.entry = Adw.PasswordEntryRow()
        self.entry.set_title("Hasło")
        # FREE_FORM + PRIVATE: InputPurpose.PASSWORD + IBus na GTK 4.22
        # potrafiły przyjąć / pokazać tylko jeden znak.
        self.entry.set_input_hints(
            Gtk.InputHints.NO_EMOJI
            | Gtk.InputHints.NO_SPELLCHECK
            | Gtk.InputHints.PRIVATE
        )
        self.entry.set_input_purpose(Gtk.InputPurpose.FREE_FORM)
        self.entry.connect('entry-activated', self._on_ok)
        group.add(self.entry)
        vbox.append(group)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button(label="Anuluj")
        cancel_btn.connect('clicked', self._on_cancel)
        btn_box.append(cancel_btn)

        ok_btn = Gtk.Button(label="OK")
        ok_btn.add_css_class('suggested-action')
        ok_btn.connect('clicked', self._on_ok)
        btn_box.append(ok_btn)

        vbox.append(btn_box)
        tv.set_content(vbox)
        self.set_child(tv)

        self.connect('closed', self._on_closed)
        GLib.idle_add(self.entry.grab_focus)

    def _on_ok(self, *_):
        if self._resolved:
            return
        password = self.entry.get_text()
        if not password:
            return
        self._resolved = True
        self._password = password
        self.close()
        self.callback(self._password)

    def _on_cancel(self, *_):
        if self._resolved:
            return
        self._resolved = True
        self.close()
        if self.on_cancel:
            self.on_cancel()

    def _on_closed(self, *_):
        if self._resolved:
            return
        self._resolved = True
        if self.on_cancel:
            self.on_cancel()


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

        # Uprawnienia przez pkexec/polkit (FIDO2), bez własnego okna na hasło sudo.
        if any(cmd_needs_privilege(cmd) for _, cmd in commands):
            GLib.idle_add(
                self.status.set_text,
                "Gdy pojawi się okno uprawnień — nic nie wpisuj, tapnij klucz FIDO2.",
            )
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        env = os.environ.copy()
        env.pop('SUDO_ASKPASS', None)

        failed = []
        total = len(self.commands)
        for i, (label, cmd) in enumerate(self.commands):
            GLib.idle_add(self.status.set_text, f"[{i+1}/{total}] {label}")
            GLib.idle_add(self.progress.set_text, f"{i+1} / {total}")

            cmd = wrap_privileged(cmd)

            GLib.idle_add(self._append, f"\n$ {' '.join(cmd)}\n")
            rc = 1
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    env=env,
                    text=False
                )
                for raw_line in proc.stdout:
                    try:
                        line = raw_line.decode('utf-8', errors='replace')
                    except Exception:
                        line = str(raw_line)
                    GLib.idle_add(self._append, line)
                rc = proc.wait()
            except Exception as e:
                GLib.idle_add(self._append, f"[BŁĄD] {e}\n")
                rc = 1
            if rc != 0:
                failed.append(label)
                GLib.idle_add(self._append, f"[BŁĄD] {label} zakończone kodem {rc}\n")
            GLib.idle_add(self.progress.set_fraction, (i + 1) / total)

        if failed:
            GLib.idle_add(self.status.set_text, f"Zakończono z błędami ({len(failed)})")
            GLib.idle_add(self._append, "\n✗ Nie wszystkie operacje się powiodły.\n")
        else:
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

        tools = Adw.PreferencesGroup()
        tools.set_title("Na start")
        missing = tools_missing()
        tools_row = Adw.ActionRow()
        tools_row.set_title("Narzędzia Settlera")
        if missing:
            tools_row.set_subtitle("Brakuje: " + ", ".join(missing))
            tools_btn = Gtk.Button(label="Zainstaluj narzędzia")
            tools_btn.add_css_class('suggested-action')
            tools_btn.set_valign(Gtk.Align.CENTER)
            tools_btn.connect('clicked', self.on_tools)
            tools_row.add_suffix(tools_btn)
        else:
            tools_row.set_subtitle("git, curl, base-devel, paru, flatpak, Flathub i gext są na miejscu")
        tools.add(tools_row)
        self.add(tools)

        descriptions = {
            "Programy": "Zaznaczone zostaną zainstalowane. Już zainstalowane są wyszarzone.",
            "Gry": "Te narzędzia można też dołożyć na stronie Gaming.",
            "Flatpak": "Flathub oraz własne paczki Flatpak z GitHuba.",
            "GitHub": "Programy z github.com/GorianWaco. Pozycje „brak” czekają na repozytorium.",
        }
        groups = {}
        for prog in PROGRAMS:
            group = groups.get(prog['group'])
            if group is None:
                group = Adw.PreferencesGroup()
                group.set_title(prog['group'])
                group.set_description(descriptions.get(prog['group'], ""))
                groups[prog['group']] = group
                self.add(group)
            group.add(self._row(prog))

        btn_group = Adw.PreferencesGroup()
        install_row = Adw.ActionRow()
        install_row.set_title("Zainstaluj zaznaczone programy")
        install_row.set_subtitle("Pacman, AUR, Flatpak i skrypty z GitHuba. Hasła nie wpisuj — tapnij klucz.")
        btn = Gtk.Button(label="Zainstaluj zaznaczone")
        btn.add_css_class('suggested-action')
        btn.set_valign(Gtk.Align.CENTER)
        btn.connect('clicked', self.on_install)
        install_row.add_suffix(btn)
        btn_group.add(install_row)
        self.add(btn_group)

    def _row(self, prog):
        row = Adw.ActionRow()
        row.set_title(prog['name'])
        row.set_subtitle(prog['desc'])
        label, css = source_tag(prog)
        tag = Gtk.Label(label=label)
        tag.add_css_class(css)
        tag.set_valign(Gtk.Align.CENTER)
        row.add_suffix(tag)

        if prog['source'] == 'unavailable':
            return row

        installed = is_program_installed(prog)
        if installed:
            badge = Gtk.Label(label="✓")
            badge.add_css_class('installed-badge')
            badge.set_valign(Gtk.Align.CENTER)
            row.add_suffix(badge)
        else:
            check = Gtk.CheckButton()
            check.set_active(True)
            check.set_sensitive(True)
            self.checks[prog['id']] = check
            row.add_suffix(check)
            row.set_activatable_widget(check)

        if prog.get('copy'):
            copy_btn = Gtk.Button()
            copy_btn.set_icon_name('edit-copy-symbolic')
            copy_btn.set_valign(Gtk.Align.CENTER)
            copy_btn.set_tooltip_text("Kopiuj komendę instalacji")
            copy_btn.connect('clicked', self._copy, prog['copy'])
            row.add_suffix(copy_btn)
        return row

    def _copy(self, _btn, text):
        self.get_display().get_clipboard().set(text)

    def on_tools(self, _):
        InstallDialog(tool_setup_commands(), 'Narzędzia', parent=self.win).present(self.win)

    def on_install(self, _):
        selected = []
        by_id = {prog['id']: prog for prog in PROGRAMS}
        for prog_id, check in self.checks.items():
            if check.get_active():
                selected.append(by_id[prog_id])
        if not selected:
            return
        InstallDialog(commands_for_programs(selected), 'Instalacja programów', parent=self.win).present(self.win)

# ──────────────────────────────────────────────────────────────
# STRONA: WYGLĄD
# ──────────────────────────────────────────────────────────────

class AppearancePage(Adw.PreferencesPage):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.set_title("Wygląd")
        self.set_icon_name("preferences-desktop-appearance-symbolic")

        # ─── Reset GNOME ─────────────────────────
        reset_group = Adw.PreferencesGroup()
        reset_group.set_title("Reset")
        reset_group.set_description("Przywraca domyślne ustawienia GNOME (może wymagać wylogowania lub restartu)")

        reset_row = Adw.ActionRow()
        reset_row.set_title("Resetuj ustawienia GNOME")
        reset_row.set_subtitle("Ikony, kursory, tapety, akcenty, ciemny motyw, mysz, zasilanie i inne")

        reset_btn = Gtk.Button(label="Resetuj wszystko")
        reset_btn.add_css_class("destructive-action")
        reset_btn.set_valign(Gtk.Align.CENTER)
        reset_btn.connect("clicked", self._reset_gnome_settings)
        reset_row.add_suffix(reset_btn)
        reset_group.add(reset_row)
        self.add(reset_group)

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

    def _set_accent(self, _btn, ac):
        gsettings_set('org.gnome.desktop.interface', 'accent-color', ac['value'])

    def _apply_icons(self, _):
        t = ICON_THEMES[self.icon_combo.get_selected()]
        cmds = []
        if t['pkg'] and not is_pkg_installed(t['pkg']):
            cmds.extend(ensure_aur_helper_cmds())
            cmds.append((f"Instalacja {t['pkg']}", aur_install_command([t['pkg']])))
        cmds.append(("Ustawianie ikon", ['gsettings', 'set',
                     'org.gnome.desktop.interface', 'icon-theme', t['value']]))
        InstallDialog(cmds, 'Ikony', parent=self.win).present(self.win)

    def _apply_cursor(self, _):
        t = CURSOR_THEMES[self.cursor_combo.get_selected()]
        cmds = []
        if t['pkg'] and not is_pkg_installed(t['pkg']):
            cmds.extend(ensure_aur_helper_cmds())
            cmds.append((f"Instalacja {t['pkg']}", aur_install_command([t['pkg']])))
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
            cmds.extend(ensure_aur_helper_cmds())
            cmds.append(("Instalacja gnome-extensions-cli (gext)", aur_install_command(['gnome-extensions-cli'])))
            cmds.append(("Instalacja rozszerzenia User Themes", ['gext', 'install', 'user-theme@gnome-shell-extensions.gcampax.github.com']))
            cmds.append(("Włączanie User Themes", ['gnome-extensions', 'enable', 'user-theme@gnome-shell-extensions.gcampax.github.com']))

        if t and t.get('pkg') and not is_pkg_installed(t['pkg']):
            cmds.extend(ensure_aur_helper_cmds())
            cmds.append((f"Instalacja {t['pkg']}", aur_install_command([t['pkg']])))

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

    def _reset_gnome_settings(self, _):
        """Resetuje ustawienia GNOME do domyślnych wartości."""
        schemas = [
            "org.gnome.desktop.interface",
            "org.gnome.desktop.wm.preferences",
            "org.gnome.desktop.background",
            "org.gnome.desktop.peripherals.mouse",
            "org.gnome.settings-daemon.plugins.power",
            "org.gnome.desktop.session",
            "org.gnome.shell.extensions.user-theme",
        ]
        cmds = []
        for schema in schemas:
            cmds.append((f"Reset {schema}", ["gsettings", "reset-recursively", schema]))
        # Usuń niestandardowe pliki CSS
        cmds.append(("Usuń niestandardowe style GTK4", ["rm", "-f", os.path.expanduser("~/.config/gtk-4.0/gtk.css")]))
        cmds.append(("Usuń niestandardowe style GTK3", ["rm", "-f", os.path.expanduser("~/.config/gtk-3.0/gtk.css")]))
        cmds.append(("Informacja", ["echo", "Zalecane: wyloguj się i zaloguj ponownie, aby zastosować wszystkie zmiany."]))
        InstallDialog(cmds, "Reset ustawień GNOME", parent=self.win).present(self.win)

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
        self._steam_guard = False
        self._steam_busy = False
        self._steam_loaded = {}
        self._build_steam()

        tools_group = Adw.PreferencesGroup()
        tools_group.set_title("Narzędzia gamingowe")

        gaming_pkgs = [
            ("GameMode",         "gamemode",               "Optymalizacja systemu dla gier",      "pacman"),
            ("GameMode 32-bit",  "lib32-gamemode",         "Wsparcie gier 32-bit",                "pacman"),
            ("MangoHud",         "mangohud",               "Overlay FPS/GPU/CPU/temp w grach",    "pacman"),
            ("MangoHud 32-bit",  "lib32-mangohud",         "Wsparcie gier 32-bit",                "pacman"),
            ("Wine",             "wine",                   "Uruchamianie gier i programów Win",   "pacman"),
            ("Wine Mono",        "wine-mono",              "Obsługa .NET w Wine",                 "pacman"),
            ("Winetricks",       "winetricks",             "Skrypty konfiguracji Wine",           "pacman"),
            ("Lutris",           "lutris",                 "Manager gier Linux",                  "pacman"),
            ("Heroic Games",     "heroic-games-launcher",  "Launcher Epic Games i GOG",           "pacman"),
            ("Steam",            "steam",                  "Platforma gamingowa Valve",           "pacman"),
            ("btop",             "btop",                   "Monitor systemu w terminalu",         "pacman"),
            ("ProtonUp-Qt",      "protonup-qt",            "Manager wersji GE-Proton",            "pacman"),
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

    def _build_steam(self):
        group = Adw.PreferencesGroup()
        group.set_title("Konfiguracja Steam")
        group.set_description(
            "Zapis do plików tego konta. Gdy klient jest włączony, "
            "Settler pyta, czy go zamknąć — przy wyjściu Steam zapisuje własną kopię ustawień."
        )

        self._steam_status = Adw.ActionRow()
        self._steam_status.set_title("Stan")
        group.add(self._steam_status)

        self._steam_start = self._steam_combo_row(
            group, "Strona startowa",
            "Okno po uruchomieniu klienta. Biblioteka to strona gier",
            STEAM_START_PAGES,
        )
        self._steam_lang = self._steam_combo_row(
            group, "Język klienta",
            "Obowiązuje po ponownym uruchomieniu Steam",
            STEAM_LANGUAGES,
        )
        if hasattr(self._steam_lang, "set_enable_search"):
            self._steam_lang.set_enable_search(True)

        self._steam_overlay = self._steam_switch_row(
            group, "Wyłącz nakładkę Steam w grze",
            "Bez nakładki i skrótu Shift+Tab w trakcie gry",
        )
        self._steam_net = self._steam_combo_row(
            group, "Funkcje sieciowe Steam",
            "Kiedy gra może udostępnić adres IP, żeby połączenie było szybsze",
            STEAM_NETWORKING,
        )
        self._steam_remote = self._steam_switch_row(
            group, "Wyłącz Remote Play",
            "Bez strumieniowania rozgrywki na inne urządzenia",
        )
        self._steam_shader = self._steam_switch_row(
            group, "Wstępne buforowanie shaderów",
            "Pobiera gotowe shadery Vulkan i OpenGL pod tę kartę",
        )
        self._steam_shader_bg = self._steam_switch_row(
            group, "Zezwalaj na przetwarzanie shaderów Vulkan w tle",
            "Kompiluje shadery Vulkan, gdy żadna gra nie jest uruchomiona",
        )
        self.add(group)

        extra = Adw.PreferencesGroup()
        extra.set_title("Dodatkowe ustawienia Steam")
        extra.set_description(
            "Zapisują się dopiero po zmianie. Zostawione tak, jak ma je teraz klient."
        )
        self._steam_downloads = self._steam_switch_row(
            extra, "Pobieraj aktualizacje podczas gry",
            "Pobieranie może iść w tle w trakcie rozgrywki",
        )
        self._steam_lowperf = self._steam_switch_row(
            extra, "Tryb lekkiej biblioteki",
            "Mniej animacji na liście gier",
        )
        self._steam_community = self._steam_switch_row(
            extra, "Ukryj treści społeczności w bibliotece",
            "Strona gry otwiera się bez automatycznych materiałów społeczności",
        )
        self._steam_recording = self._steam_combo_row(
            extra, "Nagrywanie rozgrywki",
            "Ciągłe nagrywanie w tle zajmuje dysk i kartę graficzną",
            STEAM_RECORDING,
        )
        self.add(extra)
        self._load_steam_widgets()

    def _steam_combo_row(self, group, title, subtitle, pairs):
        row = Adw.ActionRow()
        row.set_title(title)
        row.set_subtitle(subtitle)
        model = Gtk.StringList.new([label for label, _value in pairs])
        expression = Gtk.PropertyExpression.new(Gtk.StringObject, None, "string")
        combo = Gtk.DropDown.new(model, expression)
        combo._base_pairs = list(pairs)
        combo._pairs = list(pairs)
        combo.set_valign(Gtk.Align.CENTER)
        combo.set_size_request(220, -1)
        combo._row = row
        combo.connect("notify::selected", self._steam_changed)
        row.add_suffix(combo)
        group.add(row)
        return combo

    def _steam_switch_row(self, group, title, subtitle):
        row = Adw.SwitchRow()
        row.set_title(title)
        row.set_subtitle(subtitle)
        row.connect("notify::active", self._steam_changed)
        group.add(row)
        return row

    def _steam_changed(self, *_args):
        if self._steam_guard or self._steam_busy:
            return
        self._steam_guard = True
        if not self._steam_shader.get_active() and self._steam_shader_bg.get_active():
            self._steam_shader_bg.set_active(False)
        self._steam_shader_bg.set_sensitive(
            self._steam_shader.get_active() and self._steam_shader.get_sensitive()
        )
        self._steam_guard = False
        self._apply_steam()

    def _set_combo_value(self, combo, current):
        pairs = list(combo._base_pairs)
        known = {value for _label, value in pairs}
        if current not in known:
            label = "Zostaw domyślne" if current is None else f"Obecne ({current})"
            pairs.insert(0, (label, current))
        labels = [label for label, _value in pairs]
        combo._pairs = pairs
        combo.set_model(Gtk.StringList.new(labels))
        selected = 0
        for index, (_label, value) in enumerate(pairs):
            if value == current:
                selected = index
                break
        combo.set_selected(selected)

    def _combo_value(self, combo):
        index = combo.get_selected()
        pairs = combo._pairs
        if index is None or index < 0 or index >= len(pairs):
            return None
        return pairs[index][1]

    def _widget_state(self):
        shader = bool(self._steam_shader.get_active())
        return {
            "start": self._combo_value(self._steam_start),
            "language": self._combo_value(self._steam_lang),
            "overlay_off": bool(self._steam_overlay.get_active()),
            "networking": self._combo_value(self._steam_net),
            "remote_off": bool(self._steam_remote.get_active()),
            "shader": shader,
            "shader_bg": bool(self._steam_shader_bg.get_active()) and shader,
            "downloads": bool(self._steam_downloads.get_active()),
            "lowperf": bool(self._steam_lowperf.get_active()),
            "hide_community": bool(self._steam_community.get_active()),
            "recording": self._combo_value(self._steam_recording),
        }

    def _load_steam_widgets(self):
        self._steam_guard = True
        try:
            layout = steam_layout()
            local = layout["local"]
            config = layout["config"]
            registry = layout["registry"]
            shared = layout["shared"]

            steam_root = ["UserLocalConfigStore"]
            valve = ["InstallConfigStore", "Software", "Valve", "Steam"]
            roaming = ["UserRoamingConfigStore", "Software", "Valve", "Steam"]
            reg_steam = ["Registry", "HKCU", "Software", "Valve", "Steam"]

            start = read_vdf_key(shared, roaming, "SteamDefaultDialog")
            language = read_vdf_key(registry, reg_steam, "language")
            overlay = read_vdf_key(local, steam_root + ["system"], "EnableGameOverlay")
            networking = read_vdf_key(local, steam_root + ["system"], "NetworkingAllowShareIP")
            streaming = read_vdf_key(local, steam_root + ["streaming_v2"], "EnableStreaming")
            shader_off = read_vdf_key(config, valve + ["ShaderCacheManager"], "DisableShaderCache")
            shader_bg = read_vdf_key(
                config, valve + ["ShaderCacheManager"], "EnableShaderBackgroundProcessing")
            downloads = read_vdf_key(config, valve, "AllowDownloadsDuringGameplay")
            lowperf = read_vdf_key(local, steam_root, "LibraryLowPerfMode")
            community = read_vdf_key(local, steam_root, "LibraryDisableCommunityContent")
            recording = read_vdf_key(local, steam_root + ["GameRecording"], "BackgroundRecordMode")

            self._steam_start._row.set_sensitive(bool(shared))
            self._steam_lang._row.set_sensitive(bool(registry))
            local_ok = bool(local)
            config_ok = bool(config)
            self._steam_overlay.set_sensitive(local_ok)
            self._steam_net._row.set_sensitive(local_ok)
            self._steam_remote.set_sensitive(local_ok)
            self._steam_lowperf.set_sensitive(local_ok)
            self._steam_community.set_sensitive(local_ok)
            self._steam_recording._row.set_sensitive(local_ok)
            self._steam_shader.set_sensitive(config_ok)
            self._steam_downloads.set_sensitive(config_ok)

            self._set_combo_value(self._steam_start, start)
            self._set_combo_value(self._steam_lang, language)
            self._steam_overlay.set_active(overlay == "0")
            self._set_combo_value(self._steam_net, networking if networking is not None else "0")
            self._steam_remote.set_active(streaming == "0")
            self._steam_shader.set_active(shader_off != "1")
            self._steam_shader_bg.set_active(shader_bg == "1")
            self._steam_shader_bg.set_sensitive(config_ok and shader_off != "1")
            self._steam_downloads.set_active(downloads != "0")
            self._steam_lowperf.set_active(lowperf == "1")
            self._steam_community.set_active(community == "1")
            self._set_combo_value(self._steam_recording, recording)
            self._steam_loaded = self._widget_state()
            self._set_default_steam_status(layout)
        finally:
            self._steam_guard = False

    def _set_default_steam_status(self, layout=None):
        layout = layout or steam_layout()
        if not layout["root"]:
            self._steam_status.set_subtitle("Nie znaleziono katalogu Steam.")
            return
        if not layout["account"]:
            self._steam_status.set_subtitle("Steam jest, brak katalogu konta w userdata.")
            return
        if steam_is_running():
            state = "Klient działa. Zapis zamknie go przed zmianą plików"
        else:
            state = "Klient jest wyłączony"
        self._steam_status.set_subtitle(f"Konto {layout['account']}. {state}.")

    def _set_steam_status(self, text):
        self._steam_status.set_subtitle(text)

    def _apply_steam(self):
        if self._steam_guard or self._steam_busy:
            return
        if steam_is_running():
            self._steam_busy = True
            self._ask_steam_quit()
            return
        self._steam_busy = True
        self._steam_write_finish(False)

    def _ask_steam_quit(self):
        dialog = Adw.AlertDialog()
        dialog.set_heading("Steam jest uruchomiony")
        dialog.set_body(
            "Steam zapisuje swoje pliki przy wyjściu. "
            "Zamknięcie klienta kończy też uruchomioną grę. "
            "Zamknąć go teraz i zapisać to ustawienie?"
        )
        dialog.add_response("cancel", "Anuluj")
        dialog.add_response("apply", "Zamknij Steam i zapisz")
        dialog.set_response_appearance("apply", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("apply")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_steam_quit_response)
        dialog.present(self.win)

    def _on_steam_quit_response(self, _dialog, response):
        if response != "apply":
            self._steam_busy = False
            self._load_steam_widgets()
            self._set_steam_status("Anulowano. Steam nadal działa.")
            return
        self._set_steam_status("Zamykam Steam…")
        threading.Thread(target=self._quit_steam_and_write, daemon=True).start()

    def _quit_steam_and_write(self):
        try:
            subprocess.run(["steam", "-shutdown"], capture_output=True, text=True)
        except FileNotFoundError:
            GLib.idle_add(self._steam_fail, "Nie znaleziono polecenia steam.")
            return
        deadline = time.time() + 25
        while time.time() < deadline:
            if not steam_is_running():
                break
            time.sleep(0.5)
        else:
            GLib.idle_add(
                self._steam_fail,
                "Steam nie zamknął się w ciągu 25 sekund. Nic nie zapisano.",
            )
            return
        self._wait_steam_files()
        GLib.idle_add(self._steam_write_finish, True)

    def _wait_steam_files(self):
        path = steam_layout().get("local")
        if not path:
            time.sleep(0.4)
            return
        last = None
        stable = 0
        for _ in range(15):
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                return
            if mtime == last:
                stable += 1
                if stable >= 2:
                    return
            else:
                stable = 0
                last = mtime
            time.sleep(0.3)

    def _steam_fail(self, message):
        self._steam_busy = False
        self._load_steam_widgets()
        self._set_steam_status(message)
        return False

    def _steam_write_finish(self, closed_steam):
        try:
            written = self._write_steam_changes()
        except Exception as exc:
            self._steam_busy = False
            self._load_steam_widgets()
            self._set_steam_status("Nie zapisano: " + str(exc))
            return False
        self._steam_busy = False
        if written:
            lead = "Steam zamknięty. " if closed_steam else ""
            self._set_steam_status(lead + "Zapisane. Uruchom Steam ponownie.")
            self._steam_loaded = self._widget_state()
        elif closed_steam:
            self._set_steam_status("Steam zamknięty. Pliki bez zmian.")
        else:
            self._set_steam_status("Bez zmian w plikach.")
        return False

    def _write_steam_changes(self):
        layout = steam_layout()
        state = self._widget_state()
        loaded = self._steam_loaded
        grouped = {}

        def queue(path, sections, key, new, old):
            if not path or new is None or new == old:
                return
            grouped.setdefault(path, []).append((sections, key, new))

        roaming = ["UserRoamingConfigStore", "Software", "Valve", "Steam"]
        reg_steam = ["Registry", "HKCU", "Software", "Valve", "Steam"]
        reg_global = ["Registry", "HKCU", "Software", "Valve", "Steamsteamglobal"]
        valve = ["InstallConfigStore", "Software", "Valve", "Steam"]
        shaders = valve + ["ShaderCacheManager"]
        root = ["UserLocalConfigStore"]

        queue(layout["shared"], roaming, "SteamDefaultDialog", state["start"], loaded.get("start"))
        queue(layout["registry"], reg_steam, "language", state["language"], loaded.get("language"))
        queue(layout["registry"], reg_global, "language", state["language"], loaded.get("language"))
        queue(
            layout["config"], shaders, "DisableShaderCache",
            "0" if state["shader"] else "1",
            "0" if loaded.get("shader", True) else "1",
        )
        queue(
            layout["config"], shaders, "EnableShaderBackgroundProcessing",
            "1" if state["shader_bg"] else "0",
            "1" if loaded.get("shader_bg") else "0",
        )
        queue(
            layout["config"], valve, "AllowDownloadsDuringGameplay",
            "1" if state["downloads"] else "0",
            "1" if loaded.get("downloads", True) else "0",
        )
        queue(
            layout["local"], root + ["system"], "EnableGameOverlay",
            "0" if state["overlay_off"] else "1",
            "0" if loaded.get("overlay_off") else "1",
        )
        queue(
            layout["local"], root + ["system"], "NetworkingAllowShareIP",
            state["networking"], loaded.get("networking"),
        )
        queue(
            layout["local"], root + ["streaming_v2"], "EnableStreaming",
            "0" if state["remote_off"] else "1",
            "0" if loaded.get("remote_off") else "1",
        )
        queue(
            layout["local"], root, "LibraryLowPerfMode",
            "1" if state["lowperf"] else "0",
            "1" if loaded.get("lowperf") else "0",
        )
        queue(
            layout["local"], root, "LibraryDisableCommunityContent",
            "1" if state["hide_community"] else "0",
            "1" if loaded.get("hide_community") else "0",
        )
        queue(
            layout["local"], root + ["GameRecording"], "BackgroundRecordMode",
            state["recording"], loaded.get("recording"),
        )

        written = []
        for path, changes in grouped.items():
            if write_vdf_keys(path, changes):
                written.append(os.path.basename(path))
        return written

    def _install_tools(self, _):
        pacman, aur = [], []
        for pkg, (check, src) in self.checks.items():
            if check.get_active():
                (pacman if src == 'pacman' else aur).append(pkg)
        cmds = []
        if pacman:
            cmds.append(("Instalacja (pacman)", ['pkexec', 'pacman', '-S', '--needed', '--noconfirm'] + pacman))
        if aur:
            cmds.extend(ensure_aur_helper_cmds())
            helper = find_aur_helper() or 'paru'
            cmds.append((f"Instalacja AUR ({helper})", aur_install_command(aur)))
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
                ensure_aur_helper_cmds() +
                [("Instalacja gext", aur_install_command(['gnome-extensions-cli']))],
                "gext", parent=self.win).present(self.win))
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
        if any(not ext['active'] for ext in EXTENSIONS):
            self.add(inactive_group)

    def _toggle(self, row, _, uuid):
        action = 'enable' if row.get_active() else 'disable'
        subprocess.run(['gnome-extensions', action, uuid], capture_output=True)

    def _install_all(self, _):
        InstallDialog(extension_install_commands(), 'Instalacja rozszerzeń', parent=self.win).present(self.win)

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
        cmds = ensure_aur_helper_cmds() + [
            ("Instalacja keyd", aur_install_command(['keyd'])),
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
        cmds = ensure_aur_helper_cmds() + [
            ("Instalacja OpenRazer", aur_install_command(['openrazer-meta', 'polychromatic'])),
        ]
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
            preferencespage, clamp {
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
                        f'preferencespage, clamp '
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
