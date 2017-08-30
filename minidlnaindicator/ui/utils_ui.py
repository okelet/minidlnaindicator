
from typing import Optional, Tuple

import enum

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from ..constants import LOCALE_DIR, APPINDICATOR_ID

import gettext
_ = gettext.translation(APPINDICATOR_ID, LOCALE_DIR, fallback=True).gettext


ERROR_MESSAGE_OPTIONS = (Gtk.MessageType.ERROR, _("Error"))
INFO_MESSAGE_OPTIONS = (Gtk.MessageType.INFO, _("Information"))
WARNING_MESSAGE_OPTIONS = (Gtk.MessageType.WARNING, _("Warning"))
QUESTION_MESSAGE_OPTIONS = (Gtk.MessageType.QUESTION, _("Question"))

class MessageTypeEnum(enum.Enum):
    ERROR = ERROR_MESSAGE_OPTIONS
    INFO = INFO_MESSAGE_OPTIONS
    WARNING = WARNING_MESSAGE_OPTIONS
    QUESTION = QUESTION_MESSAGE_OPTIONS


def msgbox(message: str, parent: Optional[Gtk.Window]=None, title: Optional[str]=None, level: Optional[MessageTypeEnum]=None) -> None:
    if not level:
        level = MessageTypeEnum.QUESTION
    message_type, message_title = level.value
    if title:
        message_title = title
    dialog = Gtk.MessageDialog(parent, Gtk.DialogFlags.MODAL, message_type, Gtk.ButtonsType.OK, message_title)
    dialog.format_secondary_text(message)
    dialog.run()
    dialog.destroy()


def msgconfirm(message: str, parent: Optional[Gtk.Window]=None, title: Optional[str]=None, level: Optional[MessageTypeEnum]=None, default_response: int=Gtk.ResponseType.NO) -> int:
    if not level:
        level = MessageTypeEnum.WARNING
    message_type, message_title = level.value
    if title:
        message_title = title
    dialog = Gtk.MessageDialog(parent, Gtk.DialogFlags.MODAL, message_type, Gtk.ButtonsType.YES_NO, message_title)
    dialog.set_default_response(default_response)
    dialog.format_secondary_text(message)
    response = dialog.run()
    dialog.destroy()
    return response


def inputbox(message: str, parent: Optional[Gtk.Window]=None, title: Optional[str]=None, default: Optional[str]=None, password: Optional[bool]=False, show_on_taskbar: Optional[bool]=False, icon_file: Optional[str]=None, icon_name: Optional[str]=None) -> Tuple[int, Optional[str]]:

    if not title:
        title = _("Data input")
    dialog = Gtk.MessageDialog(parent, Gtk.DialogFlags.MODAL, Gtk.MessageType.QUESTION, Gtk.ButtonsType.OK_CANCEL, title)
    dialog.format_secondary_text(message)

    if icon_file:
        dialog.set_icon_from_file(icon_file)
    elif icon_name:
        dialog.set_icon_name(icon_name)

    if show_on_taskbar:
        dialog.set_skip_taskbar_hint(False)

    dialogBox = dialog.get_content_area()
    userEntry = Gtk.Entry()
    if password:
        userEntry.set_visibility(False)
        userEntry.set_invisible_char("*")
    if default:
        userEntry.set_text(default)
    userEntry.set_size_request(250, 0)
    # http://stackoverflow.com/questions/8290740/simple-versatile-and-re-usable-entry-dialog-sometimes-referred-to-as-input-dia
    userEntry.connect('activate', lambda ent, dlg, resp: dlg.response(resp), dialog, Gtk.ResponseType.OK)
    dialogBox.pack_end(userEntry, False, False, 0)

    dialog.show_all()
    response = dialog.run()
    text = userEntry.get_text()
    dialog.destroy()
    return response, text

