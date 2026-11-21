#!/usr/bin/python3
"""Educabox playback adapter. All decoding and presentation use GStreamer."""
import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import urlopen

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('Gst', '1.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import Gdk, GdkX11, GLib, Gst, GstVideo, Gtk

Gst.init(None)


class Player:
    def __init__(self, source):
        self.source = source
        self.closed = False
        self.failed = False
        self.paused = False
        self.segments = []
        self.last_skip = None
        self.pipeline = None
        self.extractor = None
        self.window = Gtk.Window(title='Reprodutor SmartTube')
        self.window.set_default_size(960, 540)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.window.add(box)
        self.screen = Gtk.DrawingArea()
        box.pack_start(self.screen, True, True, 0)
        controls = Gtk.Box(spacing=10)
        box.pack_start(controls, False, False, 0)
        for title, callback in [('Voltar', self.window.close), ('−10 s', lambda: self.seek(-10)),
                                ('Pausar / continuar', self.toggle), ('+10 s', lambda: self.seek(10))]:
            button = Gtk.Button(label=title)
            button.connect('clicked', lambda _, fn=callback: fn())
            controls.pack_start(button, False, False, 0)
        self.status = Gtk.Label(label='Abrindo vídeo…')
        controls.pack_start(self.status, True, True, 0)
        self.browser = Gtk.Button(label='Abrir no YouTube')
        self.browser.connect('clicked', lambda _: Gtk.show_uri_on_window(self.window, source, Gdk.CURRENT_TIME))
        controls.pack_end(self.browser, False, False, 0)
        self.window.connect('delete-event', self.stop_before_destroy)
        self.window.connect('destroy', self.close)
        self.window.connect('key-press-event', self.key)
        self.window.fullscreen()
        self.window.show_all()
        self.browser.hide()
        self.xid = self.screen.get_window().get_xid()
        threading.Thread(target=self.resolve, daemon=True).start()

    def resolve(self):
        if self.closed:
            return
        if self.source.startswith('https://'):
            self.extractor = subprocess.Popen([str(Path.home()/'.local/bin/educabox-yt-formatos'), self.source],
                                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            if self.closed:
                self.extractor.terminate()
            try:
                output, error = self.extractor.communicate(timeout=100)
            except subprocess.TimeoutExpired:
                self.extractor.kill()
                self.extractor.communicate()
                GLib.idle_add(self.fail, 'Tempo esgotado ao abrir o vídeo.')
                return
            if self.extractor.returncode:
                message = 'O YouTube solicitou login.' if re.search('sign in|not a bot', error, re.I) else 'Vídeo indisponível nesta qualidade.'
                GLib.idle_add(self.fail, message)
                return
            urls = output.splitlines()
        else:
            urls = [Path(self.source).resolve().as_uri()]
        GLib.idle_add(self.start, urls)

    def start(self, urls):
        if self.closed:
            return False
        try:
            if len(urls) not in (1, 2):
                raise ValueError('Nenhum fluxo de vídeo disponível.')
            self.sink = Gst.ElementFactory.make('rkximagesink')
            if self.sink is None:
                raise ValueError('Saída de vídeo Rockchip indisponível.')
            GstVideo.VideoOverlay.set_window_handle(self.sink, self.xid)
            if len(urls) == 1:
                self.pipeline = Gst.ElementFactory.make('playbin')
                self.pipeline.set_property('uri', urls[0])
                self.pipeline.set_property('video-sink', self.sink)
            else:
                self.pipeline = Gst.parse_launch(
                    'uridecodebin name=video video. ! video/x-raw ! queue ! rkximagesink name=screen '
                    'uridecodebin name=audio audio. ! audio/x-raw ! queue ! audioconvert ! audioresample ! autoaudiosink')
                self.pipeline.get_by_name('video').set_property('uri', urls[0])
                self.pipeline.get_by_name('audio').set_property('uri', urls[1])
                self.sink = self.pipeline.get_by_name('screen')
                GstVideo.VideoOverlay.set_window_handle(self.sink, self.xid)
            bus = self.pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect('message', self.message)
            self.pipeline.set_state(Gst.State.PLAYING)
            GLib.timeout_add(500, self.tick)
        except (ValueError, RuntimeError, TypeError, GLib.Error) as error:
            self.fail(str(error))
        return False

    def message(self, bus, message):
        if message.type == Gst.MessageType.EOS:
            self.window.close()
        elif message.type == Gst.MessageType.BUFFERING:
            percent = message.parse_buffering()
            self.status.set_text('Carregando vídeo · {}%'.format(percent))
            self.pipeline.set_state(Gst.State.PAUSED if percent < 100 or self.paused else Gst.State.PLAYING)
        elif message.type == Gst.MessageType.ERROR:
            self.fail(message.parse_error()[0].message)

    def fail(self, message):
        if not self.closed:
            self.failed = True
            self.status.set_text(message)
            if self.pipeline:
                self.pipeline.set_state(Gst.State.NULL)
            if self.source.startswith('https://'):
                self.browser.show()
        return False

    def tick(self):
        if self.closed or self.failed or not self.pipeline:
            return False
        ok, pos = self.pipeline.query_position(Gst.Format.TIME)
        if ok:
            seconds = pos // Gst.SECOND
            self.status.set_text('{:02d}:{:02d}'.format(seconds // 60, seconds % 60))
            for start, end in self.segments:
                if start <= seconds < end and self.last_skip != start:
                    if self.jump(end):
                        self.last_skip = start
        return True

    def jump(self, seconds):
        return self.pipeline.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
                                         int(max(0, seconds) * Gst.SECOND))

    def seek(self, delta):
        if self.pipeline:
            ok, pos = self.pipeline.query_position(Gst.Format.TIME)
            if ok:
                self.jump(pos / Gst.SECOND + delta)

    def toggle(self):
        if self.pipeline and not self.failed:
            self.paused = not self.paused
            self.pipeline.set_state(Gst.State.PAUSED if self.paused else Gst.State.PLAYING)

    def key(self, widget, event):
        actions = {Gdk.KEY_Escape: self.window.close, Gdk.KEY_BackSpace: self.window.close,
                   Gdk.KEY_space: self.toggle, Gdk.KEY_Left: lambda: self.seek(-10),
                   Gdk.KEY_Right: lambda: self.seek(10)}
        if event.keyval in actions:
            actions[event.keyval]()
            return True
        return False

    def stop_before_destroy(self, *_):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline.get_state(3 * Gst.SECOND)
        return False

    def close(self, *_):
        self.closed = True
        if self.extractor and self.extractor.poll() is None:
            self.extractor.terminate()
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
        Gtk.main_quit()

    def fetch_sponsors(self):
        url = urlparse(self.source)
        vid = (parse_qs(url.query).get('v') or [url.path.split('/')[-1]])[0]
        if not re.fullmatch(r'[A-Za-z0-9_-]{11}', vid):
            return
        query = urlencode({'videoID': vid, 'categories': '["sponsor"]'})
        try:
            with urlopen('https://sponsor.ajay.app/api/skipSegments?' + query, timeout=5) as response:
                self.segments = [tuple(row['segment']) for row in json.load(response)
                                 if row.get('actionType') == 'skip' and len(row.get('segment', [])) == 2]
        except (OSError, ValueError, TypeError):
            pass


if __name__ == '__main__':
    player = Player(sys.argv[1])
    if os.environ.get('EDUCABOX_SPONSORBLOCK') == '1':
        threading.Thread(target=player.fetch_sponsors, daemon=True).start()
    Gtk.main()
