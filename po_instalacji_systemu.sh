# GNOME / integracja
sudo pacman -S --needed --noconfirm \
  gnome-weather \
  gnome-shell-extensions \
  xdg-desktop-portal-gnome \
  power-profiles-daemon

# Firmware (CachyOS)
sudo pacman -S --needed --noconfirm linux-firmware

# Opcjonalnie: hook po reboot dla grup
# gamemode, openrazer, input — wymagają re-loginu (już masz echo, OK)




#!/bin/bash
# ============================================================
#  PO INSTALACJI SYSTEMU - CachyOS
#  Uruchom: bash ~/po_instalacji_systemu.sh
# ============================================================


# ============================================================
# 1. AUR HELPER - paru
# ============================================================
sudo pacman -S --needed --noconfirm base-devel git
git clone https://aur.archlinux.org/paru.git /tmp/paru
cd /tmp/paru && makepkg -si --noconfirm
cd ~


# ============================================================
# 2. WŁĄCZ MULTILIB (wymagane przez Steam)
# ============================================================
sudo sed -i '/^#\[multilib\]/s/^#//' /etc/pacman.conf
sudo sed -i '/^\[multilib\]/{n;s/^#//}' /etc/pacman.conf
sudo pacman -Syu --noconfirm


# ============================================================
# 3. STEROWNIKI NVIDIA
# ============================================================
sudo pacman -S --noconfirm nvidia-dkms nvidia-utils lib32-nvidia-utils nvidia-settings

# Parametry modułu
echo "options nvidia-drm modeset=1 fbdev=1" | sudo tee /etc/modprobe.d/nvidia.conf
echo "options nvidia NVreg_EnableGpuFirmware=0" | sudo tee -a /etc/modprobe.d/nvidia.conf
sudo mkinitcpio -P


# ============================================================
# 4. AUDIO - PipeWire (bez PulseAudio)
# ============================================================
# Usuń PulseAudio jeśli zainstalowany
sudo pacman -Rdd --noconfirm pulseaudio pulseaudio-alsa 2>/dev/null || true

sudo pacman -S --noconfirm \
  pipewire \
  pipewire-alsa \
  pipewire-pulse \
  pipewire-jack \
  wireplumber

systemctl --user disable --now pulseaudio.socket pulseaudio.service 2>/dev/null || true
systemctl --user enable --now pipewire pipewire-pulse wireplumber


# ============================================================
# 5. FLATPAK + FLATHUB
# ============================================================
sudo pacman -S --noconfirm flatpak
flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo


# ============================================================
# 6. GAMING
# ============================================================
sudo pacman -S --noconfirm \
  steam \
  gamemode \
  lib32-gamemode \
  mangohud \
  lib32-mangohud \
  lutris \
  wine \
  wine-mono \
  winetricks

# Dodaj do grupy gamemode
sudo usermod -aG gamemode $USER

# ProtonUp-Qt (zarządzanie GE-Proton)
paru -S --noconfirm protonup-qt


# ============================================================
# 7. PRZEGLĄDARKI
# ============================================================
sudo pacman -S --noconfirm firefox
paru -S --noconfirm brave-bin


# ============================================================
# 8. MULTIMEDIA
# ============================================================
sudo pacman -S --noconfirm \
  vlc \
  obs-studio \
  gimp \
  kdenlive \
  ardour \
  mixxx


# ============================================================
# 9. KOMUNIKATORY
# ============================================================
sudo pacman -S --noconfirm discord
paru -S --noconfirm spotify


# ============================================================
# 10. BIURO I NARZĘDZIA
# ============================================================
sudo pacman -S --noconfirm \
  libreoffice-fresh \
  libreoffice-fresh-pl \
  btop \
  htop

# VS Code
paru -S --noconfirm visual-studio-code-bin


# ============================================================
# 11. DODATKOWE PROGRAMY (AUR)
# ============================================================
paru -S --noconfirm \
  heroic-games-launcher-bin \
  firestorm-bin \
  openrgb


