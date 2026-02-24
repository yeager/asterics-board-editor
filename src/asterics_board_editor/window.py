"""Main application window."""

import gi
import gettext
import os
import threading

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, Gio, GLib, Gdk, GdkPixbuf

from asterics_board_editor.model import Project, Board, Cell, CellAction
from asterics_board_editor.pictogram import search_pictograms, pictogram_url, download_pictogram
from asterics_board_editor.preview import PreviewWindow

_ = gettext.gettext


class EditorWindow(Adw.ApplicationWindow):
    """Main editor window with sidebar for boards and grid editor."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title(_("AsTeRICS Board Editor"))
        self.set_default_size(1200, 800)

        self.project = Project()
        self.current_board = None
        self.selected_cell_pos = None  # (row, col)

        self._build_ui()
        self._show_welcome()

    def _build_ui(self):
        # Main layout
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(self.main_box)

        # Header bar
        header = Adw.HeaderBar()
        self.main_box.append(header)

        # Title
        self.title_widget = Adw.WindowTitle(
            title=_("AsTeRICS Board Editor"),
            subtitle="",
        )
        header.set_title_widget(self.title_widget)

        # Header buttons
        new_btn = Gtk.Button(icon_name="document-new-symbolic", tooltip_text=_("New Project"))
        new_btn.connect("clicked", self._on_new_project)
        header.pack_start(new_btn)

        open_btn = Gtk.Button(icon_name="document-open-symbolic", tooltip_text=_("Open"))
        open_btn.connect("clicked", self._on_open)
        header.pack_start(open_btn)

        save_btn = Gtk.Button(icon_name="document-save-symbolic", tooltip_text=_("Save"))
        save_btn.connect("clicked", self._on_save)
        header.pack_start(save_btn)

        # Right side buttons
        menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic", tooltip_text=_("Menu"))
        menu = Gio.Menu()
        menu.append(_("Export as .grd"), "win.export-grd")
        menu.append(_("Import .grd"), "win.import-grd")
        menu.append(_("About"), "app.about")
        menu_btn.set_menu_model(menu)
        header.pack_end(menu_btn)

        preview_btn = Gtk.Button(icon_name="media-playback-start-symbolic", tooltip_text=_("Preview"))
        preview_btn.connect("clicked", self._on_preview)
        header.pack_end(preview_btn)

        # Actions
        for name, cb in [("export-grd", self._on_export_grd), ("import-grd", self._on_import_grd)]:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", cb)
            self.add_action(action)

        # Content area: split view with board list + editor
        self.split_view = Adw.NavigationSplitView()
        self.main_box.append(self.split_view)
        self.split_view.set_vexpand(True)

        # Sidebar: board list
        sidebar_page = Adw.NavigationPage(title=_("Boards"))
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar_page.set_child(sidebar_box)

        sidebar_header = Adw.HeaderBar()
        sidebar_header.set_show_title(True)
        add_board_btn = Gtk.Button(icon_name="list-add-symbolic", tooltip_text=_("Add Board"))
        add_board_btn.connect("clicked", self._on_add_board)
        sidebar_header.pack_start(add_board_btn)
        sidebar_box.append(sidebar_header)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        self.board_list = Gtk.ListBox()
        self.board_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.board_list.connect("row-selected", self._on_board_selected)
        self.board_list.add_css_class("navigation-sidebar")
        scroll.set_child(self.board_list)
        sidebar_box.append(scroll)

        self.split_view.set_sidebar(sidebar_page)

        # Content: grid editor
        content_page = Adw.NavigationPage(title=_("Editor"))
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_page.set_child(self.content_box)

        # Placeholder content header
        content_header = Adw.HeaderBar()
        content_header.set_show_title(True)
        self.content_box.append(content_header)

        # Board properties bar
        props_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        props_box.set_margin_start(8)
        props_box.set_margin_end(8)
        props_box.set_margin_top(4)
        props_box.set_margin_bottom(4)

        props_box.append(Gtk.Label(label=_("Name:")))
        self.board_name_entry = Gtk.Entry(hexpand=True)
        self.board_name_entry.connect("changed", self._on_board_name_changed)
        props_box.append(self.board_name_entry)

        props_box.append(Gtk.Label(label=_("Rows:")))
        self.rows_spin = Gtk.SpinButton.new_with_range(1, 20, 1)
        self.rows_spin.set_value(3)
        self.rows_spin.connect("value-changed", self._on_grid_size_changed)
        props_box.append(self.rows_spin)

        props_box.append(Gtk.Label(label=_("Columns:")))
        self.cols_spin = Gtk.SpinButton.new_with_range(1, 20, 1)
        self.cols_spin.set_value(4)
        self.cols_spin.connect("value-changed", self._on_grid_size_changed)
        props_box.append(self.cols_spin)

        self.content_box.append(props_box)

        # Grid area
        grid_scroll = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        self.grid_container = Gtk.Grid()
        self.grid_container.set_row_spacing(4)
        self.grid_container.set_column_spacing(4)
        self.grid_container.set_margin_start(8)
        self.grid_container.set_margin_end(8)
        self.grid_container.set_margin_top(8)
        self.grid_container.set_margin_bottom(8)
        self.grid_container.set_row_homogeneous(True)
        self.grid_container.set_column_homogeneous(True)
        grid_scroll.set_child(self.grid_container)
        self.content_box.append(grid_scroll)

        self.split_view.set_content(content_page)

        # Welcome overlay (shown initially)
        self.welcome_overlay = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

    def _show_welcome(self):
        """Show welcome screen."""
        # Clear content and show welcome
        for child in list(self._iter_children(self.content_box)):
            if child != list(self._iter_children(self.content_box))[0]:  # keep header
                pass

        welcome = Adw.StatusPage(
            icon_name="document-edit-symbolic",
            title=_("Welcome to AsTeRICS Board Editor"),
            description=_("Create and edit AAC communication boards"),
            vexpand=True,
        )

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, halign=Gtk.Align.CENTER)
        new_btn = Gtk.Button(label=_("New Project"))
        new_btn.add_css_class("suggested-action")
        new_btn.add_css_class("pill")
        new_btn.connect("clicked", self._on_new_project)
        btn_box.append(new_btn)

        open_btn = Gtk.Button(label=_("Open Project"))
        open_btn.add_css_class("pill")
        open_btn.connect("clicked", self._on_open)
        btn_box.append(open_btn)

        import_btn = Gtk.Button(label=_("Import .grd"))
        import_btn.add_css_class("pill")
        import_btn.connect("clicked", lambda b: self._on_import_grd(None, None))
        btn_box.append(import_btn)

        welcome.set_child(btn_box)

        self.welcome_page = welcome
        self.content_box.append(welcome)
        self._set_editor_visible(False)

    def _set_editor_visible(self, visible):
        """Toggle between welcome and editor."""
        children = list(self._iter_children(self.content_box))
        for i, child in enumerate(children):
            if i == 0:  # header, always visible
                continue
            if child == self.welcome_page if hasattr(self, "welcome_page") else False:
                child.set_visible(not visible)
            else:
                child.set_visible(visible)

    @staticmethod
    def _iter_children(widget):
        child = widget.get_first_child()
        while child:
            yield child
            child = child.get_next_sibling()

    def _on_new_project(self, *args):
        self.project = Project()
        board = Board(name=_("Home"), rows=3, columns=4)
        board.ensure_cells()
        self.project.add_board(board)
        self._refresh_board_list()
        self._select_board(board)

        if hasattr(self, "welcome_page"):
            self.welcome_page.set_visible(False)
        self._set_editor_visible(True)

    def _on_open(self, *args):
        dialog = Gtk.FileDialog()
        f = Gtk.FileFilter()
        f.set_name(_("Board Editor Projects (*.json)"))
        f.add_pattern("*.json")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(f)
        dialog.set_filters(filters)
        dialog.open(self, None, self._on_open_response)

    def _on_open_response(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            path = file.get_path()
            self.project = Project.load_json(path)
            self._refresh_board_list()
            if self.project.home_board:
                self._select_board(self.project.home_board)
            if hasattr(self, "welcome_page"):
                self.welcome_page.set_visible(False)
            self._set_editor_visible(True)
        except Exception as e:
            if "Dismissed" not in str(e):
                self._show_error(_("Failed to open file"), str(e))

    def _on_save(self, *args):
        if not self.project.boards:
            return
        dialog = Gtk.FileDialog()
        dialog.set_initial_name("board.json")
        f = Gtk.FileFilter()
        f.set_name(_("JSON files (*.json)"))
        f.add_pattern("*.json")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(f)
        dialog.set_filters(filters)
        dialog.save(self, None, self._on_save_response)

    def _on_save_response(self, dialog, result):
        try:
            file = dialog.save_finish(result)
            self.project.save_json(file.get_path())
        except Exception as e:
            if "Dismissed" not in str(e):
                self._show_error(_("Failed to save file"), str(e))

    def _on_export_grd(self, *args):
        if not self.project.boards:
            return
        dialog = Gtk.FileDialog()
        dialog.set_initial_name("board.grd")
        dialog.save(self, None, self._on_export_grd_response)

    def _on_export_grd_response(self, dialog, result):
        try:
            file = dialog.save_finish(result)
            self.project.export_grd(file.get_path())
        except Exception as e:
            if "Dismissed" not in str(e):
                self._show_error(_("Failed to export"), str(e))

    def _on_import_grd(self, *args):
        dialog = Gtk.FileDialog()
        f = Gtk.FileFilter()
        f.set_name(_("AsTeRICS Grid files (*.grd)"))
        f.add_pattern("*.grd")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(f)
        dialog.set_filters(filters)
        dialog.open(self, None, self._on_import_grd_response)

    def _on_import_grd_response(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            self.project = Project.import_grd(file.get_path())
            self._refresh_board_list()
            if self.project.home_board:
                self._select_board(self.project.home_board)
            if hasattr(self, "welcome_page"):
                self.welcome_page.set_visible(False)
            self._set_editor_visible(True)
        except Exception as e:
            if "Dismissed" not in str(e):
                self._show_error(_("Failed to import"), str(e))

    def _on_preview(self, *args):
        if not self.project.boards:
            return
        win = PreviewWindow(project=self.project, transient_for=self)
        win.present()

    def _show_error(self, title, message):
        dialog = Adw.AlertDialog(heading=title, body=message)
        dialog.add_response("ok", _("OK"))
        dialog.present(self)

    # Board list management
    def _refresh_board_list(self):
        while True:
            row = self.board_list.get_row_at_index(0)
            if row is None:
                break
            self.board_list.remove(row)

        for board in self.project.boards:
            row = Gtk.ListBoxRow()
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            box.set_margin_start(8)
            box.set_margin_end(8)
            box.set_margin_top(4)
            box.set_margin_bottom(4)

            icon = Gtk.Image(icon_name="view-grid-symbolic")
            box.append(icon)

            label = Gtk.Label(label=board.name or _("Untitled"), xalign=0, hexpand=True)
            box.append(label)

            if board.id == self.project.home_board_id:
                home_icon = Gtk.Image(icon_name="go-home-symbolic")
                box.append(home_icon)

            row.set_child(box)
            row.board_id = board.id
            self.board_list.append(row)

    def _on_board_selected(self, listbox, row):
        if row is None:
            return
        board = self.project.get_board_by_id(row.board_id)
        if board:
            self._select_board(board)

    def _select_board(self, board):
        self.current_board = board
        self._updating = True
        self.board_name_entry.set_text(board.name)
        self.rows_spin.set_value(board.rows)
        self.cols_spin.set_value(board.columns)
        self._updating = False
        self.title_widget.set_subtitle(board.name)
        self._rebuild_grid()

    def _on_add_board(self, *args):
        board = Board(name=_("New Board"), rows=3, columns=4)
        board.ensure_cells()
        self.project.add_board(board)
        self._refresh_board_list()
        self._select_board(board)
        if hasattr(self, "welcome_page"):
            self.welcome_page.set_visible(False)
        self._set_editor_visible(True)

    def _on_board_name_changed(self, entry):
        if hasattr(self, "_updating") and self._updating:
            return
        if self.current_board:
            self.current_board.name = entry.get_text()
            self.title_widget.set_subtitle(entry.get_text())
            self._refresh_board_list()

    def _on_grid_size_changed(self, spin):
        if hasattr(self, "_updating") and self._updating:
            return
        if self.current_board:
            self.current_board.rows = int(self.rows_spin.get_value())
            self.current_board.columns = int(self.cols_spin.get_value())
            self.current_board.ensure_cells()
            self._rebuild_grid()

    # Grid rendering
    def _rebuild_grid(self):
        """Rebuild the grid display."""
        # Clear existing grid
        child = self.grid_container.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.grid_container.remove(child)
            child = next_child

        if not self.current_board:
            return

        board = self.current_board
        board.ensure_cells()

        for row in range(board.rows):
            for col in range(board.columns):
                cell = board.get_cell(row, col)
                cell_widget = self._create_cell_widget(cell, row, col)
                self.grid_container.attach(cell_widget, col, row, 1, 1)

    def _create_cell_widget(self, cell, row, col):
        """Create a widget for a single cell."""
        frame = Gtk.Frame()
        frame.set_hexpand(True)
        frame.set_vexpand(True)
        frame.set_size_request(100, 100)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        box.set_margin_start(4)
        box.set_margin_end(4)
        box.set_margin_top(4)
        box.set_margin_bottom(4)

        if cell:
            # Set background color via CSS
            if cell.bg_color and cell.bg_color != "#FFFFFF":
                css = Gtk.CssProvider()
                css.load_from_string(f"frame {{ background-color: {cell.bg_color}; }}")
                frame.get_style_context().add_provider(css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

            # Image
            if cell.image_url:
                image = Gtk.Image()
                image.set_pixel_size(64)
                image.set_icon_name("image-loading-symbolic")
                box.append(image)
                # Load image asynchronously
                self._load_cell_image(image, cell.image_url)
            else:
                icon = Gtk.Image(icon_name="list-add-symbolic")
                icon.set_pixel_size(32)
                icon.set_opacity(0.3)
                box.append(icon)

            # Label
            label = Gtk.Label(label=cell.label or "")
            label.set_wrap(True)
            label.set_max_width_chars(12)
            label.set_ellipsize(3)  # PANGO_ELLIPSIZE_END
            box.append(label)

            # Action indicator
            if cell.action.action_type == CellAction.NAVIGATE:
                nav_icon = Gtk.Image(icon_name="go-next-symbolic")
                nav_icon.set_pixel_size(16)
                box.append(nav_icon)
        else:
            icon = Gtk.Image(icon_name="list-add-symbolic")
            icon.set_pixel_size(32)
            icon.set_opacity(0.2)
            box.append(icon)

        frame.set_child(box)

        # Click handler
        click = Gtk.GestureClick()
        click.connect("pressed", self._on_cell_clicked, row, col)
        frame.add_controller(click)

        # Drag source
        drag_source = Gtk.DragSource()
        drag_source.set_actions(Gdk.DragAction.MOVE)
        drag_source.connect("prepare", self._on_drag_prepare, row, col)
        frame.add_controller(drag_source)

        # Drop target
        drop_target = Gtk.DropTarget.new(GLib.TYPE_STRING, Gdk.DragAction.MOVE)
        drop_target.connect("drop", self._on_drop, row, col)
        frame.add_controller(drop_target)

        return frame

    def _load_cell_image(self, image_widget, url):
        """Load image from URL asynchronously."""
        def load():
            path = download_pictogram(url)
            if path:
                GLib.idle_add(_set_image, path)

        def _set_image(path):
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 64, 64, True)
                texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                image_widget.set_from_paintable(texture)
            except Exception:
                image_widget.set_from_icon_name("image-missing-symbolic")
            return False

        thread = threading.Thread(target=load, daemon=True)
        thread.start()

    def _on_cell_clicked(self, gesture, n_press, x, y, row, col):
        """Handle cell click - open cell editor."""
        if not self.current_board:
            return
        self.selected_cell_pos = (row, col)
        cell = self.current_board.get_cell(row, col)
        if cell is None:
            cell = Cell()
            self.current_board.set_cell(row, col, cell)
        self._show_cell_editor(cell, row, col)

    def _on_drag_prepare(self, source, x, y, row, col):
        """Prepare drag data."""
        content = Gdk.ContentProvider.new_for_value(f"{row},{col}")
        return content

    def _on_drop(self, target, value, x, y, dest_row, dest_col):
        """Handle drop - swap cells."""
        try:
            src_row, src_col = map(int, value.split(","))
        except:
            return False

        board = self.current_board
        if not board:
            return False

        src_cell = board.get_cell(src_row, src_col)
        dest_cell = board.get_cell(dest_row, dest_col)
        board.set_cell(dest_row, dest_col, src_cell)
        board.set_cell(src_row, src_col, dest_cell)
        self._rebuild_grid()
        return True

    # Cell editor dialog
    def _show_cell_editor(self, cell, row, col):
        """Show dialog to edit cell properties."""
        dialog = Adw.Dialog()
        dialog.set_title(_("Edit Cell"))
        dialog.set_content_width(500)
        dialog.set_content_height(600)

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        # Delete button
        delete_btn = Gtk.Button(icon_name="user-trash-symbolic", tooltip_text=_("Delete Cell"))
        delete_btn.add_css_class("destructive-action")
        header.pack_start(delete_btn)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(16)
        content.set_margin_bottom(16)

        # Label
        group1 = Adw.PreferencesGroup(title=_("Cell Properties"))
        label_row = Adw.EntryRow(title=_("Label"))
        label_row.set_text(cell.label)
        group1.add(label_row)

        # Background color
        color_row = Adw.ActionRow(title=_("Background Color"))
        color_btn = Gtk.ColorDialogButton()
        color_dialog = Gtk.ColorDialog()
        color_btn.set_dialog(color_dialog)
        try:
            rgba = Gdk.RGBA()
            rgba.parse(cell.bg_color)
            color_btn.set_rgba(rgba)
        except:
            pass
        color_btn.set_valign(Gtk.Align.CENTER)
        color_row.add_suffix(color_btn)
        group1.add(color_row)
        content.append(group1)

        # Action
        group2 = Adw.PreferencesGroup(title=_("Action"))
        action_row = Adw.ComboRow(title=_("Type"))
        action_model = Gtk.StringList()
        action_model.append(_("Speak Text"))
        action_model.append(_("Navigate to Board"))
        action_row.set_model(action_model)
        action_row.set_selected(0 if cell.action.action_type == CellAction.SPEAK else 1)
        group2.add(action_row)

        action_value_row = Adw.EntryRow(title=_("Value"))
        action_value_row.set_text(cell.action.value)
        group2.add(action_value_row)

        # Board selector for navigate action
        if self.project.boards:
            board_row = Adw.ComboRow(title=_("Target Board"))
            board_model = Gtk.StringList()
            board_ids = []
            selected_idx = 0
            for i, b in enumerate(self.project.boards):
                board_model.append(b.name or _("Untitled"))
                board_ids.append(b.id)
                if b.id == cell.action.value:
                    selected_idx = i
            board_row.set_model(board_model)
            board_row.set_selected(selected_idx)
            board_row.set_visible(cell.action.action_type == CellAction.NAVIGATE)
            group2.add(board_row)

            def on_action_type_changed(combo, param):
                is_nav = combo.get_selected() == 1
                board_row.set_visible(is_nav)
                action_value_row.set_visible(not is_nav)

            action_row.connect("notify::selected", on_action_type_changed)
            action_value_row.set_visible(cell.action.action_type != CellAction.NAVIGATE)

        content.append(group2)

        # Pictogram search
        group3 = Adw.PreferencesGroup(title=_("Pictogram"))

        if cell.image_url:
            current_img = Gtk.Image()
            current_img.set_pixel_size(64)
            self._load_cell_image(current_img, cell.image_url)
            img_row = Adw.ActionRow(title=_("Current Image"))
            img_row.add_suffix(current_img)
            clear_btn = Gtk.Button(icon_name="edit-clear-symbolic", valign=Gtk.Align.CENTER)
            img_row.add_suffix(clear_btn)
            group3.add(img_row)

        search_row = Adw.EntryRow(title=_("Search ARASAAC"))
        group3.add(search_row)

        search_btn = Gtk.Button(label=_("Search"), halign=Gtk.Align.END)
        search_btn.add_css_class("suggested-action")
        content.append(group3)
        content.append(search_btn)

        # Search results
        results_flow = Gtk.FlowBox()
        results_flow.set_max_children_per_line(5)
        results_flow.set_min_children_per_line(3)
        results_flow.set_selection_mode(Gtk.SelectionMode.SINGLE)
        results_flow.set_homogeneous(True)
        content.append(results_flow)

        selected_pictogram_url = [cell.image_url]

        def on_search(btn):
            query = search_row.get_text().strip()
            if not query:
                return
            # Clear results
            child = results_flow.get_first_child()
            while child:
                next_c = child.get_next_sibling()
                results_flow.remove(child)
                child = next_c

            def do_search():
                results = search_pictograms(query)
                GLib.idle_add(show_results, results)

            def show_results(results):
                for r in results[:20]:
                    url = r["url_500"]
                    pic_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                    img = Gtk.Image()
                    img.set_pixel_size(48)
                    self._load_cell_image(img, url)
                    pic_box.append(img)
                    kw = ", ".join(r["keywords"][:2]) if r["keywords"] else str(r["id"])
                    lbl = Gtk.Label(label=kw)
                    lbl.set_max_width_chars(10)
                    lbl.set_ellipsize(3)
                    pic_box.append(lbl)
                    pic_box.pictogram_url = url
                    results_flow.append(pic_box)

            threading.Thread(target=do_search, daemon=True).start()

        search_btn.connect("clicked", on_search)

        def on_pictogram_selected(flowbox, child):
            if child:
                box = child.get_child()
                if hasattr(box, "pictogram_url"):
                    selected_pictogram_url[0] = box.pictogram_url

        results_flow.connect("child-activated", on_pictogram_selected)

        scroll.set_child(content)
        toolbar_view.set_content(scroll)
        dialog.set_child(toolbar_view)

        # Save on close
        def on_dialog_closed(d):
            cell.label = label_row.get_text()
            rgba = color_btn.get_rgba()
            cell.bg_color = f"#{int(rgba.red*255):02x}{int(rgba.green*255):02x}{int(rgba.blue*255):02x}"
            cell.image_url = selected_pictogram_url[0]

            if action_row.get_selected() == 0:
                cell.action = CellAction(CellAction.SPEAK, action_value_row.get_text())
            else:
                if hasattr(action_row, '_board_ids_ref'):
                    bid = action_row._board_ids_ref[board_row.get_selected()]
                else:
                    # Use board_ids from closure
                    try:
                        bid = board_ids[board_row.get_selected()]
                    except:
                        bid = action_value_row.get_text()
                cell.action = CellAction(CellAction.NAVIGATE, bid)

            self._rebuild_grid()

        def on_delete(btn):
            self.current_board.set_cell(row, col, None)
            dialog.close()
            self._rebuild_grid()

        delete_btn.connect("clicked", on_delete)
        dialog.connect("closed", on_dialog_closed)

        if cell.image_url and 'clear_btn' in dir():
            pass

        dialog.present(self)
