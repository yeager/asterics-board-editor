#!/usr/bin/env python3
"""Main entry point for AsTeRICS Board Editor."""

import sys
import gi
import gettext
import locale
import os

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, Gio, GLib

from asterics_board_editor import __app_id__, __version__
from asterics_board_editor.window import EditorWindow

# i18n setup
LOCALE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "po")
try:
    locale.bindtextdomain("asterics-board-editor", LOCALE_DIR)
    locale.textdomain("asterics-board-editor")
except:
    pass
gettext.bindtextdomain("asterics-board-editor", LOCALE_DIR)
gettext.textdomain("asterics-board-editor")
_ = gettext.gettext


class Application(Adw.Application):
    """Main application class."""

    def __init__(self):
        super().__init__(
            application_id=__app_id__,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.set_resource_base_path("/se/danielnylander/asterics-board-editor")

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = EditorWindow(application=self)
        win.present()

    def do_startup(self):
        Adw.Application.do_startup(self)
        self._setup_actions()

    def _setup_actions(self):
        actions = [
            ("quit", self._on_quit),
            ("about", self._on_about),
        ]
        for name, callback in actions:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

        self.set_accels_for_action("app.quit", ["<primary>q"])

    def _on_quit(self, action, param):
        self.quit()

    def _on_about(self, action, param):
        about = Adw.AboutDialog(
            application_name=_("AsTeRICS Board Editor"),
            application_icon=__app_id__,
            version=__version__,
            developer_name="Daniel Nylander",
            license_type=Gtk.License.GPL_3_0,
            website="https://github.com/yeager/asterics-board-editor",
            issue_url="https://github.com/yeager/asterics-board-editor/issues",
            developers=["Daniel Nylander"],
            # Translators: Replace with your name for translation credit
            translator_credits=_("translator-credits"),
            copyright="© 2026 Daniel Nylander",
        )
        about.present(self.props.active_window)


def main():
    app = Application()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
