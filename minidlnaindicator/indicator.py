#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

from typing import List, Optional

import dbus
from dbus.service import Object
from dbus.mainloop.glib import DBusGMainLoop
import distro
import getpass
import logging
import logging.config
import os
import shutil
import signal
import subprocess
import time

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
gi.require_version('Notify', '0.7')
from gi.repository import Gtk, AppIndicator3, Notify, GLib, GObject


from .minidlnaconfig import MiniDLNAConfig
from .constants import LOCALE_DIR, APPINDICATOR_ID, MINIDLNA_CONFIG_FILE, \
    MINIDLNA_ICON_GREY, MINIDLNA_ICON_GREEN, APP_DBUS_PATH, APP_DBUS_DOMAIN
from .indicatorconfig import MiniDLNAIndicatorConfig
from .processrunner import ProcessRunner
from .processlistener import ProcessListener
from .ui.utils_ui import msgconfirm, msgbox, MessageTypeEnum
from .fsmonitor import FSMonitorThread
from .fslistener import FSListener
from .exceptions.alreadyrunning import AlreadyRunningException
from .update_check_thread import UpdateCheckThread
from .update_check_listener import UpdateCheckListener
from .version import __version__ as module_version

import gettext
_ = gettext.translation(APPINDICATOR_ID, LOCALE_DIR, fallback=True).gettext


