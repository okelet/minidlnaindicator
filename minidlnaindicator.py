#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import argparse
import codecs
from datetime import datetime
import getpass
import logging, logging.config
import os
from pprint import pprint, pformat
import pydbus
import random
import re
import subprocess
import sys
import threading
import time
import uuid
import yaml

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
gi.require_version('Notify', '0.7')
from gi.repository import Gtk, AppIndicator3, Notify, GLib, Gdk, GObject


BASEDIR = os.path.dirname(os.path.abspath(sys.argv[0]))
APPINDICATOR_ID = 'minidlnaindicator'

import gettext
_ = gettext.translation(APPINDICATOR_ID, os.path.join(BASEDIR, "locale"), fallback=True).ugettext
__ = gettext.translation(APPINDICATOR_ID, os.path.join(BASEDIR, "locale"), fallback=True).ungettext


MINIDLNA_CONFIG_DIR = os.path.expanduser("~/.minidlna")
MINIDLNA_CONFIG_FILE = os.path.join(MINIDLNA_CONFIG_DIR, "minidlna.conf")
MINIDLNA_PID_FILE = os.path.join(MINIDLNA_CONFIG_DIR, "minidlna.pid")
MINIDLNA_CACHE_DIR = os.path.join(MINIDLNA_CONFIG_DIR, "cache")
MINIDLNA_LOG_DIR = MINIDLNA_CONFIG_DIR
MINIDLNA_LOG_FILE = os.path.join(MINIDLNA_LOG_DIR, "minidlna.log")
MINIDLNA_INDICATOR_CONFIG = os.path.join(MINIDLNA_CONFIG_DIR, "indicator.yml")

GNOME_CONFIG_DIR = os.path.expanduser("~/.config")
GNOME_AUTOSTART_DIR = os.path.join(GNOME_CONFIG_DIR, "autostart")
MINIDLNA_INDICATOR_GNOME_AUTOSTART_FILE = os.path.join(GNOME_AUTOSTART_DIR, APPINDICATOR_ID + ".desktop")

GNOME_MENU_APPS_DIR = os.path.expanduser("~/.local/share/applications")
MINIDLNA_INDICATOR_GNOME_MENU_APPS_FILE = os.path.join(GNOME_MENU_APPS_DIR, APPINDICATOR_ID + ".desktop")

MINIDLNA_ICON_GREY = os.path.join(BASEDIR, "dlna_grey_32.png")
MINIDLNA_ICON_GREEN = os.path.join(BASEDIR, "dlna_green_32.png")

# AUDIO_ICON = os.path.join(BASEDIR, "audio.svg")
# PICTURE_ICON = os.path.join(BASEDIR, "picture.svg")
# PICTUREVIDEO_ICON = os.path.join(BASEDIR, "picturevideo.svg")
# VIDEO_ICON = os.path.join(BASEDIR, "video.svg")
# MIXED_ICON = os.path.join(BASEDIR, "mixed.svg")


def run_command(command):
    pipes = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    pid = pipes.pid
    std_out, std_err = pipes.communicate()
    return pid, pipes.returncode, std_out, std_err


def get_minidlna_path():
    command_pid, returncode, std_out, std_err = run_command("/usr/bin/which minidlnad")
    if returncode == 0:
        return std_out.strip()
    else:
        return None


def bytearray_to_string(thebytearray):
    return u"".join(chr(val) for val in thebytearray).rstrip(u"\x00")


class DBusPropertiesChanged(object):

    def __init__(self, indicator, dev_path):
        self.indicator = indicator
        self.dev_path = dev_path

    def properties_changed(self, type, properties, others):
        self.indicator.device_changed(self.dev_path, type, properties)


