#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

from typing import List, Optional

import argparse
import dbus
from dbus.service import Object
from dbus.mainloop.glib import DBusGMainLoop
import distro
import codecs
import logging
import logging.config
import os
import shutil
import subprocess
import sys
import threading

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
gi.require_version('Notify', '0.7')
from gi.repository import Gtk, AppIndicator3, Notify, GLib, GObject


from .minidlnaconfig import MiniDLNAConfig
from .constants import LOG_DIR, LOG_LEVELS, LOGGING_CONFIG, LOCALE_DIR, APPINDICATOR_ID, MINIDLNA_CONFIG_DIR, MINIDLNA_CONFIG_FILE, \
    MINIDLNA_INDICATOR_CONFIG, XDG_CONFIG_DIR, XDG_AUTOSTART_DIR, XDG_AUTOSTART_FILE, \
    MINIDLNA_ICON_GREY, MINIDLNA_ICON_GREEN, APP_DBUS_PATH, APP_DBUS_DOMAIN
from .indicatorconfig import MiniDLNAIndicatorConfig
from .processrunner import ProcessRunner
from .processlistener import ProcessListener
from .ui.utils_ui import msgconfirm
from .fsmonitor import FSMonitorThread
from .fslistener import FSListener
from .utils import run_command
from .exceptions.alreadyrunning import AlreadyRunningException

import gettext
_ = gettext.translation(APPINDICATOR_ID, LOCALE_DIR, fallback=True).gettext


