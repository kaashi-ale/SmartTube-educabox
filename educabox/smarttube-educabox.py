#!/usr/bin/python3
import os
import json
import xml.etree.ElementTree as ET
import subprocess
import threading
from pathlib import Path
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gdk, Gtk, GLib
from browse import Browse, QUERIES

bin_dir = Path.home() / '.local/bin'
strings = ET.parse(Path(__file__).with_name('smarttube-strings.xml'))
def label(name):
    return strings.find("./string[@name='{}']".format(name)).text

state = Path(GLib.get_user_data_dir()) / 'smarttube-educabox/history.json'
try:
    stored = json.loads(state.read_text())
    history = [item for item in stored if isinstance(item, list) and len(item) == 3
               and all(isinstance(value, str) for value in item)] if isinstance(stored, list) else []
except (OSError, ValueError):
    history = []

window = Gtk.Window(title='SmartTube • Educabox')
window.set_default_size(720, 460)
window.connect('destroy', Gtk.main_quit)
layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
layout.set_border_width(28)
css = Gtk.CssProvider()
css.load_from_data(b'window {background:#101722;color:#f4f7ff;} entry,treeview,button,combobox {font-size:22px;} entry,button {padding:8px;} label {font-size:18px;}')
Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
window.add(layout)
entry = Gtk.SearchEntry()
entry.set_placeholder_text('Pesquise um vídeo ou cole um link')
toolbar = Gtk.Box(spacing=12)
layout.pack_start(toolbar, False, False, 0)
toolbar.pack_start(entry, True, True, 0)
search_button = Gtk.Button(label=label('title_search'))
toolbar.pack_start(search_button, False, False, 0)
history_button = Gtk.Button(label=label('header_history'))
toolbar.pack_start(history_button, False, False, 0)
quality = Gtk.ComboBoxText()
for height in ('720', '360'):
    quality.append(height, height + 'p')
quality.set_active_id('720')
quality.set_tooltip_text(label('playback_settings'))
toolbar.pack_start(quality, False, False, 0)
status = Gtk.Label(label='Enter para buscar ou abrir o link')
status.set_xalign(0)
layout.pack_start(status, False, False, 0)
playback = None

def play(url, title=None):
    global playback
    if playback is not None and playback.poll() is None:
        status.set_text('Feche o vídeo atual antes de abrir outro.')
        return
    row = [title or url, '', url]
    history[:] = [row] + [item for item in history if item[2] != url][:49]
    try:
        state.parent.mkdir(parents=True, exist_ok=True)
        temporary = state.with_suffix('.tmp')
        temporary.write_text(json.dumps(history, ensure_ascii=False))
        temporary.replace(state)
    except OSError:
        status.set_text('O histórico não pôde ser salvo.')
    env = dict(os.environ, EDUCABOX_VIDEO_HEIGHT=quality.get_active_id())

    playback = subprocess.Popen(['xfce4-terminal', '--disable-server', '--title=YouTube', '--execute',
                      str(bin_dir / 'educabox-midia'), url], env=env)

def populate(rows, message):
    status.set_text(message)
    entry.set_sensitive(True)
    search_button.set_sensitive(True)
    history_button.set_sensitive(True)
    browse.widget.set_sensitive(True)
    browse.show(rows)
    if not rows:
        entry.grab_focus()

def search(query):
    root = Path.home() / '.nvm/versions/node/v20.20.2/compat'
    lib = root / 'lib/arm-linux-gnueabihf'
    env = dict(os.environ, LD_LIBRARY_PATH=str(lib) + ':' +
               str(root / 'usr/lib/arm-linux-gnueabihf'))
    executable = Path.home() / '.local/opt/edu-yt-dlp/yt-dlp_linux_armv7l'
    rows = []
    try:
        raw = subprocess.check_output(
            [str(executable), '--ignore-config', '--flat-playlist', '--no-warnings',
             '--print', '%(id)s\t%(title)s\t%(duration_string)s',
             '--', 'ytsearch12:' + query], env=env, timeout=85,
            stderr=subprocess.DEVNULL, universal_newlines=True)
        for line in raw.splitlines():
            parts = line.split('\t', 2)
            if len(parts) == 3 and len(parts[0]) == 11:
                video_id, title, duration = parts
                rows.append((title, duration if duration != 'NA' else '',
                             'https://www.youtube.com/watch?v=' + video_id))
        message = '{} vídeos • Enter para reproduzir'.format(len(rows))
    except (OSError, subprocess.SubprocessError):
        message = 'A busca falhou. Tente novamente ou cole o link do vídeo.'
    GLib.idle_add(populate, rows, message)

def submit(field):
    query = field.get_text().strip()
    if query.startswith('https://'):
        play(query)
    elif query:
        browse.show([])
        browse.widget.set_sensitive(False)
        entry.set_sensitive(False)
        search_button.set_sensitive(False)
        history_button.set_sensitive(False)
        status.set_text('Buscando no YouTube…')
        threading.Thread(target=search, args=(query,), daemon=True).start()

def focus_search(widget, event):
    if event.keyval == Gdk.KEY_F11:
        if window.get_window().get_state() & Gdk.WindowState.FULLSCREEN:
            window.unfullscreen()
        else:
            window.fullscreen()
        return True
    if event.keyval in (Gdk.KEY_Escape, Gdk.KEY_BackSpace) and not entry.has_focus():
        entry.grab_focus()
        return True
    if event.keyval == Gdk.KEY_l and event.state & Gdk.ModifierType.CONTROL_MASK:
        entry.grab_focus()
        entry.select_region(0, -1)
        return True
    return False

window.connect("key-press-event", focus_search)

def section_selected(name):
    browse.set_section(name)
    if name in QUERIES:
        entry.set_text(QUERIES[name])
        submit(entry)
    else:
        populate(history, label('header_history') if history else
                 'Pesquise ou cole um link para começar.')

browse = Browse(label, play, section_selected)
layout.pack_start(browse.widget, True, True, 0)
history_button.connect('clicked', lambda button: section_selected('HISTORY'))
search_button.connect('clicked', lambda button: submit(entry))
entry.connect('activate', submit)
window.show_all()
if os.getenv("SMARTTUBE_WINDOWED") != "1":
    window.fullscreen()
section_selected('HOME')
entry.grab_focus()
Gtk.main()