class MiniDLNAIndicator(object):

    def __init__(self):

        self.logger = logging.getLogger(self.__class__.__name__)

        if not os.path.exists(MINIDLNA_CONFIG_DIR):
            os.mkdir(MINIDLNA_CONFIG_DIR)
        self.config = MiniDLNAIndicatorConfig(MINIDLNA_INDICATOR_CONFIG)
        self.set_gnome_autostart(self.config.startup_indicator)

        self.indicator = AppIndicator3.Indicator.new(APPINDICATOR_ID, MINIDLNA_ICON_GREY, AppIndicator3.IndicatorCategory.APPLICATION_STATUS)
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

        self.minidlna_running = False
        self.minidlna_path = None
        self.minidlna_port = 0
        self.minidlna_dirs = []
        self.minidlna_logdir = None

        self.minidlna_not_installed_menuitem = None
        self.install_minidlna_menuitem = None
        self.minidlna_detect_menuitem = None

        self.reload_configuration_menuitem = None
        self.start_menuitem = None
        self.start_reindex_menuitem = None
        self.restart_menuitem = None
        self.restart_reindex_menuitem = None
        self.stop_menuitem = None
        self.weblink_menuitem = None
        self.editconfig_menuitem = None
        self.showlog_menuitem = None
        self.indicator_startup_menuitem = None
        self.minidlna_startup_menuitem = None
        self.minidlna_stop_on_exit_menuitem = None
        self.item_quit = None

        self.ensure_menu_shotcut()

        self.logger.debug(u"Startup: Detecting MiniDLNA...")
        self.detect_minidlna()

        # Monitor for usb disks plugs
        self.current_partitions = []
        self.bus = pydbus.SystemBus()
        self.udisks2_manager = self.bus.get('.UDisks2')

        for path, properties in self.udisks2_manager.GetManagedObjects().items():
            block_properties = properties.get('org.freedesktop.UDisks2.Block')
            filesystem_properties = properties.get('org.freedesktop.UDisks2.Filesystem')
            if block_properties and filesystem_properties:
                self.add_device(path, block_properties, filesystem_properties)
        self.udisks2_manager.onInterfacesAdded = self.device_added
        self.udisks2_manager.onInterfacesRemoved = self.device_removed

        if self.config.startup_minidlna:
            if not self.get_minidlna_pid():
                self.logger.debug(u"Startup: Auto-Starting MiniDLNA...")
                self.start_minidlna_process()

        Notify.init(APPINDICATOR_ID)

        self.logger.debug(u"Starting thread to monitor minidlna status...")
        self.background_minidlna_running_status_changes_stopevent = threading.Event()
        self.background_minidlna_running_status_changes_thread = threading.Thread(target=self.background_minidlna_running_status_changes)
        self.background_minidlna_running_status_changes_thread.start()

        # Notify if minidlna not found
        if not self.minidlna_path:
            Notify.Notification.new(
                _(u"MiniDLNA not installed"),
                _(u"MiniDLNA is not installed; please, click in the menu to install it."),
                None
            ).show()

        # http://stackoverflow.com/questions/16410852/keyboard-interrupt-with-with-python-gtk
        self.mainloop = GObject.MainLoop()
        try:
            self.mainloop.run()
        except KeyboardInterrupt:
            self.logger.info(u"Ctrl+C hit, quitting")
            self.quit(None)


    def add_device(self, path, block_properties, filesystem_properties):
        device = bytearray_to_string(block_properties.get('Device'))
        mountpoints = [bytearray_to_string(v) for v in filesystem_properties.get("MountPoints", [])]
        if not mountpoints:
            self.logger.warn(u"Device {device} has no mountpoints.".format(device=device))
        self.current_partitions.append({"dbus_path": path, "device": device, "mountpoints": mountpoints})
        self.logger.info(u"{path}, adding device {device} in {mountpoints}.".format(path=path, device=device, mountpoints=", ".join(mountpoints)))
        self.filesystem_changed(mountpoints)


    def device_added(self, path, properties):
        types = properties.keys()
        if sorted(types) == sorted(['org.freedesktop.UDisks2.Partition', 'org.freedesktop.UDisks2.Filesystem', 'org.freedesktop.UDisks2.Block']):
            self.logger.info(u"Detected connection of {path}...".format(path=path))
            block_properties = properties.get('org.freedesktop.UDisks2.Block')
            filesystem_properties = properties.get('org.freedesktop.UDisks2.Filesystem')
            if block_properties and filesystem_properties:
                dev = self.bus.get('.UDisks2', path)
                dev.onPropertiesChanged = DBusPropertiesChanged(self, path).properties_changed
                self.add_device(path, block_properties, filesystem_properties)


    def device_changed(self, path, type, properties):
        if type == "org.freedesktop.UDisks2.Filesystem" and 'MountPoints' in properties:
            found_fs = None
            for fs_data in self.current_partitions:
                if fs_data.get("dbus_path") == path:
                    found_fs = fs_data
                    break
            if found_fs:
                mountpoints = [bytearray_to_string(v) for v in properties.get('MountPoints')]
                self.logger.debug(u"Changing mountpoints of {device} from {old_mp} to {new_mp}.".format(device=found_fs["device"], old_mp=found_fs["mountpoints"], new_mp=mountpoints))
                for mountpoint in list(set(found_fs["mountpoints"]) - set(mountpoints)):
                    self.logger.debug(u"Waiting for removed {mountpoint} to not exist...".format(mountpoint=mountpoint))
                    while os.path.exists(mountpoint):
                        time.sleep(1)
                found_fs["mountpoints"] = mountpoints
                self.filesystem_changed(mountpoints)


    def device_removed(self, path, types):
        if sorted(types) == sorted(['org.freedesktop.UDisks2.Partition', 'org.freedesktop.UDisks2.Filesystem', 'org.freedesktop.UDisks2.Block']):
            self.logger.info(u"Detected disconnection of {path}...".format(path=path))
            found_fs = None
            for fs_data in self.current_partitions:
                if fs_data.get("dbus_path") == path:
                    found_fs = fs_data
                    break
            if found_fs:
                for mountpoint in found_fs["mountpoints"]:
                    self.logger.debug(u"Waiting for {mountpoint} to not exist...".format(mountpoint=mountpoint))
                    while os.path.exists(mountpoint):
                        time.sleep(1)
                self.current_partitions.remove(found_fs)
                self.filesystem_changed(found_fs.get("mountpoints"))


    def filesystem_changed(self, mountpoints):

        changes_detected = False
        for dir in self.minidlna_dirs:
            for mountpoint in mountpoints:
                if dir["path"].startswith(mountpoint):
                    self.logger.debug(u"The path for the media dir {dir} is under {mountpoint}; MiniDLNA needs restart.".format(dir=dir["path"], mountpoint=mountpoint))
                    changes_detected = True
                    break
            if changes_detected:
                break

        if changes_detected:
            self.logger.debug(u"Rebuilding menu...")
            self.build_menu()
            if self.get_minidlna_pid():
                self.logger.debug(u"Restarting MiniDLNA...")
                # Fixme: reindex a true
                self.restart_minidlna_process_nonblocking(False)


    def ensure_menu_shotcut(self):
        if os.path.exists(GNOME_MENU_APPS_DIR):
            with codecs.open(MINIDLNA_INDICATOR_GNOME_MENU_APPS_FILE, "w", "utf-8") as f:
                f.write("[Desktop Entry]\n")
                f.write("Type = Application\n")
                f.write("Encoding = UTF-8\n")
                f.write("Name = " + _(u"MiniDLNA Indicator") + "\n")
                f.write("Exec = " + os.path.abspath(sys.argv[0]) + "\n")
                f.write("Icon = " + MINIDLNA_ICON_GREEN + "\n")
                f.write("Comment = " + _(u"Indicator for launching MiniDLNA as a normal user") + "\n")
                f.write("Terminal = false\n")


    def reset_minidlna_settings(self):

        self.minidlna_path = None
        self.minidlna_port = 0
        self.minidlna_dirs = []
        self.minidlna_logdir = None


    def detect_minidlna(self):

        self.minidlna_path = get_minidlna_path()

        if self.minidlna_path:
            self.configure_minidlna()
        else:
            self.reset_minidlna_settings()
        self.build_menu()
        self.check_running_and_update_menu_status()


    def background_minidlna_running_status_changes(self):
        self.logger.debug(u"Starting minidlna running status background thread...")
        while not self.background_minidlna_running_status_changes_stopevent.is_set():
            self.logger.debug(u"Periodic task: Checking MiniDLNA status...")
            self.check_running_and_update_menu_status()
            self.background_minidlna_running_status_changes_stopevent.wait(5)
        self.logger.debug(u"Stopping minidlna running status background thread...")


    def configure_minidlna(self):

        if not os.path.exists(MINIDLNA_CONFIG_DIR):
            self.logger.debug(u"Creating config dir: {config_dir}...".format(cache_dir=MINIDLNA_CONFIG_DIR))
            os.mkdir(MINIDLNA_CONFIG_DIR)

        if not os.path.exists(MINIDLNA_CACHE_DIR):
            self.logger.debug(u"Creating cache dir: {cache_dir}...".format(cache_dir=MINIDLNA_CACHE_DIR))
            os.mkdir(MINIDLNA_CACHE_DIR)

        if not os.path.exists(MINIDLNA_CONFIG_FILE):

            self.logger.debug(u"Creating initial config file...")
            with codecs.open(MINIDLNA_CONFIG_FILE, "w", "utf-8") as f:
                home_dir = os.path.expanduser("~")
                f.write(u"db_dir={db_dir}\n".format(db_dir=MINIDLNA_CACHE_DIR))
                self.minidlna_logdir = MINIDLNA_LOG_DIR
                f.write(u"log_dir={log_dir}\n".format(log_dir=self.minidlna_logdir))
                self.minidlna_port = 8200+random.randint(1, 99)
                self.logger.debug(u"Setting port to {port}".format(port=self.minidlna_port))
                f.write(u"port={port}\n".format(port=self.minidlna_port))
                f.write(u"uuid={uuid}\n".format(uuid=str(uuid.uuid4())))
                f.write(u"friendly_name=" + _(u"Multimedia for {user}").format(user=getpass.getuser()) + "\n")

                download_dir = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD)
                if download_dir:
                    if download_dir != home_dir:
                        download_dir = download_dir.decode('utf-8')
                        self.logger.debug(u"Adding folder {folder} as downloads...".format(folder=download_dir))
                        f.write(u"media_dir={media_dir}\n".format(media_dir=download_dir))
                        self.minidlna_dirs.append({"path": download_dir, "type": "mixed"})
                    else:
                        self.logger.debug(u"Detected download folder {folder} is the same as the home folder; ignoring.".format(folder=download_dir))
                else:
                    self.logger.debug(u"Couldn't detect download folder; ignoring.")

                pictures_dir = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES)
                if pictures_dir:
                    if pictures_dir != home_dir:
                        pictures_dir = pictures_dir.decode('utf-8')
                        self.logger.debug(u"Adding folder {folder} as pictures...".format(folder=pictures_dir))
                        f.write(u"media_dir=P,{media_dir}\n".format(media_dir=pictures_dir))
                        self.minidlna_dirs.append({"path": pictures_dir, "type": "pictures"})
                    else:
                        self.logger.debug(u"Detected pictures folder {folder} is the same as the home folder; ignoring.".format(folder=pictures_dir))
                else:
                    self.logger.debug(u"Couldn't detect pictures folder; ignoring.")

                music_dir = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_MUSIC)
                if music_dir:
                    if music_dir != home_dir:
                        music_dir = music_dir.decode('utf-8')
                        self.logger.debug(u"Adding folder {folder} as music...".format(folder=music_dir))
                        f.write(u"media_dir=A,{media_dir}\n".format(media_dir=music_dir))
                        self.minidlna_dirs.append({"path": music_dir, "type": "audio"})
                    else:
                        self.logger.debug(u"Detected music folder {folder} is the same as the home folder; ignoring.".format(folder=music_dir))
                else:
                    self.logger.debug(u"Couldn't detect music folder; ignoring.")

                videos_dir = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_VIDEOS)
                if videos_dir:
                    if videos_dir != home_dir:
                        videos_dir = videos_dir.decode('utf-8')
                        self.logger.debug(u"Adding folder {folder} as videos...".format(folder=videos_dir))
                        f.write(u"media_dir=V,{media_dir}\n".format(media_dir=videos_dir))
                        self.minidlna_dirs.append({"path": videos_dir, "type": "video"})
                    else:
                        self.logger.debug(u"Detected videos folder {folder} is the same as the home folder; ignoring.".format(folder=videos_dir))
                else:
                    self.logger.debug(u"Couldn't detect videos folder; ignoring.")

        else:

            # Obtener los datos actuales del archivo de configuración
            self.logger.debug(u"Reading existing config file {config_file}...".format(config_file=MINIDLNA_CONFIG_FILE))
            with codecs.open(MINIDLNA_CONFIG_FILE, "a+", "utf-8") as fp:
                uuid_file = None
                friendly_name = None
                for line in fp:
                    line = line.strip()
                    if line.startswith("port="):
                        self.minidlna_port = int(re.sub(r'^port=', "", line))
                        self.logger.debug(u"Setting port to {port}...".format(port=self.minidlna_port))
                    elif line.startswith("log_dir="):
                        self.minidlna_logdir = re.sub(r'^log_dir=', "", line)
                        self.logger.debug(u"Setting log_dir to {log_dir}...".format(log_dir=self.minidlna_logdir))
                    elif line.startswith("uuid="):
                        uuid_file = re.sub(r'^uuid=', "", line)
                        self.logger.debug(u"Setting uuid to {uuid}...".format(uuid=uuid_file))
                    elif line.startswith("friendly_name="):
                        friendly_name = re.sub(r'^friendly_name=', "", line)
                        self.logger.debug(u"Setting friendly_name to {friendly_name}...".format(friendly_name=friendly_name))
                    elif line.startswith("media_dir="):
                        line = re.sub(r'^media_dir=', '', line)
                        if line.startswith("A,"):
                            line = re.sub(r'^A,', '', line)
                            self.logger.debug(u"Adding audio folder {folder}...".format(folder=line))
                            self.minidlna_dirs.append({"path": line, "type": "audio"})
                        elif line.startswith("P,"):
                            line = re.sub(r'^P,', '', line)
                            self.logger.debug(u"Adding pictures folder {folder}...".format(folder=line))
                            self.minidlna_dirs.append({"path": line, "type": "pictures"})
                        elif line.startswith("V,"):
                            line = re.sub(r'^V,', '', line)
                            self.logger.debug(u"Adding video folder {folder}...".format(folder=line))
                            self.minidlna_dirs.append({"path": line, "type": "video"})
                        elif line.startswith("PV,"):
                            line = re.sub(r'^PV,', '', line)
                            self.logger.debug(u"Adding pictures/video folder {folder}...".format(folder=line))
                            self.minidlna_dirs.append({"path": line, "type": "picturesvideo"})
                        else:
                            self.logger.debug(u"Adding mixed (no-type specified) folder {folder}...".format(folder=line))
                            self.minidlna_dirs.append({"path": line, "type": "mixed"})

                if not uuid_file or not friendly_name or not self.minidlna_port:
                    fp.write("\n")
                    if not uuid_file:
                        self.logger.info(u"No UUID specified in configuration file; generating one and saving to file...")
                        generated_uuid_file = str(uuid.uuid4())
                        self.logger.debug(u"UUID generated: {uuid}".format(uuid=generated_uuid_file))
                        fp.write(u"uuid={uuid}\n".format(uuid=generated_uuid_file))
                    if not friendly_name:
                        self.logger.info(u"No friendly_name specified in configuration file; generating one and saving to file...")
                        generated_friendly_name = _(u"Multimedia for {user}").format(user=getpass.getuser())
                        self.logger.debug(u"friendly_name generated: {friendly_name}".format(friendly_name=generated_friendly_name))
                        fp.write(u"friendly_name={friendly_name}\n".format(friendly_name=generated_friendly_name))
                    if not self.minidlna_port:
                        self.logger.info(u"No port specified in configuration file; generating one and saving to file...")
                        self.minidlna_port = 8200 + random.randint(1, 99)
                        self.logger.debug(u"Port generated: {port}".format(port=self.minidlna_port))
                        fp.write(u"port={port}\n".format(port=self.minidlna_port))


    def build_menu(self):

        self.menu = Gtk.Menu()

        if not self.minidlna_path:

            self.minidlna_not_installed_menuitem = Gtk.MenuItem(_(u"MiniDLNA is not installed"))
            self.minidlna_not_installed_menuitem.set_sensitive(False)
            self.menu.append(self.minidlna_not_installed_menuitem)

            self.install_minidlna_menuitem = Gtk.MenuItem(_(u"Install MiniDLNA"))
            self.install_minidlna_menuitem.connect('activate', self.install_minidlna_menuitem_activated)
            self.menu.append(self.install_minidlna_menuitem)

            self.minidlna_detect_menuitem = Gtk.MenuItem(_(u"Retry discovery"))
            self.minidlna_detect_menuitem.connect('activate', self.minidlna_detect_menuitem_activated)
            self.menu.append(self.minidlna_detect_menuitem)

        else:

            self.reload_configuration_menuitem = Gtk.MenuItem(_(u"Reload MiniDLNA configuration"))
            self.reload_configuration_menuitem.connect('activate', self.reload_configuration_menuitem_toggled)
            self.menu.append(self.reload_configuration_menuitem)

            self.start_menuitem = Gtk.MenuItem(_(u"Start MiniDLNA"))
            self.start_menuitem.connect('activate', lambda _: self.start_minidlna_process())
            self.menu.append(self.start_menuitem)

            self.start_reindex_menuitem = Gtk.MenuItem(_(u"Start and reindex MiniDLNA"))
            self.start_reindex_menuitem.connect('activate', lambda _: self.start_minidlna_process(True))
            self.menu.append(self.start_reindex_menuitem)

            self.restart_menuitem = Gtk.MenuItem(_(u"Restart MiniDLNA"))
            self.restart_menuitem.connect('activate', lambda _: self.restart_minidlna_process_nonblocking())
            self.menu.append(self.restart_menuitem)

            self.restart_reindex_menuitem = Gtk.MenuItem(_(u"Restart and reindex MiniDLNA"))
            self.restart_reindex_menuitem.connect('activate', lambda _: self.restart_minidlna_process_nonblocking(True))
            self.menu.append(self.restart_reindex_menuitem)

            self.stop_menuitem = Gtk.MenuItem(_(u"Stop MiniDLNA"))
            self.stop_menuitem.connect('activate', lambda _: self.stop_minidlna_process_nonblocking())
            self.menu.append(self.stop_menuitem)

            self.weblink_menuitem = Gtk.MenuItem(_(u"Web interface (port {port})").format(port=self.minidlna_port))
            self.weblink_menuitem.connect('activate', lambda _: self.run_xdg_open(_, "http://localhost:{port}".format(port=self.minidlna_port)))
            self.menu.append(self.weblink_menuitem)

            self.menu.append(Gtk.SeparatorMenuItem())

            if self.minidlna_dirs:

                mappings = {
                    "audio": {"display": _(u"Audio"), "icon": None},
                    "pictures": {"display": _(u"Pictures"), "icon": None},
                    "video": {"display": _("Video"), "icon": None},
                    "picturesvideo": {"display": _(u"Pictures/Video"), "icon": None},
                    "mixed": {"display": _(u"Mixed"), "icon": None},
                }

                for dir_data in self.minidlna_dirs:
                    sensitive =  os.path.exists(dir_data["path"]) and os.path.isdir(dir_data["path"]) and os.access(dir_data["path"], os.R_OK)
                    display_type = "[" + mappings.get(dir_data["type"])["display"] + "] "
                    dir_menuitem = Gtk.MenuItem(u"{display_type}{path}".format(display_type=display_type, path=dir_data["path"]))
                    dir_menuitem.connect('activate', self.run_xdg_open, dir_data["path"])
                    dir_menuitem.set_sensitive(sensitive)
                    self.menu.append(dir_menuitem)

            else:
                nodirs_menuitem = Gtk.MenuItem(_(u"No media folders specified; please, edit the configuration."))
                nodirs_menuitem.set_sensitive(False)
                self.menu.append(nodirs_menuitem)

            self.menu.append(Gtk.SeparatorMenuItem())

            self.showlog_menuitem = Gtk.MenuItem(_(u"Show MiniDLNA LOG"))
            self.showlog_menuitem.connect('activate', self.run_xdg_open, os.path.join(self.minidlna_logdir, "minidlna.log"))
            self.menu.append(self.showlog_menuitem)

            self.editconfig_menuitem = Gtk.MenuItem(_(u"Edit MiniDLNA configuration"))
            self.editconfig_menuitem.connect('activate', self.run_xdg_open, MINIDLNA_CONFIG_FILE)
            self.menu.append(self.editconfig_menuitem )

            self.menu.append(Gtk.SeparatorMenuItem())

            self.configuration_menu = Gtk.Menu()
            self.configuration_menuitem = Gtk.MenuItem(_(u"Indicator configuration"))
            self.configuration_menuitem.set_submenu(self.configuration_menu)
            self.menu.add(self.configuration_menuitem)

            self.indicator_startup_menuitem = Gtk.CheckMenuItem(_(u"Autostart indicator"))
            self.indicator_startup_menuitem.connect('activate', self.indicator_startup_menuitem_toggled)
            self.indicator_startup_menuitem.set_active(self.config.startup_indicator)
            self.configuration_menu.append(self.indicator_startup_menuitem)

            self.minidlna_startup_menuitem = Gtk.CheckMenuItem(_(u"Autostart MiniDLNA"))
            self.minidlna_startup_menuitem.connect('activate', self.minidlna_startup_menuitem_toggled)
            self.minidlna_startup_menuitem.set_active(self.config.startup_minidlna)
            self.configuration_menu.append(self.minidlna_startup_menuitem)

            self.minidlna_stop_on_exit_menuitem = Gtk.CheckMenuItem(_(u"Stop MiniDLNA when exit indicator"))
            self.minidlna_stop_on_exit_menuitem.connect('activate', self.minidlna_stop_on_exit_menuitem_toggled)
            self.minidlna_stop_on_exit_menuitem.set_active(self.config.stop_minidlna_exit_indicator)
            self.configuration_menu.append(self.minidlna_stop_on_exit_menuitem)

        self.menu.append(Gtk.SeparatorMenuItem())

        self.help_menu = Gtk.Menu()
        self.help_menuitem = Gtk.MenuItem(_(u"Help"))
        self.help_menuitem.set_submenu(self.help_menu)
        self.menu.add(self.help_menuitem)

        self.minidlna_help_menuitem = Gtk.MenuItem(_(u"MiniDLNA help"))
        self.minidlna_help_menuitem.connect('activate', self.run_xdg_open, "https://help.ubuntu.com/community/MiniDLNA")
        self.help_menu.add(self.minidlna_help_menuitem)

        self.minidlna_help_menuitem = Gtk.MenuItem(_(u"MiniDLNA Indicator help"))
        self.minidlna_help_menuitem.connect('activate', self.run_xdg_open, "https://github.com/okelet/minidlnaindicator")
        self.help_menu.add(self.minidlna_help_menuitem)

        self.item_quit = Gtk.MenuItem(_(u"Quit"))
        self.item_quit.connect('activate', self.quit)
        self.menu.append(self.item_quit)

        self.menu.show_all()
        self.indicator.set_menu(self.menu)


    def minidlna_detect_menuitem_activated(self, _):
        self.detect_minidlna()


    def install_minidlna_menuitem_activated(self, _):
        self.run_xdg_open(_, "apt://minidlna")


    def indicator_startup_menuitem_toggled(self, _):
        if self.indicator_startup_menuitem.get_active():
            self.config.startup_indicator = True
        else:
            self.config.startup_indicator = False
        self.set_gnome_autostart(self.config.startup_indicator)
        self.config.save()


    def set_gnome_autostart(self, enabled):
        if enabled:
            if not os.path.exists(GNOME_AUTOSTART_DIR):
                if os.path.exists(GNOME_CONFIG_DIR):
                    os.mkdir(GNOME_AUTOSTART_DIR)
            if os.path.exists(GNOME_AUTOSTART_DIR):
                with codecs.open(MINIDLNA_INDICATOR_GNOME_AUTOSTART_FILE, "w", "utf-8") as f:
                    f.write("[Desktop Entry]\n")
                    f.write("Encoding = UTF-8\n")
                    f.write("Type = Application\n")
                    f.write("Name = " + _(u"MiniDLNA Indicator") + "\n")
                    f.write("Exec = " + os.path.abspath(sys.argv[0]) + "\n")
                    f.write("Icon = " + MINIDLNA_ICON_GREEN + "\n")
                    f.write("Comment = " + _(u"Indicator for launching MiniDLNA as a normal user") + "\n")
                    f.write("X-GNOME-Autostart-enabled = true\n")
                    f.write("Terminal = false\n")
        else:
            if os.path.exists(MINIDLNA_INDICATOR_GNOME_AUTOSTART_FILE):
                os.remove(MINIDLNA_INDICATOR_GNOME_AUTOSTART_FILE)


    def reload_configuration_menuitem_toggled(self, _):
        self.detect_minidlna()


    def minidlna_startup_menuitem_toggled(self, _):
        if self.minidlna_startup_menuitem.get_active():
            self.config.startup_minidlna = True
        else:
            self.config.startup_minidlna = False
        self.config.save()


    def minidlna_stop_on_exit_menuitem_toggled(self, _):
        if self.minidlna_stop_on_exit_menuitem.get_active():
            self.config.stop_minidlna_exit_indicator = True
        else:
            self.config.stop_minidlna_exit_indicator = False
        self.config.save()


    def check_running_and_update_menu_status(self):
        """
        Checks if MiniDLNA is running and calls the method to update the menu items.
        :rtype: void
        """
        if self.minidlna_path:

            self.minidlna_running = self.get_minidlna_pid() != 0

            if self.minidlna_running:
                GLib.idle_add(lambda: self.indicator.set_icon_full(MINIDLNA_ICON_GREEN, ""))
            else:
                GLib.idle_add(lambda: self.indicator.set_icon_full(MINIDLNA_ICON_GREY, ""))

            GLib.idle_add(lambda: self.reload_configuration_menuitem.set_sensitive(not self.minidlna_running))
            GLib.idle_add(lambda: self.start_menuitem.set_sensitive(not self.minidlna_running))
            GLib.idle_add(lambda: self.start_reindex_menuitem.set_sensitive(not self.minidlna_running))
            GLib.idle_add(lambda: self.restart_menuitem.set_sensitive(self.minidlna_running))
            GLib.idle_add(lambda: self.restart_reindex_menuitem.set_sensitive(self.minidlna_running))
            GLib.idle_add(lambda: self.stop_menuitem.set_sensitive(self.minidlna_running))
            GLib.idle_add(lambda: self.weblink_menuitem.set_sensitive(self.minidlna_running))


    def get_minidlna_pid(self):
        """
        :return: Returns the PID of MiniDLAN if it is running; else 0.
        :rtype: int
        """
        minidlna_pid = 0

        # Read pid file
        if os.path.exists(MINIDLNA_PID_FILE):
            tmp_minidlna_pid = 0
            with open(MINIDLNA_PID_FILE) as myfile:
                data = myfile.read()
                if data:
                    tmp_minidlna_pid = int(data.strip())
            # if pid in file
            if tmp_minidlna_pid:
                self.logger.debug(u"Checking if MiniDLNA with PID {pid} is running...".format(pid=tmp_minidlna_pid))
                try:
                    os.kill(tmp_minidlna_pid, 0)
                    minidlna_pid = tmp_minidlna_pid
                except OSError as ex:
                    self.logger.warn(u"The MiniDLNA process with PID {pid} is not running.".format(pid=tmp_minidlna_pid))
                    self.logger.warn(u"Deleting the PID file with the incorrect PID...")
                    os.remove(MINIDLNA_PID_FILE)

        return minidlna_pid


    def start_minidlna_process(self, reindex=False):
        """

        :param reindex: Indicates if MiniDLNA must be started with the option "-R", that causes a full reinitialization of the database; useful when MiniDLNA has not detected the changes in the filesystem correctly.
        :type reindex: bool
        """

        if self.minidlna_path:

            current_pid = self.get_minidlna_pid()
            if not current_pid:
                command = "{minidlna_path} -f {minidlna_conf} -P {minidlna_pid}".format(minidlna_path=self.minidlna_path, minidlna_conf=MINIDLNA_CONFIG_FILE, minidlna_pid=MINIDLNA_PID_FILE)
                if reindex:
                    command += " -R"
                self.logger.debug(u"Running MiniDLNA: {command}...".format(command=command))

                comand_pid, returncode, std_out, std_err = run_command(command)
                if returncode == 0:
                    self.logger.debug(u"MiniDLNA launched successfully.")
                else:
                    self.logger.error(u"Error running MiniDLNA: {code} - {error}.".format(code=returncode, error=std_err))
            else:
                self.logger.debug(u"MiniDLNA is already running with PID {pid}".format(pid=current_pid))

            self.check_running_and_update_menu_status()


    def restart_minidlna_process_nonblocking(self, reindex=False):

        t = threading.Thread(target=self.restart_minidlna_process_blocking, kwargs={"reindex": reindex})
        t.start()


    def restart_minidlna_process_blocking(self, reindex=False):
        finished = self.stop_minidlna_process_blocking()
        if finished:
            self.start_minidlna_process(reindex)


    def stop_minidlna_process_nonblocking(self):

        t = threading.Thread(target=self.stop_minidlna_process_blocking)
        t.start()


    def stop_minidlna_process_blocking(self):

        finished = False
        if self.minidlna_path:

            # Disable the menus while stopping
            GLib.idle_add(lambda: self.reload_configuration_menuitem.set_sensitive(False))
            GLib.idle_add(lambda: self.start_menuitem.set_sensitive(False))
            GLib.idle_add(lambda: self.start_reindex_menuitem.set_sensitive(False))
            GLib.idle_add(lambda: self.restart_menuitem.set_sensitive(False))
            GLib.idle_add(lambda: self.restart_reindex_menuitem.set_sensitive(False))
            GLib.idle_add(lambda: self.stop_menuitem.set_sensitive(False))
            GLib.idle_add(lambda: self.weblink_menuitem.set_sensitive(False))

            minidlna_pid = self.get_minidlna_pid()
            if minidlna_pid:

                self.logger.debug(u"Stopping MiniDLNA with PID {pid}...".format(pid=minidlna_pid))
                try:
                    os.kill(minidlna_pid, 15)
                except OSError as ex:
                    self.logger.warn(u"Error stopping MiniDLNA: {error}".format(error=str(ex)))

                # Wait to the process to die
                finish_time = time.time() + 5
                while time.time() < finish_time:
                    if self.get_minidlna_pid() != minidlna_pid:
                        finished = True
                        break
                    else:
                        # Wait 500 ms
                        time.sleep(0.5)

                if not finished:
                    self.logger.warn(u"MiniDLNA has not finished after the kill signal in the allowed time.")
                    Notify.Notification.new(
                        _(u"MiniDLNA not stopped"),
                        _(u"MiniDLNA has not stopped in the allowed time; perhaps it is slow and will finish later."),
                        None
                    ).show()

            self.check_running_and_update_menu_status()

        return finished


    def run_xdg_open(self, src, uri):
        subprocess.call(["xdg-open", uri])


    def quit(self, source):
        # self.mounted_device_monitor.stop()
        self.background_minidlna_running_status_changes_stopevent.set()
        self.background_minidlna_running_status_changes_thread.join()
        if self.config.stop_minidlna_exit_indicator:
            self.stop_minidlna_process_blocking()
        Notify.uninit()
        self.mainloop.quit()