class MiniDLNAIndicator(Object, ProcessListener, FSListener):
    """
    :type logger: logging.Loggger
    :type config: MiniDLNAIndicatorConfig

    :type indicator: AppIndicator3.Indicator

    :type minidlna_pid: int

    :type menu: Gtk.Menu
    :type showlog_menuitem: Gtk.MenuItem
    """
    def __init__(self) -> None:

        self.logger = logging.getLogger(__name__)

        try:
            session_bus = dbus.SessionBus(dbus.mainloop.glib.DBusGMainLoop())
        except dbus.DBusException:
            raise RuntimeError(_("No D-Bus connection"))

        if session_bus.name_has_owner(APP_DBUS_DOMAIN):
            raise AlreadyRunningException()

        bus_name = dbus.service.BusName(APP_DBUS_DOMAIN, session_bus)
        dbus.service.Object.__init__(
            self,
            object_path=APP_DBUS_PATH,
            bus_name=bus_name
        )

        if not os.path.exists(MINIDLNA_CONFIG_DIR):
            os.mkdir(MINIDLNA_CONFIG_DIR)
        self.config = MiniDLNAIndicatorConfig(MINIDLNA_INDICATOR_CONFIG)
        self.set_gnome_autostart(self.config.startup_indicator)

        self.indicator = AppIndicator3.Indicator.new(APPINDICATOR_ID, MINIDLNA_ICON_GREY, AppIndicator3.IndicatorCategory.APPLICATION_STATUS)
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

        self.minidlna_config = MiniDLNAConfig(self, MINIDLNA_CONFIG_FILE)
        self.minidlna_path = None  # type: Optional[str]

        # Build menu items

        self.menu = Gtk.Menu()
        self.indicator.set_menu(self.menu)

        if distro.id() in ["fedora", "centos", "rhel"]:
            self.detect_menuitem = Gtk.MenuItem(_("MiniDLNA not installed; click here to show how to install"))
            self.detect_menuitem.connect('activate', lambda _: self.run_xdg_open(None, "https://github.com/okelet/minidlnaindicator"))
        elif distro.id() in ["ubuntu", "mint"]:
            self.detect_menuitem = Gtk.MenuItem(_("MiniDLNA not installed; click here to install"))
            self.detect_menuitem.connect('activate', lambda _: self.detect_minidlna(auto_start=True, ask_for_install=True))
        else:
            self.detect_menuitem = Gtk.MenuItem(_("MiniDLNA not installed"))

        self.start_menuitem = Gtk.MenuItem(_("Start MiniDLNA"))
        self.start_menuitem.connect('activate', lambda _: self.start_minidlna_process())

        self.start_reindex_menuitem = Gtk.MenuItem(_("Start and reindex MiniDLNA"))
        self.start_reindex_menuitem.connect('activate', lambda _: self.start_minidlna_process(True))

        self.restart_menuitem = Gtk.MenuItem(_("Restart MiniDLNA"))
        self.restart_menuitem.connect('activate', lambda _: self.restart_minidlna_process_nonblocking())

        self.restart_reindex_menuitem = Gtk.MenuItem(_("Restart and reindex MiniDLNA"))
        self.restart_reindex_menuitem.connect('activate', lambda _: self.restart_minidlna_process_nonblocking(True))

        self.stop_menuitem = Gtk.MenuItem(_("Stop MiniDLNA"))
        self.stop_menuitem.connect('activate', lambda _: self.stop_minidlna_process_nonblocking())

        self.weblink_menuitem = Gtk.MenuItem(_("Web interface (port {port})").format(port=self.minidlna_config.port))
        self.weblink_menuitem.connect('activate', self.on_weblink_menuitem_activated)

        self.showlog_menuitem = Gtk.MenuItem(_("Show MiniDLNA LOG"))
        self.showlog_menuitem.connect('activate', self.on_showlog_menuitem_activated)

        self.editconfig_menuitem = Gtk.MenuItem(_("Edit MiniDLNA configuration"))
        self.editconfig_menuitem.connect('activate', self.on_editconfig_menuitem_activated)

        self.indicator_startup_menuitem = Gtk.CheckMenuItem(_("Autostart indicator"))
        self.indicator_startup_menuitem.connect('activate', self.indicator_startup_menuitem_toggled)
        self.indicator_startup_menuitem.set_active(self.config.startup_indicator)

        self.minidlna_help_menuitem = Gtk.MenuItem(_("MiniDLNA help"))
        self.minidlna_help_menuitem.connect('activate', self.run_xdg_open, "https://help.ubuntu.com/community/MiniDLNA")

        self.indicator_help_menuitem = Gtk.MenuItem(_("MiniDLNA Indicator help"))
        self.indicator_help_menuitem.connect('activate', self.run_xdg_open, "https://github.com/okelet/minidlnaindicator")

        self.item_quit = Gtk.MenuItem(_("Quit"))
        self.item_quit.connect('activate', self.quit)

        self.runner = ProcessRunner()
        self.runner.add_listener(self)

        self.rebuild_menu()

        # Init notifications before running minidlna
        Notify.init(APPINDICATOR_ID)

        # FS Monitor
        self.fs_monitor = FSMonitorThread()
        self.fs_monitor.add_listener(self)
        self.fs_monitor.start()

        # Detect minidlna and rebuild menu
        self.detect_minidlna()

        # Start minidlna
        if self.minidlna_path:
            self.logger.debug("Startup: Auto-Starting MiniDLNA...")
            self.runner.start(self.get_minidlna_command())
        else:
            self.logger.debug("Startup: NOT Auto-Starting MiniDLNA because not found.")

        # http://stackoverflow.com/questions/16410852/keyboard-interrupt-with-with-python-gtk
        self.mainloop = GObject.MainLoop()
        try:
            self.mainloop.run()
        except KeyboardInterrupt:
            self.logger.info("Ctrl+C hit, quitting")
            self.quit(None)


    def get_minidlna_command(self, reindex: bool=False) -> List[str]:

        if self.minidlna_path:

            command = [
                self.minidlna_path,
                "-f", MINIDLNA_CONFIG_FILE,
                "-P", "/dev/null",
                "-S"
            ]
            if reindex:
                command.append("-R")
            return command

        else:
            raise RuntimeError()


    def show_notification(self, title: str, message: str) -> None:
        Notify.Notification.new(
            title,
            message,
            MINIDLNA_ICON_GREEN if self.runner.is_running() else MINIDLNA_ICON_GREY
        ).show()


    """
    def on_config_file_change(self, event):
        if event.src_path == MINIDLNA_CONFIG_FILE:
            if self.minidlna_pid:
                self.show_notification(
                    _("Configuration changed"),
                    _("A change in the MiniDLNA configuration has been detected; you should restart MiniDLNA to reflect these changes.")
                )
            else:
                self.minidlna_config.reload_config()
                GLib.idle_add(self.rebuild_menu)
    """

    def rebuild_menu(self) -> None:

        for item in self.menu.get_children():
            self.menu.remove(item)

        if self.minidlna_path:

            self.start_menuitem.set_sensitive(not self.runner.is_running())
            self.menu.append(self.start_menuitem)

            self.start_reindex_menuitem.set_sensitive(not self.runner.is_running())
            self.menu.append(self.start_reindex_menuitem)

            self.restart_menuitem.set_sensitive(self.runner.is_running())
            self.menu.append(self.restart_menuitem)

            self.restart_reindex_menuitem.set_sensitive(self.runner.is_running())
            self.menu.append(self.restart_reindex_menuitem)

            self.stop_menuitem.set_sensitive(self.runner.is_running())
            self.menu.append(self.stop_menuitem)

            self.weblink_menuitem.set_sensitive(self.runner.is_running())
            self.menu.append(self.weblink_menuitem)

        else:

            self.menu.append(self.detect_menuitem)

        self.menu.append(Gtk.SeparatorMenuItem())

        if self.minidlna_config.dirs:

            for minidlna_dir in self.minidlna_config.dirs:
                display_type = "[" + minidlna_dir.description + "] "
                dir_menuitem = Gtk.MenuItem("{display_type}{path}".format(display_type=display_type, path=minidlna_dir.path))
                dir_menuitem.connect('activate', self.run_xdg_open, minidlna_dir.path)
                if not minidlna_dir.accessable:
                    dir_menuitem.set_sensitive(False)
                    dir_menuitem.set_tooltip_text(_("Directory does not exist"))
                self.menu.append(dir_menuitem)

        else:
            nodirs_menuitem = Gtk.MenuItem(_("No media folders specified; please, edit the configuration."))
            nodirs_menuitem.set_sensitive(False)
            self.menu.append(nodirs_menuitem)

        self.menu.append(Gtk.SeparatorMenuItem())
        self.menu.append(self.showlog_menuitem)
        self.menu.append(self.editconfig_menuitem)
        self.menu.append(Gtk.SeparatorMenuItem())
        self.menu.append(self.indicator_startup_menuitem)
        self.menu.append(Gtk.SeparatorMenuItem())
        self.menu.add(self.minidlna_help_menuitem)
        self.menu.add(self.indicator_help_menuitem)
        self.menu.append(self.item_quit)

        self.menu.show_all()


    def on_weblink_menuitem_activated(self, menu_item: Gtk.MenuItem) -> None:
        self.run_xdg_open(menu_item, "http://localhost:{port}".format(port=self.minidlna_config.port))


    def on_showlog_menuitem_activated(self, menu_item: Gtk.MenuItem) -> None:
        self.run_xdg_open(menu_item, self.minidlna_config.log)


    def on_editconfig_menuitem_activated(self, menu_item: Gtk.MenuItem) -> None:
        self.run_xdg_open(menu_item, MINIDLNA_CONFIG_FILE)


    def indicator_startup_menuitem_toggled(self, menu_item: Gtk.MenuItem) -> None:
        if self.indicator_startup_menuitem.get_active():
            self.config.startup_indicator = True
        else:
            self.config.startup_indicator = False
        self.set_gnome_autostart(self.config.startup_indicator)
        self.config.save()


    def set_gnome_autostart(self, enabled: bool) -> None:

        # ~/.config
        if not os.path.exists(XDG_CONFIG_DIR):
            os.mkdir(XDG_CONFIG_DIR)

        # ~/.config/autostart
        if not os.path.exists(XDG_AUTOSTART_DIR):
            os.mkdir(XDG_AUTOSTART_DIR)

        with codecs.open(XDG_AUTOSTART_FILE, "w", "utf-8") as f:
            f.write("[Desktop Entry]\n")
            f.write("Encoding = UTF-8\n")
            f.write("Type = Application\n")
            f.write("Name = " + _("MiniDLNA Indicator") + "\n")
            f.write("Exec = minidlnaindicator\n")
            f.write("Icon = " + MINIDLNA_ICON_GREEN + "\n")
            f.write("Comment = " + _("Indicator for launching MiniDLNA as a normal user") + "\n")
            f.write("X-GNOME-Autostart-enabled = {value}\n".format(value='true' if enabled else 'false'))
            f.write("Terminal = false\n")


    #################################################################################################################
    # Listener
    #################################################################################################################

    def on_process_starting(self) -> None:
        GLib.idle_add(lambda: self.indicator.set_icon_full(MINIDLNA_ICON_GREY, ""))
        GLib.idle_add(lambda: self.start_menuitem.set_sensitive(False))
        GLib.idle_add(lambda: self.start_reindex_menuitem.set_sensitive(False))
        GLib.idle_add(lambda: self.restart_menuitem.set_sensitive(False))
        GLib.idle_add(lambda: self.restart_reindex_menuitem.set_sensitive(False))
        GLib.idle_add(lambda: self.stop_menuitem.set_sensitive(False))
        GLib.idle_add(lambda: self.weblink_menuitem.set_sensitive(False))


    def on_process_started(self, pid: int) -> None:
        GLib.idle_add(lambda: self.indicator.set_icon_full(MINIDLNA_ICON_GREEN, ""))
        GLib.idle_add(lambda: self.start_menuitem.set_sensitive(False))
        GLib.idle_add(lambda: self.start_reindex_menuitem.set_sensitive(False))
        GLib.idle_add(lambda: self.restart_menuitem.set_sensitive(True))
        GLib.idle_add(lambda: self.restart_reindex_menuitem.set_sensitive(True))
        GLib.idle_add(lambda: self.stop_menuitem.set_sensitive(True))
        GLib.idle_add(lambda: self.weblink_menuitem.set_sensitive(True))


    def on_process_finished(self, pid: int, exit_code: int, std_out: Optional[str], std_err: Optional[str]) -> None:
        GLib.idle_add(lambda: self.indicator.set_icon_full(MINIDLNA_ICON_GREY, ""))
        GLib.idle_add(lambda: self.start_menuitem.set_sensitive(True))
        GLib.idle_add(lambda: self.start_reindex_menuitem.set_sensitive(True))
        GLib.idle_add(lambda: self.restart_menuitem.set_sensitive(False))
        GLib.idle_add(lambda: self.restart_reindex_menuitem.set_sensitive(False))
        GLib.idle_add(lambda: self.stop_menuitem.set_sensitive(False))
        GLib.idle_add(lambda: self.weblink_menuitem.set_sensitive(False))
        if exit_code != 0:
            text = ""
            if std_out and std_err:
                text = std_out + "\n" + std_err
            elif std_out:
                text = std_out
            elif std_err:
                text = std_err
            self.show_notification(
                title=_("MiniDLNA error"),
                message=_("MiniDLNA has exited with a code {code} and this text {text}.".format(code=exit_code, text=text))
            )


    def on_process_error(self, reason: str) -> None:
        self.show_notification(
            _("Error running MiniDLNA"),
            reason
        )


    def on_fs_changed(self, new_filesystems: List[str]) -> None:
        # raise NotImplementedError()
        self.logger.debug("Recevived notification of FS changed: {new_filesystems}.".format(new_filesystems=new_filesystems))
        self.rebuild_menu()


    def detect_minidlna(self, auto_start: bool=False, ask_for_install: bool=False) -> None:

        self.minidlna_path = shutil.which("minidlnad")
        self.rebuild_menu()

        if not self.minidlna_path:
            self.show_notification(_("MiniDLNA not installed"), _("MiniDLNA is not installed."))
            if ask_for_install:
                apturl_path = shutil.which("apturl")
                if apturl_path:
                    if msgconfirm(
                        title=_("MiniDLNA not installed"),
                        message=_("MiniDLNA is not installed. Do you want to install it?"),
                        parent=None
                    ) == Gtk.ResponseType.YES:
                        pid, exit_code, std_out, std_err = run_command(["apturl", "apt://minidlna"])
                        if exit_code == 0:
                            self.minidlna_path = shutil.which("minidlnad")
                            self.rebuild_menu()
                            if auto_start:
                                self.start_minidlna_process()
                        else:
                            self.logger.error("Error running apturl: PID: {pid}, exit code: {exit_code}, stdout: {std_out}, stderr: {std_err}.".format(pid=pid, exit_code=exit_code, std_out=std_out, std_err=std_err))
                else:
                    self.logger.warning("Couldn't find apturl.")


    def start_minidlna_process(self, reindex: bool=False) -> None:

        if self.runner.is_running():
            raise RuntimeError()

        self.runner.start(self.get_minidlna_command(reindex))


    def restart_minidlna_process_nonblocking(self, reindex: bool=False) -> None:

        if not self.runner.is_running():
            raise RuntimeError()

        t = threading.Thread(target=self.restart_minidlna_process_blocking, kwargs={"reindex": reindex})
        t.start()


    def restart_minidlna_process_blocking(self, reindex: bool=False) -> None:

        if not self.runner.is_running():
            raise RuntimeError()

        finished = self.stop_minidlna_process_blocking()
        if finished:
            self.start_minidlna_process(reindex)


    def stop_minidlna_process_nonblocking(self) -> None:

        if not self.runner.is_running():
            raise RuntimeError()

        t = threading.Thread(target=self.stop_minidlna_process_blocking)
        t.start()


    def stop_minidlna_process_blocking(self) -> bool:

        if not self.runner.is_running():
            raise RuntimeError()

        killed = self.runner.stop()
        if not killed:
            self.logger.warning("MiniDLNA has not finished after the kill signal in the allowed time.")
            self.show_notification(
                _("MiniDLNA not stopped"),
                _("MiniDLNA has not stopped in the allowed time; perhaps it is slow and will finish later."),
            )

        return killed


    def run_xdg_open(self, menu_item: Gtk.MenuItem, uri: str) -> None:
        subprocess.call(["xdg-open", uri])


    def quit(self, menu_item: Gtk.MenuItem) -> None:

        self.logger.debug("Exiting...")

        self.logger.debug("Stopping FS monitor thread...")
        if self.fs_monitor.is_alive():
            self.fs_monitor.stop()

        self.logger.debug("Stopping MiniDLNA runner thread...")
        if self.runner.is_running():
            self.stop_minidlna_process_blocking()

        self.logger.debug("Stopping Notify...")
        Notify.uninit()

        self.logger.debug("Exiting main loop...")
        self.mainloop.quit()


def main() -> None:

    if not os.path.exists(LOG_DIR):
        os.mkdir(LOG_DIR)

    parser = argparse.ArgumentParser()
    parser.add_argument('--stderr', action='store_true')
    parser.add_argument('-l', '--log-level', choices=LOG_LEVELS.keys())
    args = parser.parse_args()

    if args.stderr:
        LOGGING_CONFIG["loggers"]["minidlnaindicator"]["handlers"].append("console_handler")

    if args.log_level:
        LOGGING_CONFIG["loggers"]["minidlnaindicator"]["level"] = LOG_LEVELS.get(args.log_level)

    logging.config.dictConfig(LOGGING_CONFIG)
    logger = logging.getLogger(__name__)

    DBusGMainLoop(set_as_default=True)
    try:
        app = MiniDLNAIndicator()
        # app.run()
    except AlreadyRunningException as ex:
        logger.info("Application already running.")
        print(_("Application already running."))
        sys.exit(0)


if __name__ == "__main__":

    main()