# ============================================================
# 12. USTAWIENIA SYSTEMU (GNOME)
# ============================================================

# --- Zasilanie ---
# Tryb wydajności
powerprofilesctl set performance
# Wyłącz automatyczne usypianie (na zasilaniu)
gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'nothing'
# Wyłącz przygaszanie ekranu
gsettings set org.gnome.settings-daemon.plugins.power idle-dim false
# Wyłącz wygaszacz / auto-blokada
gsettings set org.gnome.desktop.session idle-delay 0
# Przycisk zasilania = menu zamykania
gsettings set org.gnome.settings-daemon.plugins.power power-button-action 'interactive'

# --- Mysz ---
# Prędkość kursora
gsettings set org.gnome.desktop.peripherals.mouse speed 0.0
# Wyłącz przyspieszenie myszy
gsettings set org.gnome.desktop.peripherals.mouse accel-profile 'flat'
# Tradycyjny kierunek przewijania
gsettings set org.gnome.desktop.peripherals.mouse natural-scroll false

# --- Pasek tytułu okien ---
# Przyciski: minimalizacja + maksymalizacja po prawej stronie
gsettings set org.gnome.desktop.wm.preferences button-layout 'appmenu:minimize,maximize,close'

# --- Monitor (3440x1440 180Hz HDR - Xiaomi Mi Monitor) ---
mkdir -p ~/.config
cat > ~/.config/monitors.xml << 'EOF'
<monitors version="2">
  <configuration>
    <layoutmode>logical</layoutmode>
    <logicalmonitor>
      <x>0</x>
      <y>0</y>
      <scale>1</scale>
      <primary>yes</primary>
      <monitor>
        <monitorspec>
          <connector>DP-1</connector>
          <vendor>XMI</vendor>
          <product>Mi monitor</product>
          <serial>5505610025927</serial>
        </monitorspec>
        <mode>
          <width>3440</width>
          <height>1440</height>
          <rate>180.000</rate>
        </mode>
        <colormode>bt2100</colormode>
      </monitor>
    </logicalmonitor>
  </configuration>
</monitors>
EOF


# ============================================================
# 13. OPTYMALIZACJA SYSTEMU
# ============================================================

# vm.swappiness - niższa wartość = mniej swapu, lepsze dla gamingu
echo "vm.swappiness=10" | sudo tee /etc/sysctl.d/99-swappiness.conf
sudo sysctl --system

# Włącz OpenRGB przy starcie systemu
sudo systemctl enable --now openrgb


# ============================================================
# 13. PERYFERIA - RAZER (klawiatura i myszka)
# ============================================================
paru -S --noconfirm openrazer-meta polychromatic

# Na Arch/CachyOS używamy grupy 'openrazer' (nie 'plugdev' jak na Ubuntu/Mint)
sudo gpasswd -a $USER openrazer

# Włącz demon openrazer (uruchamia się po ponownym zalogowaniu)
systemctl --user enable openrazer-daemon

echo "WAŻNE: Wyloguj się i zaloguj ponownie aby zmiany grupy 'openrazer' weszły w życie!"


# ============================================================
# 14. KIEROWNICA - LOGITECH
# ============================================================
paru -S --noconfirm oversteer

# Reguły udev dla kół Logitech (G29, G920, G923 itp.)
sudo pacman -S --noconfirm linuxconsole

# Dodaj użytkownika do grupy input (wymagane dla kierownicy)
sudo usermod -aG input $USER


# ============================================================
# 15. KEYD - REMAPOWANIE KLAWISZY
# ============================================================
paru -S --noconfirm keyd
sudo systemctl enable --now keyd

# Konfiguracja keyd dla Razer BlackWidow V4 X - M1-M6 = CTRL+SHIFT+1-6
sudo mkdir -p /etc/keyd
sudo bash -c 'cat > /etc/keyd/default.conf << EOF
[ids]
1532:0293

