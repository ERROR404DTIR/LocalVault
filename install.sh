#!/usr/bin/env bash
# LocalVault installer for Linux (also works on macOS).
#   bash install.sh              install or update
#   bash install.sh --yes        do not ask before installing system packages
#   bash install.sh --uninstall  remove the app (your vault is kept)
#   bash install.sh --purge      with --uninstall: also delete your vault data
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
APP_DIR="$DATA_HOME/localvault-app"
BIN_DIR="$HOME/.local/bin"
DESKTOP_FILE="$DATA_HOME/applications/localvault.desktop"
ICON_FILE="$DATA_HOME/icons/hicolor/scalable/apps/localvault.svg"
ASSUME_YES=0; UNINSTALL=0; PURGE=0

for arg in "$@"; do
  case "$arg" in
    -y|--yes) ASSUME_YES=1 ;;
    --uninstall) UNINSTALL=1 ;;
    --purge) PURGE=1 ;;
    -h|--help) sed -n '2,6p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

say()  { printf '\033[1;33m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m[ok]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

if [ "$UNINSTALL" = 1 ]; then
  rm -rf "$APP_DIR" "$BIN_DIR/localvault" "$DESKTOP_FILE" "$ICON_FILE"
  ok "LocalVault removed."
  if [ "$PURGE" = 1 ]; then
    rm -rf "$DATA_HOME/localvault"
    ok "Vault data deleted."
  else
    say "Your vault in $DATA_HOME/localvault was kept. Use --purge to delete it too."
  fi
  exit 0
fi

SUDO=""
if [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1; then SUDO="sudo"; fi

pkg_install() {  # $@ = package names for apt; mapped for other managers by caller
  local cmd="$1"; shift
  say "Need to install system packages: $*"
  if [ "$ASSUME_YES" = 0 ]; then
    read -r -p "Run '$SUDO $cmd $*' now? [Y/n] " reply
    case "${reply:-Y}" in [Nn]*) die "Please install them manually and re-run bash install.sh" ;; esac
  fi
  # shellcheck disable=SC2086
  $SUDO $cmd "$@"
}

find_python() {
  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && \
       "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
      echo "$candidate"; return 0
    fi
  done
  return 1
}

install_system_deps() {  # $1 = what is missing: tk | venv
  local what="$1"
  if command -v apt-get >/dev/null 2>&1; then
    if [ "$what" = tk ]; then pkg_install "apt-get install -y" python3-tk
    else pkg_install "apt-get install -y" python3-venv python3-pip; fi
  elif command -v dnf >/dev/null 2>&1; then
    if [ "$what" = tk ]; then pkg_install "dnf install -y" python3-tkinter; else pkg_install "dnf install -y" python3-pip; fi
  elif command -v pacman >/dev/null 2>&1; then
    if [ "$what" = tk ]; then pkg_install "pacman -S --needed --noconfirm" tk; else pkg_install "pacman -S --needed --noconfirm" python-pip; fi
  elif command -v zypper >/dev/null 2>&1; then
    if [ "$what" = tk ]; then pkg_install "zypper install -y" python3-tk; else pkg_install "zypper install -y" python3-pip; fi
  elif command -v apk >/dev/null 2>&1; then
    if [ "$what" = tk ]; then pkg_install "apk add" py3-tkinter; else pkg_install "apk add" py3-pip; fi
  else
    die "Could not detect your package manager. Install Python 3.9+ with Tk (tkinter) and venv support, then re-run."
  fi
}

PY="$(find_python)" || die "Python 3.9 or newer was not found. Install it from your package manager first."
ok "Python found: $($PY --version)"

if ! "$PY" -c 'import tkinter' 2>/dev/null; then
  install_system_deps tk
  "$PY" -c 'import tkinter' 2>/dev/null || die "tkinter is still not available."
fi
ok "Tk found"

mkdir -p "$APP_DIR" "$BIN_DIR"
if ! "$PY" -m venv "$APP_DIR/venv" 2>/dev/null; then
  rm -rf "$APP_DIR/venv"
  install_system_deps venv
  "$PY" -m venv "$APP_DIR/venv" || die "Could not create a virtual environment."
fi

say "Installing LocalVault and its dependencies (needs internet once)"
"$APP_DIR/venv/bin/python" -m pip install --quiet --upgrade pip
"$APP_DIR/venv/bin/python" -m pip install --quiet --upgrade "$REPO_DIR"
ok "Installed to $APP_DIR"

ln -sf "$APP_DIR/venv/bin/localvault" "$BIN_DIR/localvault"

if [ "$(uname -s)" = "Linux" ]; then
  mkdir -p "$(dirname "$DESKTOP_FILE")" "$(dirname "$ICON_FILE")"
  cp "$REPO_DIR/assets/icon.svg" "$ICON_FILE"
  cat > "$DESKTOP_FILE" <<DESKTOP
[Desktop Entry]
Type=Application
Name=LocalVault
Comment=Offline encrypted password manager
Exec=$APP_DIR/venv/bin/localvault
Icon=localvault
Terminal=false
Categories=Utility;Security;
Keywords=password;vault;security;
DESKTOP
  command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$(dirname "$DESKTOP_FILE")" >/dev/null 2>&1 || true
  ok "LocalVault is in your app menu"
fi

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) say "Add $BIN_DIR to your PATH to run 'localvault' from a terminal." ;;
esac
say "Done. Start it from your app menu or run: localvault"