class MiniDLNAIndicatorConfig(object):

    def __init__(self, filename):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.filename = filename
        self.startup_indicator = True
        self.startup_minidlna = True
        self.stop_minidlna_exit_indicator = True
        self.load()

    def load(self):
        if os.path.exists(self.filename):
            with codecs.open(self.filename, "r", "utf-8") as f:
                data = yaml.load(f)
                self.startup_indicator = data.get("startup_indicator", False)
                self.startup_minidlna = data.get("startup_minidlna", False)
                self.stop_minidlna_exit_indicator = data.get("stop_minidlna_exit_indicator", True)
                self.logger.debug(u"Startup indicator: {value}".format(value=self.startup_indicator))
                self.logger.debug(u"Startup MiniDLNA: {value}".format(value=self.startup_minidlna))
                self.logger.debug(u"Stop MiniDLNA on exit indicator: {value}".format(value=self.stop_minidlna_exit_indicator))
        else:
            self.logger.info(u"Config file doesn't exist.")

    def save(self):
        data = {}
        data["startup_indicator"] = self.startup_indicator
        data["startup_minidlna"] = self.startup_minidlna
        data["stop_minidlna_exit_indicator"] = self.stop_minidlna_exit_indicator
        with codecs.open(self.filename, "w", "utf-8") as f:
            yaml.dump(data, f)


