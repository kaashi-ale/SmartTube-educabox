#!/usr/bin/python3
import os
import json
import xml.etree.ElementTree as ET
import subprocess
import threading
import re
import sqlite3
from urllib.request import urlopen
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

state.parent.mkdir(parents=True, exist_ok=True)
channels = sqlite3.connect(str(state.with_name('subscriptions.sqlite')))
channels.execute('CREATE TABLE IF NOT EXISTS subscriptions (id TEXT PRIMARY KEY, name TEXT NOT NULL)')
video_channels = {}

def channel_menu(widget, url):
    channel = video_channels.get(url)
    if not channel:
        status.set_text('Informação de canal indisponível para este vídeo.')
        return True
    cid, name = channel
    exists = channels.execute('SELECT 1 FROM subscriptions WHERE id=?', (cid,)).fetchone()
    menu = Gtk.Menu()
    action = Gtk.MenuItem(label=('Cancelar inscrição · ' if exists else 'Inscrever-se · ') + name)
    def change(item):
        with channels:
            if exists:
                channels.execute('DELETE FROM subscriptions WHERE id=?', (cid,))
            else:
                channels.execute('INSERT OR IGNORE INTO subscriptions VALUES (?,?)', (cid, name))
        status.set_text(('Inscrição removida · ' if exists else 'Inscrição salva · ') + name)
    action.connect('activate', change)
    menu.append(action)
    menu.show_all()
    menu.attach_to_widget(widget, None)
    menu.popup_at_widget(widget, Gdk.Gravity.SOUTH_WEST, Gdk.Gravity.NORTH_WEST, None)
    return True

def subscription_feed(records):
    rows = []
    authors = {}
    errors = 0
    for cid, name in records:
        try:
            with urlopen('https://www.youtube.com/feeds/videos.xml?channel_id=' + cid, timeout=6) as response:
                feed = ET.fromstring(response.read(512 * 1024))
            for item in feed.findall('{http://www.w3.org/2005/Atom}entry'):
                vid = item.findtext('{http://www.youtube.com/xml/schemas/2015}videoId', '')
                if re.fullmatch(r'[A-Za-z0-9_-]{11}', vid):
                    link = 'https://www.youtube.com/watch?v=' + vid
                    rows.append((item.findtext('{http://www.w3.org/2005/Atom}published', ''),
                                 item.findtext('{http://www.w3.org/2005/Atom}title', vid), link))
                    authors[link] = (cid, name)
        except (OSError, ET.ParseError):
            errors += 1
    items = [(title, '', link) for _, title, link in sorted(rows, reverse=True)[:12]]
    GLib.idle_add(populate, items, 'Inscrições locais · {} vídeos · {} canais indisponíveis'.format(len(items), errors), authors)

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
sponsors = Gtk.CheckButton(label='SponsorBlock')
sponsors.set_tooltip_text('Consultar SponsorBlock para pular trechos patrocinados')
toolbar.pack_start(sponsors, False, False, 0)
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
    lib = Path.home()/'.local/opt/rk-media/usr/lib/arm-linux-gnueabihf'
    env = dict(os.environ, EDUCABOX_VIDEO_HEIGHT=quality.get_active_id(),
               EDUCABOX_SPONSORBLOCK='1' if sponsors.get_active() else '0',
               LD_LIBRARY_PATH=str(lib), GST_PLUGIN_PATH=str(lib/'gstreamer-1.0'))
    playback = subprocess.Popen(['/usr/bin/python3', str(Path(__file__).with_name('player.py')), url], env=env)

def populate(rows, message, authors=None):
    video_channels.clear()
    video_channels.update(authors or {})
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
    authors = {}
    try:
        raw = subprocess.check_output(
            [str(executable), '--ignore-config', '--flat-playlist', '--no-warnings',
             '--print', '%(id)s\t%(channel_id)s\t%(channel)s\t%(duration_string)s\t%(title)s',
             '--', 'ytsearch12:' + query], env=env, timeout=85,
            stderr=subprocess.DEVNULL, universal_newlines=True)
        for line in raw.splitlines():
            parts = line.split('\t', 4)
            if len(parts) == 5 and re.fullmatch(r'[A-Za-z0-9_-]{11}', parts[0]):
                vid, cid, name, duration, title = parts
                link = 'https://www.youtube.com/watch?v=' + vid
                rows.append((title, duration if duration != 'NA' else '', link))
                if re.fullmatch(r'UC[A-Za-z0-9_-]{22}', cid):
                    authors[link] = (cid, name)
        message = '{} vídeos • Enter para reproduzir'.format(len(rows))
    except (OSError, subprocess.SubprocessError):
        message = 'A busca falhou. Tente novamente ou cole o link do vídeo.'
    GLib.idle_add(populate, rows, message, authors)

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
    if name == 'SUBSCRIPTIONS':
        records = channels.execute('SELECT id, name FROM subscriptions ORDER BY name').fetchall()
        if records:
            for item in (entry, search_button, history_button, browse.widget):
                item.set_sensitive(False)
            status.set_text('Carregando inscrições…')
            threading.Thread(target=subscription_feed, args=(records,), daemon=True).start()
        else:
            populate([], 'Use o botão direito ou Shift+F10 em um resultado para seguir o canal.')
    elif name in QUERIES:
        entry.set_text(QUERIES[name])
        submit(entry)
    else:
        populate(history, label('header_history') if history else
                 'Pesquise ou cole um link para começar.')

browse = Browse(label, play, section_selected, channel_menu)
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