class MiniDLNAIndicator(Object, ProcessListener, FSListener, UpdateCheckListener):

    def __init__(self, config: MiniDLNAIndicatorConfig, test_mode: bool) -> None:

        self.logger = logging.getLogger(__name__)  # type: logging.Logger

        DBusGMainLoop(set_as_default=True)
        try:
            self.session_bus = dbus.SessionBus(dbus.mainloop.glib.DBusGMainLoop())
        except dbus.DBusException:
            raise RuntimeError(_("No D-Bus connection"))

        if self.session_bus.name_has_owner(APP_DBUS_DOMAIN):
            raise AlreadyRunningException()

        bus_name = dbus.service.BusName(APP_DBUS_DOMAIN, self.session_bus)
        dbus.service.Object.__init__(
            self,
            object_path=APP_DBUS_PATH,
            bus_name=bus_name
        )

        self.config = config
        self.test_mode = test_mode

        self.indicator = AppIndicator3.Indicator.new(APPINDICATOR_ID, MINIDLNA_ICON_GREY, AppIndicator3.IndicatorCategory.APPLICATION_STATUS)
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

        self.minidlna_config = MiniDLNAConfig(self, MINIDLNA_CONFIG_FILE)
        self.minidlna_path = None  # type: Optional[str]

        # Build menu items

        self.menu = Gtk.Menu()
        self.indicator.set_menu(self.menu)

        if distro.id() in ["fedora", "centos", "rhel", "ubuntu", "mint"]:
            self.detect_menuitem = Gtk.MenuItem(_("MiniDLNA not installed; click here to install"))
            self.detect_menuitem.connect('activate', lambda _: self.detect_minidlna(auto_start=True, ask_for_install=True))
        else:
            self.detect_menuitem = Gtk.MenuItem(_("MiniDLNA not installed; click here to show how to install"))
            self.detect_menuitem.connect('activate', lambda _: self.run_xdg_open(None, "https://github.com/okelet/minidlnaindicator"))

        self.start_menuitem = Gtk.MenuItem(_("Start MiniDLNA"))
        self.start_menuitem.connect('activate', lambda _: self.start_minidlna())

        self.start_reindex_menuitem = Gtk.MenuItem(_("Start and reindex MiniDLNA"))
        self.start_reindex_menuitem.connect('activate', lambda _: self.start_minidlna(True))

        self.restart_menuitem = Gtk.MenuItem(_("Restart MiniDLNA"))
        self.restart_menuitem.connect('activate', lambda _: self.restart_minidlna())

        self.restart_reindex_menuitem = Gtk.MenuItem(_("Restart and reindex MiniDLNA"))
        self.restart_reindex_menuitem.connect('activate', lambda _: self.restart_minidlna(True))

        self.stop_menuitem = Gtk.MenuItem(_("Stop MiniDLNA"))
        self.stop_menuitem.connect('activate', lambda _: self.stop_minidlna())

        self.weblink_menuitem = Gtk.MenuItem(_("Web interface (port {port})").format(port=self.minidlna_config.port))
        self.weblink_menuitem.connect('activate', self.on_weblink_menuitem_activated)

        self.showlog_menuitem = Gtk.MenuItem(_("Show MiniDLNA LOG"))
        self.showlog_menuitem.connect('activate', self.on_showlog_menuitem_activated)

        self.editconfig_menuitem = Gtk.MenuItem(_("Edit MiniDLNA configuration"))
        self.editconfig_menuitem.connect('activate', self.on_editconfig_menuitem_activated)

        self.indicator_startup_menuitem = Gtk.CheckMenuItem(_("Autostart indicator"))
        self.indicator_startup_menuitem.connect('activate', self.indicator_startup_menuitem_toggled)
        self.indicator_startup_menuitem.set_active(self.config.auto_start)

        self.update_available = None
        self.new_version_menuitem = Gtk.MenuItem(_("A new version of MiniDLNA has been detected; click here to show how to upgrade"))
        self.new_version_menuitem.connect('activate', self.run_xdg_open, "https://github.com/okelet/minidlnaindicator")

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

        # Update check
        self.update_checker = UpdateCheckThread(self.config, "minidlnaindicator", module_version, self.test_mode)
        self.update_checker.add_listener(self)
        self.update_checker.start()

        # Detect minidlna and rebuild menu
        self.detect_minidlna()


    def run(self):

        if self.minidlna_path:
            self.logger.debug("Startup: Auto-Starting MiniDLNA...")
            self.runner.start(self.get_minidlna_command())
        else:
            self.logger.debug("Startup: NOT Auto-Starting MiniDLNA because not found.")
            self.show_notification(
                title=_("MiniDLNA not installed"),
                message=_("MiniDLNA is not installed.")
            )

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
        if self.update_available:
            self.menu.append(self.new_version_menuitem)
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


    def indicator_startup_menuitem_toggled(self, _: Gtk.MenuItem) -> None:
        self.config.auto_start = self.indicator_startup_menuitem.get_active()
        self.config.save(reason="Auto start changed from indicator menu")


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


    def on_process_finished(self, command: str, pid: int, exit_code: int, std_out: Optional[str], std_err: Optional[str]) -> None:

        GLib.idle_add(lambda: self.indicator.set_icon_full(MINIDLNA_ICON_GREY, ""))
        GLib.idle_add(lambda: self.start_menuitem.set_sensitive(True))
        GLib.idle_add(lambda: self.start_reindex_menuitem.set_sensitive(True))
        GLib.idle_add(lambda: self.restart_menuitem.set_sensitive(False))
        GLib.idle_add(lambda: self.restart_reindex_menuitem.set_sensitive(False))
        GLib.idle_add(lambda: self.stop_menuitem.set_sensitive(False))
        GLib.idle_add(lambda: self.weblink_menuitem.set_sensitive(False))

        if exit_code != 0:

            if self.config.enable_orphan_process_killer and ("error: bind(http):" in std_out or "error: bind(http):" in std_err):
                self.logger.warning("Address already in use error message detected; we will try to kill existing orphan process for the same user and start minidlna again.")
                try:
                    pids_str = subprocess.check_output(["pgrep", "-U", getpass.getuser(), "minidlnad"], universal_newlines=True)
                    if pids_str:
                        pids = [x for x in pids_str.split("\n") if x]
                        if len(pids) == 1:
                            # If only 1 old orphan process found, kill it
                            self.logger.warning("Killing orphan minidlna process: %s", pids[0])
                            os.kill(int(pids[0]), signal.SIGTERM)
                            # Wait to finish
                            killed = False
                            finish_time = time.time() + 5
                            while time.time() < finish_time:
                                try:
                                    os.kill(int(pids[0]), 0)
                                    time.sleep(0.2)
                                except OSError:
                                    killed = True
                                    break
                            if killed:
                                self.logger.info("Orphan minidlna process with pid %s killed, starting again minidlna with command %s.", pids[0], command)
                                self.runner.start(command, ignore_running=True)
                                return
                            else:
                                self.logger.error("Orphan minidlna process with pid %s couldn't be killed.", pids[0])
                        elif len(pids) > 1:
                            self.logger.error("Multiple (%s) process found minidlna.", len(pids))
                        else:
                            # No process found for minidlna for the current user; perhaps there is another process using the same port
                            pass
                except Exception as ex:
                    self.logger.exception("Error while detecting existing minidlna process: %s", ex)

            text = ""
            if std_out and std_err:
                text = std_out + "\n" + std_err
            elif std_out:
                text = std_out
            elif std_err:
                text = std_err
            self.logger.error(
                "MiniDLNA has exited without success; PID: %s, return code: %s, std out: %s, std err: %s",
                pid, exit_code, std_out, std_err
            )
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
        self.logger.debug("Recevived notification of FS changed: %s.", new_filesystems)
        GLib.idle_add(self._on_fs_changed)


    def _on_fs_changed(self) -> None:
        self.rebuild_menu()


    def on_update_detected(self, new_version: str) -> None:
        self.logger.debug("Recevived notification of update detected; new version: %s.", new_version)
        GLib.idle_add(self._on_update_detected, new_version)


    def _on_update_detected(self, new_version: str) -> None:
        if not self.update_available or self.update_available != new_version:
            self.update_available = new_version
            self.rebuild_menu()
            self.show_notification(
                title=_("Update available"),
                message=_("A new version ({new_version}) of the application has been released.").format(new_version=new_version)
            )


    def detect_minidlna(self, auto_start: bool=False, ask_for_install: bool=False) -> None:

        prev_path = self.minidlna_path
        self.minidlna_path = shutil.which("minidlnad")
        if prev_path == self.minidlna_path and self.minidlna_path:
            return

        self.rebuild_menu()

        if not self.minidlna_path:

            if ask_for_install and msgconfirm(
                    title=_("MiniDLNA not installed"),
                    message=_("MiniDLNA is not installed. Do you want to install it?"),
                    parent=None
            ) == Gtk.ResponseType.YES:

                try:

                    proxy = self.session_bus.get_object('org.freedesktop.PackageKit', '/org/freedesktop/PackageKit')
                    iface = dbus.Interface(proxy, 'org.freedesktop.PackageKit.Modify')
                    self.logger.debug("Calling InstallPackageNames DBUS method...")
                    iface.InstallPackageNames(dbus.UInt32(0), ["minidlna"], "show-confirm-search,hide-finished")
                    self.logger.debug("InstallPackageNames returned.")

                    # Ubuntu waits until installation is finished, but Fedora returns from the dbus method inmediate.
                    # We check if installed (usually Ubuntu), and if not, notify the user to re-detect minidlna after
                    # installation (usually Fedora).
                    self.minidlna_path = shutil.which("minidlnad")
                    if self.minidlna_path:
                        self.rebuild_menu()
                        if auto_start:
                            self.start_minidlna()
                    else:
                        msgbox(
                            title=_("Confirm installation"),
                            message=_("If after installation, MiniDLNA is not detected automatically, click the indicator menu again."),
                            level=MessageTypeEnum.INFO
                        )


                except dbus.DBusException as e:
                    if e.get_dbus_name() == "org.freedesktop.Packagekit.Modify.Cancelled":
                        self.logger.warning("Intallation cancelled.")
                    elif e.get_dbus_name() == "org.freedesktop.Packagekit.Modify.Forbidden":
                        self.logger.warning("Intallation forbidden.")
                    else:
                        self.logger.exception("Error installing MiniDLNA: %s", str(e))
                        msgbox(
                            title=_("Installation error"),
                            message=_("An error has happened while installing MiniDLNA: {error}.".format(error=str(e))),
                            level=MessageTypeEnum.ERROR,
                        )

        elif auto_start:
            if not self.runner.is_running():
                self.start_minidlna()


    def start_minidlna(self, reindex: bool=False) -> None:

        if self.runner.is_running():
            raise RuntimeError()

        self.runner.start(self.get_minidlna_command(reindex))


    def restart_minidlna(self, reindex: bool=False) -> None:

        if not self.runner.is_running():
            raise RuntimeError()

        finished = self.stop_minidlna()
        if finished:
            self.start_minidlna(reindex)


    def stop_minidlna(self) -> None:

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


    def run_xdg_open(self, _: Gtk.MenuItem, uri: str) -> None:
        subprocess.call(["xdg-open", uri])


    def quit(self, _: Gtk.MenuItem) -> None:

        self.logger.debug("Exiting...")

        self.logger.debug("Stopping FS monitor thread...")
        if self.fs_monitor.is_alive():
            self.fs_monitor.stop()

        self.logger.debug("Stopping update checker thread...")
        if self.update_checker.is_alive():
            self.update_checker.stop()

        self.logger.debug("Stopping MiniDLNA runner thread...")
        if self.runner.is_running():
            self.stop_minidlna()

        self.logger.debug("Stopping Notify...")
        Notify.uninit()

        self.logger.debug("Exiting main loop...")
        self.mainloop.quit()

