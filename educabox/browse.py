"""GTK implementation of the SmartTube browse sections and video cards."""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import urlopen

from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango

ROOT = Path(__file__).parent
SECTIONS = json.loads((ROOT / 'sections.json').read_text())
QUERIES = {
    'TRENDING': 'vídeos populares Brasil',
    'MUSIC': 'música Brasil lançamentos',
    'GAMING': 'jogos gameplay Brasil',
    'SPORTS': 'esportes melhores momentos Brasil',
}


class Browse:
    def __init__(self, label, play, select_section):
        self.play = play
        self.pool = ThreadPoolExecutor(max_workers=3)
        self.cards = []
        self.widget = Gtk.Box(spacing=24)
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.widget.pack_start(sidebar, False, False, 0)
        self.navigation = []
        for key, section in SECTIONS.items():
            caption = label(section['title'])
            if key in QUERIES:
                caption = 'Buscar · ' + caption
            button = Gtk.Button(label=caption)
            icon = ROOT / 'icons' / (section['icon'] + '.png')
            if icon.is_file():
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(icon), 24, 24, True)
                button.set_image(Gtk.Image.new_from_pixbuf(pixbuf))
                button.set_always_show_image(True)
            button.connect('clicked', lambda _button, name=key: select_section(name))
            sidebar.pack_start(button, False, False, 0)
            self.navigation.append(button)
        self.grid = Gtk.FlowBox()
        self.grid.set_selection_mode(Gtk.SelectionMode.NONE)
        self.grid.set_min_children_per_line(1)
        self.grid.set_max_children_per_line(5)
        self.grid.set_row_spacing(12)
        self.grid.set_column_spacing(12)
        self.grid.set_valign(Gtk.Align.START)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.add(self.grid)
        self.widget.pack_start(scroller, True, True, 0)

    def set_section(self, name):
        # Android ROW sections are shelves. GRID sections fill the available columns.
        self.grid.set_max_children_per_line(4 if SECTIONS[name]['layout'] == 'ROW' else 5)

    def show(self, rows, focus=True):
        for card in self.cards:
            card.get_parent().destroy()
        self.cards.clear()
        for title, duration, url in rows[:12]:
            card = Gtk.Button()
            card.set_size_request(232, 161)
            content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            image = Gtk.Image.new_from_icon_name('video-x-generic', Gtk.IconSize.DIALOG)
            image.set_size_request(216, 121)
            content.pack_start(image, False, False, 0)
            caption = Gtk.Label(label=title + ('  ·  ' + duration if duration else ''))
            caption.set_xalign(0)
            caption.set_ellipsize(Pango.EllipsizeMode.END)
            caption.set_max_width_chars(20)
            content.pack_start(caption, False, False, 0)
            card.add(content)
            card.set_tooltip_text(title)
            card.connect('clicked', lambda _button, link=url, name=title: self.play(link, name))
            card.connect('key-press-event', self.navigate_card)
            self.grid.add(card)
            self.cards.append(card)
            match = re.fullmatch(r'https://www\.youtube\.com/watch\?v=([\w-]{11})', url, re.ASCII)
            if match:
                self.pool.submit(self.thumbnail, image, match.group(1))
        self.grid.show_all()
        if self.cards and focus:
            self.cards[0].grab_focus()

    def navigate_card(self, card, event):
        if event.keyval in (Gdk.KEY_Escape, Gdk.KEY_BackSpace):
            self.navigation[0].grab_focus()
            return True
        if event.keyval in (Gdk.KEY_Left, Gdk.KEY_Right):
            direction = -1 if event.keyval == Gdk.KEY_Left else 1
            index = self.cards.index(card) + direction
            if 0 <= index < len(self.cards):
                self.cards[index].grab_focus()
            elif direction < 0:
                self.navigation[0].grab_focus()
            return True
        return False

    @staticmethod
    def thumbnail(image, video_id):
        try:
            with urlopen('https://i.ytimg.com/vi/{}/mqdefault.jpg'.format(video_id), timeout=6) as response:
                payload = response.read(128 * 1024)
            GLib.idle_add(Browse.draw_thumbnail, image, payload)
        except OSError:
            pass

    @staticmethod
    def draw_thumbnail(image, payload):
        if image.get_parent() is not None:
            loader = GdkPixbuf.PixbufLoader.new_with_type('jpeg')
            loader.set_size(216, 121)
            try:
                loader.write(payload)
                loader.close()
                image.set_from_pixbuf(loader.get_pixbuf())
            except GLib.Error:
                pass
        return False