[main]
f13 = C-S-1
f14 = C-S-2
f15 = C-S-3
f16 = C-S-4
f17 = C-S-5
f18 = C-S-6
EOF'
sudo systemctl restart keyd


# ============================================================
# 16. GNOME - ROZSZERZENIA
# ============================================================

# Extension Manager (do zarządzania rozszerzeniami przez GUI)
flatpak install -y flathub com.mattjakeman.ExtensionManager

# gext - narzędzie do instalacji rozszerzeń z linii komend
paru -S --noconfirm gnome-extensions-cli

# Instalacja wszystkich rozszerzeń przez UUID
EXTS=(
  "user-theme@gnome-shell-extensions.gcampax.github.com"
  "auto-move-windows@gnome-shell-extensions.gcampax.github.com"
  "show-desktop-button@amivaleo"
  "ding@rastersoft.com"
  "burn-my-windows@schneegans.github.com"
  "lockkeys@vaina.lt"
  "freon@UshakovVasilii_Github.yahoo.com"
  "trayIconsReloaded@selfmade.pl"
  "ddterm@amezin.github.com"
  "vertical-workspaces@G-dH.github.com"
  "EasyScreenCast@iacopodeenosee.gmail.com"
  "fq@megh"
  "gnome-ui-tune@itstime.tech"
  "advanced-weather@sanjai.com"
  "reboottouefi@ubaygd.com"
  "ShutdownTimer@deminder"
  "gamemodeshellextension@trsnaqe.com"
  "compiz-windows-effect@hermes83.github.com"
  "system-rpg@conan513"
  "blur-my-shell@aunetx"
  "weatheroclock@CleoMenezesJr.github.io"
  "dash-to-dock@micxgx.gmail.com"
  "dash-to-panel@jderose9.github.com"
)

for EXT in "${EXTS[@]}"; do
  echo "Instalowanie: $EXT"
  gext install "$EXT" 2>/dev/null || echo "Pominięto: $EXT"
done

# Włączenie rozszerzeń (tych które były aktywne)
ACTIVE_EXTS=(
  "user-theme@gnome-shell-extensions.gcampax.github.com"
  "auto-move-windows@gnome-shell-extensions.gcampax.github.com"
  "show-desktop-button@amivaleo"
  "ding@rastersoft.com"
  "burn-my-windows@schneegans.github.com"
  "lockkeys@vaina.lt"
  "freon@UshakovVasilii_Github.yahoo.com"
  "trayIconsReloaded@selfmade.pl"
  "ddterm@amezin.github.com"
  "vertical-workspaces@G-dH.github.com"
  "EasyScreenCast@iacopodeenosee.gmail.com"
  "fq@megh"
  "gnome-ui-tune@itstime.tech"
  "advanced-weather@sanjai.com"
  "reboottouefi@ubaygd.com"
  "ShutdownTimer@deminder"
  "gamemodeshellextension@trsnaqe.com"
  "compiz-windows-effect@hermes83.github.com"
  "system-rpg@conan513"
)

for EXT in "${ACTIVE_EXTS[@]}"; do
  gnome-extensions enable "$EXT" 2>/dev/null
done


# ============================================================
# GOTOWE
# ============================================================
echo ""
echo "============================================"
echo "  Instalacja zakończona!"
echo "  Uruchom ponownie komputer: sudo reboot"
echo "============================================"
echo ""
echo "Po restarcie:"
echo "  - Ustaw launch options w Steam: gamemoderun mangohud %command%"
echo "  - Otwórz ProtonUp-Qt i pobierz GE-Proton"
echo "  - Otwórz Extension Manager i skonfiguruj Dash to Dock"
echo "  - Otwórz Polychromatic aby skonfigurować Razer"
echo "  - Otwórz Oversteer aby skonfigurować kierownicę Logitech"