if __name__ == "__main__":

    if not os.path.exists(MINIDLNA_CONFIG_DIR):
        os.mkdir(MINIDLNA_CONFIG_DIR)

    script_name = os.path.splitext(os.path.basename(__file__))[0]
    current_date = datetime.now()
    default_timeout = 10

    log_filename = os.path.join(MINIDLNA_CONFIG_DIR, "indicator.log")

    parser = argparse.ArgumentParser()
    parser.add_argument('--stderr', action='store_true', help=_(u"Show also LOG messages in the error output."))
    parser.add_argument('--debug', action='store_true', help=_(u"Set LOG level to DEBUG"))
    args = parser.parse_args()

    logging_config = {
        'version': 1,
        'formatters': {
            'standard': {
                'format': '%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d %(name)s:%(funcName)s: %(message)s',
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'standard',
                'stream': 'ext://sys.stderr',
            },
            'file_rotate': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': log_filename,
                'maxBytes': 10 * 1024 * 1024,
                'backupCount': 5,
                'formatter': 'standard',
            }
        },
        'root': {
            'handlers': ['file_rotate'],
        },
    }

    if args.stderr:
        logging_config["root"]["handlers"].append('console')

    logging.config.dictConfig(logging_config)
    if args.debug:
        logging.getLogger(MiniDLNAIndicator.__name__).setLevel(logging.DEBUG)
        logging.getLogger(MiniDLNAIndicatorConfig.__name__).setLevel(logging.DEBUG)
        logging.getLogger(__name__).setLevel(logging.DEBUG)

    MiniDLNAIndicator()

