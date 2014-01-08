# cddb.py
#
# Copyright (C) 2006 - Jon Oberheide <jon@oberheide.org>
# Copyright (C) 2006 - Fabien Carrion <fabien.carrion@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301  USA.

import string, operator, sys
import urllib, time
import rb

from gi.repository import Gio, Gtk, Gdk, GObject, Pango, Peas
from gi.repository import RB

class CddbPlugin(GObject.Object, Peas.Activatable):
    object = GObject.property (type = GObject.Object)

    def __init__(self):
        GObject.Object.__init__(self)

        for path in sys.path:
            try:
                self.gladefile = path + "/cddb.glade"
            except:
                pass
            else:
                break
        self.glade = Gtk.Builder()
        self.glade.add_from_file(self.gladefile)
        dic = { "on_album_view_cursor_changed" : self.album_cursor_changed,
                "apply_dialog" : self.apply_dialog,
                "hide_dialog" : self.hide_dialog }
        self.glade.connect_signals(dic)
        self.dialog = self.glade.get_object("dialog")

    def do_activate(self):
        data = dict()
        shell = self.object
        app = Gio.Application.get_default()

        data['action_group'] = Gio.SimpleAction.new("cddb-plugin-actions", None)
        data['action_group'].connect('activate', self.cddb)
        app.add_action(data['action_group'])

        data['ui_id'] = app.add_plugin_menu_item("tools",
                                 "cddb-plugin-actions",
                                 Gio.MenuItem.new(label=_("Cddb"),
                                                  detailed_action="app.cddb-plugin-actions"))


        self.cddb_name = "freedb.freedb.org"
        self.cddb_port = 80
        self.appname = "Rhythmbox"
        self.version = "0.10.1"

        self.albums = None
        self.disc = DiscInfos()

        # Configure search in the array on the first column
        treeview = self.glade.get_object('album-view')
        renderer = Gtk.CellRendererText()
        treeview.insert_column_with_attributes(-1, 'Artist / Album', renderer, text = 0)
        renderer = Gtk.CellRendererText()
        treeview.insert_column_with_attributes(-1, 'Category', renderer, text = 1)

        treeview = self.glade.get_object('tracks-view')
        renderer = Gtk.CellRendererText()
        treeview.insert_column_with_attributes(-1, '#', renderer, text = 0)
        treeview.insert_column_with_attributes(-1, 'Track Name', renderer, text = 1)
        treeview.insert_column_with_attributes(-1, 'Time', renderer, text = 2)

    def do_deactivate(self):
        shell = self.object

        app = shell.props.application
        app.remove_plugin_menu_item("tools", "cddb-plugin-actions")
        app.remove_action("cddb-plugin-actions")

        treeview = self.glade.get_object('album-view')
        model = Gtk.ListStore(str, str)
        treeview.set_model(model)
        treeview = self.glade.get_object('tracks-view')
        model = Gtk.ListStore(str, str, str)
        treeview.set_model(model)
        statusbar = self.glade.get_object('album-statusbar')
        statusbar.pop(0)

        self.albums = None
        self.disc = None

    def apply_dialog(self, *args):
        shell = self.object
        db = shell.props.db
        source = shell.props.library_source
        entryView = source.get_entry_view()
        entries = entryView.get_selected_entries()

        i = 0
        for entry in entries:
            db.entry_set(entry, RB.RhythmDBPropType.ARTIST, self.disc.disc[0])
            db.entry_set(entry, RB.RhythmDBPropType.ALBUM, self.disc.disc[1])
            db.entry_set(entry, RB.RhythmDBPropType.GENRE, self.disc.genre)
            db.entry_set(entry, RB.RhythmDBPropType.YEAR, int(self.disc.year))
            db.entry_set(entry, RB.RhythmDBPropType.TRACK_NUMBER, (i + 1))
            db.entry_set(entry, RB.RhythmDBPropType.TITLE, self.disc.trackname[i])
            i += 1
        db.commit()
        self.hide_dialog(args)
        return True

    def hide_dialog(self, *args):
        treeview = self.glade.get_object('album-view')
        model = Gtk.ListStore(str, str)
        treeview.set_model(model)
        treeview = self.glade.get_object('tracks-view')
        model = Gtk.ListStore(str, str, str)
        treeview.set_model(model)
        statusbar = self.glade.get_object('album-statusbar')
        statusbar.pop(0)

        self.albums = None
        self.disc = DiscInfos()
        self.dialog.hide()
        return True

    def cddb(self, action, parameter):
        shell = self.object
        source = shell.props.library_source
        entryView = source.get_entry_view()
        entries = entryView.get_selected_entries()
        total_frames = 150
        disc_length  = 2
        total_id = 0
        num_tracks = len(entries)
        query_string = ""

        self.disc.trackslength = []
        for entry in entries:
            secs = entry.get_ulong(RB.RhythmDBPropType.DURATION)
            self.disc.trackslength.append(time.strftime("%M:%S", time.gmtime(secs)))
            query_string = "%s+%d" % (
                    query_string,
                    total_frames )
            total_id += secs % 10
            total_frames += secs * 75
            disc_length += secs

        cddb_discid = "%08x" % ( ((total_id % 0xFF) << 24) | (disc_length << 8) | num_tracks )

        loader = rb.Loader()
        url = "http://%s:%d/~cddb/cddb.cgi?cmd=cddb+query+%s+%d+%s+%d&hello=noname+localhost+%s+%s&proto=6" % (
                urllib.parse.quote(self.cddb_name.encode('utf-8')),
                self.cddb_port,
                cddb_discid,
                num_tracks,
                query_string,
                disc_length,
                urllib.parse.quote(self.appname.encode('utf-8')),
                urllib.parse.quote(self.version.encode('utf-8')))

        self.dialog.show_all()
        self.dialog.grab_focus()

        print(url)
        loader.get_url(url, self.handle_albums_result)

    def handle_albums_result(self, data):
        treeview = self.glade.get_object('tracks-view')
        model = Gtk.ListStore(str, str, str)
        treeview.set_model(model)
        treeview = self.glade.get_object('album-view')
        model = Gtk.ListStore(str, str)
        treeview.set_model(model)

        if data is None:
            model.append(["Server did not respond.", ""])
            return

        lines = data.splitlines()
        if len(lines) < 3:
            model.append(["No album found.", ""])
            return

        lines.pop(0)
        lines.pop()

        self.albums = []
        for line in lines:
            tmp = str(line, encoding='utf8').split(" ", 2)
            self.albums.append(tmp[1])
            model.append([tmp[2], tmp[0]])

    def album_cursor_changed(self, treeview):
        treeview = self.glade.get_object('album-view')
        treeselection = treeview.get_selection()
        model, iter = treeselection.get_selected()

        if iter is None:
            return

        row = int(model.get_string_from_iter(iter))
        #row to color in red
        discid = self.albums[row]

        loader = rb.Loader()
        url = "http://%s:%d/~cddb/cddb.cgi?cmd=cddb+read+%s+%s&hello=noname+localhost+%s+%s&proto=6" % (
                urllib.parse.quote(self.cddb_name.encode('utf-8')),
                self.cddb_port,
                model.get_value(iter, 1),
                discid,
                urllib.parse.quote(self.appname.encode('utf-8')),
                urllib.parse.quote(self.version.encode('utf-8')))

        print(url)
        loader.get_url(url, self.handle_album_result)

    def handle_album_result(self, data):
        treeview = self.glade.get_object('tracks-view')
        model = Gtk.ListStore(str, str, str)
        treeview.set_model(model)
        statusbar = self.glade.get_object('album-statusbar')
        statusbar.pop(0)

        if data is None:
            model.append(["Server did not respond.", "", ""])
            return

        lines = str(data, encoding='utf8').splitlines()
        lines.pop(0)
        lines.pop()

        album = []
        i = 1
        for line in lines:
            if line[0] != "#":
                if line.startswith("DTITLE"):
                    tmp = line.replace("DTITLE=", "", 1)
                    self.disc.disc = tmp.split(" / ", 1)
                if line.startswith("TTITLE"):
                    tmp = line.split("=", 1)
                    model.append([str(i), str(tmp[1]), str(self.disc.trackslength[i - 1])])
                    self.disc.trackname.append(tmp[1])
                    i += 1
                if line.startswith("DYEAR="):
                    self.disc.year = line.replace("DYEAR=", "", 1)
                if line.startswith("DGENRE="):
                    self.disc.genre = line.replace("DGENRE=", "", 1)

        statusbar.push(0, "Title (" + self.disc.disc[1] + "), Artist (" + self.disc.disc[0] + "), Year (" + self.disc.year + "), genre (" + self.disc.genre + ")")

class DiscInfos:
    def __init__(self):
        self.trackslength = []
        self.trackname = []
        self.disc = []
        self.year = ''
        self.genre = ''
