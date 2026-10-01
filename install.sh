#!/usr/bin/env bash
# Settler — instalacja na świeży CachyOS / Arch.
#
# Z katalogu repozytorium:
#   ./install.sh
#
# Jedna komenda, gdy ten plik jest na GitHubie:
#   curl -fsSL https://raw.githubusercontent.com/GorianWaco/Settler/main/install.sh | bash
#
# Skrypt kładzie program w menu. Listy programów nie instaluje sam —
# po uruchomieniu Settlera kliknij „Zainstaluj narzędzia”, potem zaznacz programy.

set -euo pipefail

REPO_URL="https://github.com/GorianWaco/Settler.git"
DEST="${HOME}/Projekty/Settler"
BIN_DIR="${HOME}/.local/bin"
APP_DIR="${HOME}/.local/share/applications"

info() { printf '==> %s\n' "$*"; }
die() { printf 'Błąd: %s\n' "$*" >&2; exit 1; }

as_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  elif command -v pkexec >/dev/null 2>&1; then
    pkexec "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    die "Potrzebuję pkexec albo sudo, żeby doinstalować Pythona, GTK i git."
  fi
}

info "Zależności Settlera (Python, GTK 4, libadwaita, git)"
as_root pacman -S --needed --noconfirm python python-gobject gtk4 libadwaita git

ROOT=""
if [[ -n "${BASH_SOURCE[0]:-}" && -f "${BASH_SOURCE[0]}" ]]; then
  SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  if [[ -f "${SRC}/Settler/settler.py" ]]; then
    ROOT="$SRC"
  fi
fi

if [[ -z "$ROOT" ]]; then
  info "Pobieram Settler do ${DEST}"
  mkdir -p "${HOME}/Projekty"
  if [[ -d "${DEST}/.git" ]]; then
    git -C "$DEST" pull --ff-only || info "Zostawiam lokalną kopię."
  elif [[ ! -f "${DEST}/Settler/settler.py" ]]; then
    git clone "$REPO_URL" "$DEST"
  fi
  ROOT="$DEST"
fi

[[ -f "${ROOT}/Settler/settler.py" ]] || die "Nie widzę Settler/settler.py w ${ROOT}"

mkdir -p "$BIN_DIR" "$APP_DIR"
cat > "${BIN_DIR}/settler" << EOF
#!/usr/bin/env bash
exec python3 "${ROOT}/Settler/settler.py" "\$@"
EOF
chmod +x "${BIN_DIR}/settler"

cat > "${APP_DIR}/settler.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Settler
Name[pl]=Settler
GenericName[pl]=Konfiguracja po instalacji CachyOS
Comment[pl]=GUI konfiguracji CachyOS po świeżej instalacji
Exec=${BIN_DIR}/settler
Icon=system-software-install
Terminal=false
Categories=Settings;System;
Keywords=cachyos;setup;post-install;gnome;
StartupNotify=true
EOF

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
fi

info "Settler jest w menu. Polecenie: ${BIN_DIR}/settler"
if [[ ":${PATH}:" != *":${BIN_DIR}:"* ]]; then
  info "Po zalogowaniu się ponownie polecenie settler będzie w PATH."
fi
info "Otwórz Settler, kliknij „Zainstaluj narzędzia”, potem zaznacz programy."
