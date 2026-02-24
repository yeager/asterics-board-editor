"""Preview mode for AAC boards with TTS."""

import gi
import subprocess
import threading
import gettext

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, Gdk, GdkPixbuf, GLib

from asterics_board_editor.model import CellAction
from asterics_board_editor.pictogram import download_pictogram

_ = gettext.gettext


class PreviewWindow(Adw.Window):
    """Full-screen preview of a board with TTS playback."""

    def __init__(self, project, **kwargs):
        super().__init__(**kwargs)
        self.project = project
        self.board_stack = []  # for back navigation
        self.set_title(_("Preview"))
        self.set_default_size(1024, 768)

        self._build_ui()
        if project.home_board:
            self._show_board(project.home_board)

    def _build_ui(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(box)

        header = Adw.HeaderBar()
        box.append(header)

        self.back_btn = Gtk.Button(icon_name="go-previous-symbolic", tooltip_text=_("Back"))
        self.back_btn.connect("clicked", self._on_back)
        self.back_btn.set_sensitive(False)
        header.pack_start(self.back_btn)

        self.title_widget = Adw.WindowTitle(title=_("Preview"), subtitle="")
        header.set_title_widget(self.title_widget)

        # Output bar (shows accumulated spoken text)
        self.output_label = Gtk.Label(label="", wrap=True, xalign=0)
        self.output_label.set_margin_start(16)
        self.output_label.set_margin_end(16)
        self.output_label.set_margin_top(8)
        self.output_label.set_margin_bottom(8)
        self.output_label.add_css_class("title-2")
        box.append(self.output_label)

        # Clear button
        output_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        output_bar.set_margin_start(16)
        output_bar.set_margin_end(16)
        output_bar.set_margin_bottom(8)
        clear_btn = Gtk.Button(label=_("Clear"), halign=Gtk.Align.START)
        clear_btn.connect("clicked", lambda b: self.output_label.set_text(""))
        output_bar.append(clear_btn)

        speak_all_btn = Gtk.Button(label=_("Speak All"), halign=Gtk.Align.START)
        speak_all_btn.add_css_class("suggested-action")
        speak_all_btn.connect("clicked", self._on_speak_all)
        output_bar.append(speak_all_btn)
        box.append(output_bar)

        # Grid
        scroll = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        self.grid = Gtk.Grid()
        self.grid.set_row_spacing(6)
        self.grid.set_column_spacing(6)
        self.grid.set_margin_start(12)
        self.grid.set_margin_end(12)
        self.grid.set_margin_top(12)
        self.grid.set_margin_bottom(12)
        self.grid.set_row_homogeneous(True)
        self.grid.set_column_homogeneous(True)
        scroll.set_child(self.grid)
        box.append(scroll)

        self.spoken_text = []

    def _show_board(self, board):
        self.current_board = board
        self.title_widget.set_subtitle(board.name)
        self.back_btn.set_sensitive(len(self.board_stack) > 0)

        # Clear grid
        child = self.grid.get_first_child()
        while child:
            next_c = child.get_next_sibling()
            self.grid.remove(child)
            child = next_c

        board.ensure_cells()
        for row in range(board.rows):
            for col in range(board.columns):
                cell = board.get_cell(row, col)
                widget = self._create_preview_cell(cell)
                self.grid.attach(widget, col, row, 1, 1)

    def _create_preview_cell(self, cell):
        btn = Gtk.Button()
        btn.set_hexpand(True)
        btn.set_vexpand(True)
        btn.set_size_request(120, 120)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)

        if cell:
            if cell.bg_color and cell.bg_color != "#FFFFFF":
                css = Gtk.CssProvider()
                css.load_from_string(f"button {{ background-color: {cell.bg_color}; }}")
                btn.get_style_context().add_provider(css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

            if cell.image_url:
                img = Gtk.Image()
                img.set_pixel_size(80)
                self._load_image(img, cell.image_url)
                box.append(img)

            if cell.label:
                label = Gtk.Label(label=cell.label)
                label.add_css_class("title-3")
                label.set_wrap(True)
                label.set_max_width_chars(15)
                box.append(label)

            if cell.action.action_type == CellAction.NAVIGATE:
                nav_icon = Gtk.Image(icon_name="go-next-symbolic")
                nav_icon.set_pixel_size(16)
                box.append(nav_icon)

            btn.connect("clicked", self._on_cell_activated, cell)
        else:
            btn.set_sensitive(False)

        btn.set_child(box)
        return btn

    def _load_image(self, image_widget, url):
        def load():
            path = download_pictogram(url)
            if path:
                GLib.idle_add(_set, path)

        def _set(path):
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 80, 80, True)
                texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                image_widget.set_from_paintable(texture)
            except:
                pass
            return False

        threading.Thread(target=load, daemon=True).start()

    def _on_cell_activated(self, btn, cell):
        if cell.action.action_type == CellAction.SPEAK:
            text = cell.action.value or cell.label
            if text:
                self.spoken_text.append(text)
                self.output_label.set_text(" ".join(self.spoken_text))
                self._speak(text)
        elif cell.action.action_type == CellAction.NAVIGATE:
            target = self.project.get_board_by_id(cell.action.value)
            if target:
                self.board_stack.append(self.current_board)
                self._show_board(target)

    def _on_back(self, btn):
        if self.board_stack:
            board = self.board_stack.pop()
            self._show_board(board)

    def _on_speak_all(self, btn):
        text = " ".join(self.spoken_text)
        if text:
            self._speak(text)

    def _speak(self, text):
        """Use system TTS to speak text."""
        def do_speak():
            try:
                # Try espeak-ng first, then espeak, then macOS say
                for cmd in [["espeak-ng", text], ["espeak", text], ["say", text]]:
                    try:
                        subprocess.run(cmd, timeout=10)
                        return
                    except FileNotFoundError:
                        continue
            except Exception as e:
                print(f"TTS error: {e}")

        threading.Thread(target=do_speak, daemon=True).start()
