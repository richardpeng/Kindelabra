#!/usr/bin/env python
#author:Richard Peng
#project:Kindelabra
#website:http://www.richardpeng.com/projects/kindelabra/
#repository:https://github.com/richardpeng/Kindelabra
#license:Creative Commons GNU GPL v2
# (http://creativecommons.org/licenses/GPL/2.0/)

import os
import datetime
import json
import re

import gtk
import kindle

VERSION = '0.1'
FILTER = ['pdf', 'mobi', 'prc', 'txt', 'tpz', 'azw', 'manga']

class KindleUI:
    '''Interface for manipulating a Kindle collection JSON file
    '''
    def __init__(self):
        self.root = os.getcwd()
        self.filemodel = gtk.TreeStore(str, str)
        self.fileview = self.get_view('Files', self.filemodel, 'fileview')
        self.colmodel = gtk.TreeStore(str, str)
        self.colview = self.get_view('Collections', self.colmodel, 'colview')

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title("Kindelabra v%s" % VERSION)
        self.window.set_default_size(1000, 700)
        self.window.connect("destroy", gtk.main_quit)
        vbox_main = gtk.VBox()
        filechooserdiag = gtk.FileChooserDialog("Select your Kindle folder", self.window,
                                     gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER, 
                                    (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                                     gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
        filechooserdiag.set_current_folder(os.path.join(self.root, 'system'))
        self.filechooser = gtk.FileChooserButton(filechooserdiag)
        self.filechooser.connect("current-folder-changed", self.load)
        
        file_toolbar = gtk.HBox()
        file_toolbar.pack_start(self.filechooser, True, True, 2)
        file_toolbar.pack_start(self.get_button('gtk-refresh', 'Refresh files', self.refresh), False, True, 2)
        file_toolbar.pack_start(self.get_button('gtk-open', 'Open collection file', self.open_collection), False, True, 2)
        file_toolbar.pack_start(gtk.VSeparator(), False, True, 2)
        file_toolbar.pack_start(self.get_button('gtk-save', 'Save collection file', self.save), False, True, 2)
        
        hbox_main = gtk.HBox()
        filescroll = gtk.ScrolledWindow()
        filescroll.add(self.fileview)
        colscroll = gtk.ScrolledWindow()
        colscroll.add(self.colview)
        col_toolbar = gtk.VBox()
        col_toolbar.pack_start(self.get_button('gtk-new', 'Create new collection', self.add_collection), False, True, 2)
        col_toolbar.pack_start(self.get_button('gtk-edit', 'Rename collection', self.rename_collection), False, True, 2)
        col_toolbar.pack_start(self.get_button('gtk-remove', 'Delete collection', self.del_collection), False, True, 2)
        col_toolbar.pack_start(gtk.HSeparator(), False, True, 7)
        col_toolbar.pack_start(self.get_button('gtk-go-forward', 'Add book to collection', self.add_file), False, True, 2)
        col_toolbar.pack_start(self.get_button('gtk-go-back', 'Remove book from collection', self.del_file), False, True, 2)
        col_toolbar.pack_start(gtk.HSeparator(), False, True, 7)
        col_toolbar.pack_start(self.get_button('gtk-revert-to-saved', 'Revert collections', self.revert), False, True, 2)

        hbox_main.add(filescroll)
        hbox_main.pack_start(col_toolbar, False, False, 2)
        hbox_main.add(colscroll)
        
        self.statusbar = gtk.Statusbar()

        vbox_main.pack_start(file_toolbar, False)
        vbox_main.add(hbox_main)
        vbox_main.pack_start(self.statusbar, False)

        self.window.add(vbox_main)
        self.window.show_all()
        self.status("Select your Kindle's home folder")
        gtk.main()

    def get_button(self, image, tooltip, cb):
        button = gtk.Button()
        label = gtk.Image()
        label.set_from_stock(image, gtk.ICON_SIZE_LARGE_TOOLBAR)
        button.set_image(label)
        button.set_tooltip_text(tooltip)
        button.connect("clicked", cb)
        return button

    def status(self, message):
        self.statusbar.pop(1)
        self.statusbar.push(1, message)

    def load(self, widget):
        current = self.filechooser.get_current_folder()
        if not self.root == current:
            self.status("Loading... please wait")
            self.root = current
            self.kindle = kindle.Kindle(self.root)
            self.filemodel.clear()
            self.colmodel.clear()
            if self.kindle.is_connected():
                self.colfile = os.path.join(self.root, 'system', 'collections.json')
                self.db = kindle.CollectionDB(self.colfile)
                self.refresh(widget)
                self.revert(widget)
                self.status("Kindle Loaded")
            else:
                self.status("Kindle files not found")

    def get_collections(self, colmodel):
        for collection in self.db:
            citer = colmodel.append(None, [collection, ""])
            for namehash in self.db[collection]['items']:
                namehash = str(namehash.lstrip("*"))
                if namehash in self.kindle.files:
                    filename = os.path.basename(self.kindle.files[namehash])
                    fiter = colmodel.append(citer, [filename, namehash])

    def add_collection(self, widget):
        (dialog, input_box) = self.collection_prompt("Add Collection", "New Collection name:")
        dialog.show_all()
        colname = ""
        if dialog.run() == gtk.RESPONSE_ACCEPT:
            colname = unicode(input_box.get_text().strip())
        dialog.destroy()
        if colname == "":
            return
        if not colname in self.db:
            self.colmodel.append(None, [colname, ""])
            self.db[colname] = kindle.Collection({ 'locale': 'en-US', 'items': [], 'lastAccess': 0})
        else:
            self.status("%s collection already exists" % colname)

    def collection_prompt(self, title, label):
        labeltext = label
        label = gtk.Label(labeltext)
        col_input = gtk.Entry()
        col_input.set_activates_default(True)
        dialog = gtk.Dialog(title,
            self.window,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
            gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
        dialog.set_default_response(gtk.RESPONSE_ACCEPT)
        dialog.vbox.pack_start(label)
        dialog.vbox.pack_start(col_input)
        return (dialog, col_input)

    def del_collection(self, widget):
        (colstore, rows) = self.colview.get_selection().get_selected_rows()
        collections = list()
        for row in rows:
            if len(row) == 1:
                collections.append(gtk.TreeRowReference(colstore, row))
        for col in collections:
            collection = unicode(self.get_path_value(colstore, col)[0])
            dialog = self.del_collection_prompt(collection)
            if dialog.run() == gtk.RESPONSE_ACCEPT and collection in self.db:
                del self.db[collection]
                colstore.remove(colstore[col.get_path()].iter)
                self.status("Deleted collection %s" % collection)
            dialog.destroy()

    def del_collection_prompt(self, title):
        label = gtk.Label("Delete collection \"%s\"?" % title)
        dialog = gtk.Dialog("Delete collection",
                    self.window,
                    gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                    (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                    gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
        dialog.vbox.pack_start(label)
        dialog.show_all()
        return dialog

    def rename_collection(self, widget):
        (colstore, rows) = self.colview.get_selection().get_selected_rows()
        collections = list()
        for row in rows:
            if len(row) == 1:
                collections.append(gtk.TreeRowReference(colstore, row))
        if len(collections) == 1:
            colrow = colstore[collections[0].get_path()]
            colname = colrow[0]
            (dialog, input_box) = self.collection_prompt("Add Collection", "New Collection name:")
            input_box.set_text(colname)
            dialog.show_all()
            newname = ""
            if dialog.run() == gtk.RESPONSE_ACCEPT:
                newname = input_box.get_text().strip()
                if not newname == colname and colname in self.db:
                    colrow[0] = newname
                    self.db[newname] = self.db[colname]
                    del self.db[colname]
            else:
                self.statusbar.pop(1)
            dialog.destroy()
        elif len(collections) > 1:
            self.status("Select a single collection to rename")
        else:
            self.statusbar.pop(1)

    def get_path_value(self, model, row):
        if isinstance(row, gtk.TreeRowReference):
            path = row.get_path()
        elif isinstance(row, tuple):
            path = row
        else:
            return None
        piter = model[path].iter
        return model.get(piter, 0, 1)

    def get_hashes(self, filestore, filerows):
        filehashes = list()
        for row in filerows:
            gtkrow = gtk.TreeRowReference(filestore, row)
            filerow = self.get_path_value(filestore, gtkrow)
            if filerow[1] == "":
                piter = filestore.get_iter(gtkrow.get_path())
                citer = filestore.iter_children(piter)
                if citer:
                    subrow = filestore.get_path(citer)
                    subhashes = self.get_hashes(filestore, [subrow])
                    for subhash in subhashes:
                        filehashes.append(subhash)

                    niter = filestore.iter_next(citer)
                    while niter:
                        nextrow = filestore.get_path(niter)
                        subhashes = self.get_hashes(filestore, [nextrow])
                        for subhash in subhashes:
                            filehashes.append(subhash)
                        niter = filestore.iter_next(niter)
            else:
                filehashes.append((filerow[0], filerow[1]))
        return filehashes

    def add_file(self, widget):
        self.statusbar.pop(1)
        (filestore, filerows) = self.fileview.get_selection().get_selected_rows()
        (colstore, colrows) = self.colview.get_selection().get_selected_rows()
        
        colpaths = list()
        for row in colrows:
            if len(row) == 1:
                colpaths.append(row)
            else:
                parent = (row[0], )
                if not parent in colpaths:
                    colpaths.append(parent)
        targetcols = list()
        for path in colpaths:
            gtkrow = gtk.TreeRowReference(colstore, path)
            targetcols.append((path, self.get_path_value(colstore, gtkrow)[0]))
        if len(targetcols) == 0:
            self.status("Select a target collection to add")

        filehashes = self.get_hashes(filestore, filerows)
        for filename, filehash in filehashes:
            for colpath, colname in targetcols:
                colname = unicode(colname)
                if colname in self.db:
                    if not self.db.in_collection(colname, filehash):
                        colstore.append(colstore[colpath].iter, [filename, filehash])
                        self.db.add_filehash(colname, filehash)
                    else:
                        self.status("%s is already in collection %s" % (filename, colname))
                else:
                    self.status("No such collection:" + colname)
        self.colview.expand_all()

    def del_file(self, widget):
        self.statusbar.pop(1)
        (colstore, rows) = self.colview.get_selection().get_selected_rows()
        ref = list()
        for row in rows:
            if len(row) == 2:
                ref.append(gtk.TreeRowReference(colstore, row))
        for row in range(len(ref)):
            gtkrow = ref[row]
            path = gtkrow.get_path()
            (filename, filehash) = self.get_path_value(colstore, gtkrow)
            collection = unicode(self.get_path_value(colstore, (path[0], ))[0])
            jsonhash = '*' + filehash
            if self.db[collection].has_hash(filehash):
                self.db[collection]['items'].remove(jsonhash)
                colstore.remove(colstore[path].iter)
            else:
                self.status("File not in collection")
            
    def get_view(self, title, model, name):
        treeview = gtk.TreeView(model)
        treeview.set_name(name)
        tvcolumn = gtk.TreeViewColumn(title)
        treeview.append_column(tvcolumn)
        cell = gtk.CellRendererText()
        tvcolumn.pack_start(cell, True)
        tvcolumn.add_attribute(cell, 'text', 0)
        treeview.set_search_column(0)
        treeview.expand_all()
        treeview.set_rubber_banding(True)
        treeselection = treeview.get_selection()
        treeselection.set_mode(gtk.SELECTION_MULTIPLE)
        tvcolumn.set_sort_column_id(0)
        return treeview

    def revert(self, widget):
        self.db = kindle.CollectionDB(self.colfile)
        self.colmodel.clear()
        self.get_collections(self.colmodel)
        self.colview.expand_all()
        self.status("Kindle collections reloaded")

    def save(self, widget):
        now = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        backup = os.path.join(self.root, 'system', '%s-collections.json.backup' % (now))
        jsonfile = os.path.join(self.root, 'system', 'collections.json')
        if os.path.exists(jsonfile):
            os.rename(jsonfile, backup)
        with open(os.path.join(self.root, 'system', 'collections.json'), 'wb') as colfile:
            json.dump(self.db.toKindleDb(), colfile, separators=(',', ':'), ensure_ascii=True)
        self.status("Collections saved to Kindle, restart to load your new collections")

    def get_filenodes(self, tree, nodes):
        if len(nodes) > 1:
            if not nodes[0] in tree:
                tree[nodes[0]] = dict()
            self.get_filenodes(tree[nodes[0]], nodes[1:])
        elif len(nodes) == 1:
            if not 'files' in tree:
                tree['files'] = list()
            tree['files'].append(nodes[0])

    def get_files(self, filemodel, tree, piter=None, path=""):
        for node in tree:
            if node == 'files':
                for filename in tree['files']:
                    filehash = self.kindle.get_hash('/mnt/us' + '/'.join([path, filename]))
                    filemodel.append(piter, [filename, filehash])
            else:
                niter = filemodel.append(piter, [node, ""])
                self.get_files(filemodel, tree[node], niter, '/'.join([path,node]))

    def refresh(self, widget):
        self.kindle.init_data()
        self.filemodel.clear()
        self.get_files(self.filemodel, self.kindle.filetree)
        self.fileview.expand_all()
        self.status("File list refreshed")

    def open_collection(self, widget):
        dialog = gtk.FileChooserDialog("Open a collection", self.window,
                                     gtk.FILE_CHOOSER_ACTION_OPEN, 
                                    (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                                     gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
        dialog.set_current_folder(os.path.join(self.root, 'system'))
        dialog.show()
        if dialog.run() == gtk.RESPONSE_ACCEPT:
            filename = dialog.get_filename()
            self.colfile = filename
            self.db = kindle.CollectionDB(self.colfile)
            self.revert(widget)
        dialog.destroy()

if __name__ == "__main__":
    KindleUI()
