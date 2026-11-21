#!/bin/bash
set -euo pipefail
src=$(cd "$(dirname "$0")" && pwd)
for dep in gst-play-1.0 ffmpeg desktop-file-validate xfce4-terminal; do
  command -v "$dep" >/dev/null || { echo "Dependência ausente: $dep" >&2; exit 1; }
done
desktop_file="$(xdg-user-dir DESKTOP)/SmartTube Educabox.desktop"
app="$HOME/.local/share/smarttube-educabox"
install -d "$app" "$HOME/.local/bin" "$HOME/.local/share/applications" "$(dirname "$desktop_file")"
install -m755 "$src/smarttube-educabox.py" "$app/"
install -m644 "$src/../common/src/main/res/values-pt-rBR/strings.xml" "$app/smarttube-strings.xml"
install -m755 "$src/educabox-midia" "$src/educabox-yt-formatos" "$HOME/.local/bin/"
cat > "$app/SmartTube-Educabox.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=SmartTube Educabox
Comment=Pesquisar e reproduzir vídeos na TV
Icon=applications-multimedia
Exec="$app/smarttube-educabox.py"
Terminal=false
Categories=AudioVideo;Player;
DESKTOP
desktop-file-validate "$app/SmartTube-Educabox.desktop"
install -m755 "$app/SmartTube-Educabox.desktop" "$desktop_file"
install -m644 "$app/SmartTube-Educabox.desktop" "$HOME/.local/share/applications/"
