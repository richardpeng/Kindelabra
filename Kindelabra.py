#!/usr/bin/env python

import kindle
import sys
import gtk
import os
import time
import datetime
import codecs
import json
import re

FILTER = ['pdf', 'mobi', 'prc', 'txt', 'tpz', 'azw', 'manga']

class KindleUI:
    '''Interface for manipulating a Kindle collection JSON file
    '''
    def __init__(self):
        dic = {
            "on_windowMain_destroy" : self.quit,
            "on_revert_clicked" : self.revert,
            "on_save_clicked" : self.save,
            "on_select_folder" : self.load,
            "on_refresh_clicked" : self.refresh,
            "on_add_collection_clicked" : self.add_collection,
            "on_del_collection_clicked" : self.del_collection,
            "on_add_file_clicked" : self.add_file,
            "on_del_file_clicked" : self.del_file,
            "on_open_clicked" : self.open_collection,
            "on_rename_clicked" : self.rename_collection,
        }
        gladefile = "kindle.glade"
        self.wTree = gtk.Builder()
        self.wTree.add_from_file(gladefile)
        self.window = self.wTree.get_object("window")
        if self.window:
            self.window.connect("destroy", gtk.main_quit)
        self.wTree.connect_signals(dic)
        self.window.show()
        self.filemodel = gtk.TreeStore(str, str)
        container = self.wTree.get_object('filescroll')
        if not container.get_child():
            container.add(self.get_view('Files', self.filemodel, 'fileview'))
            container.show_all()
        self.colmodel = gtk.TreeStore(str, str)
        container = self.wTree.get_object('colscroll')
        if not container.get_child():
            container.add(self.get_view('Collections', self.colmodel, 'colview'))
            container.show_all()
        self.root = os.getcwd()
        self.status("Select your Kindle's home folder")
        gtk.main()

    def status(self, message):
        sbar = self.wTree.get_object('statusbar')
        sbar.pop(1)
        sbar.push(1, message)

    def load(self, widget):
        current = self.wTree.get_object('folderchooser').get_current_folder()
        if not self.root == current:
            #print "loading"
            self.status("Loading... please wait")
            self.root = current
            #print "make kindle object"
            self.kindle = kindle.Kindle(self.root)
            #print "done"
            self.filemodel.clear()
            self.colmodel.clear()
            if self.kindle.is_connected():
                #print "loading db"
                self.colfile = os.path.join(self.root, 'system', 'collections.json')
                self.db = kindle.CollectionDB(self.colfile)
                #print "refreshing"
                self.refresh(widget)
                #print "reverting"
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
            colname = input_box.get_text().strip()
        dialog.destroy()
        if not colname == "":
            treeview = self.wTree.get_object('colscroll').get_child()
            model = treeview.get_model()
            model.append(None, [colname, ""])
            self.db[colname] = kindle.Collection({ 'locale': 'en-US', 'items': [], 'lastAccess': 0})

    def collection_prompt(self, title, label):
        labeltext = label
        label = gtk.Label(labeltext)
        col_input = gtk.Entry()
        dialog = gtk.Dialog(title,
            self.window,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
            gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
        dialog.vbox.pack_start(label)
        dialog.vbox.pack_start(col_input)
        return (dialog, col_input)

    def del_collection(self, widget):
        (colstore, rows) = self.wTree.get_object('colscroll').get_child().get_selection().get_selected_rows()
        collections = list()
        for row in rows:
            if len(row) == 1:
                collections.append(gtk.TreeRowReference(colstore, row))
        for col in collections:
            collection = unicode(self.get_path_value(colstore, col)[0])
            if collection in self.db:
                del self.db[collection]
                colstore.remove(colstore[col.get_path()].iter)
                self.status("Deleted collection %s" % collection)
            else:
                self.status("Collection not in database" + collection)

    def rename_collection(self, widget):
        (colstore, rows) = self.wTree.get_object('colscroll').get_child().get_selection().get_selected_rows()
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
                self.status('')
            dialog.destroy()
        elif len(collections) > 1:
            self.status("Select a single collection to rename")
        else:
            self.status('')

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
        self.status('')
        (filestore, filerows) = self.wTree.get_object('filescroll').get_child().get_selection().get_selected_rows()
        (colstore, colrows) = self.wTree.get_object('colscroll').get_child().get_selection().get_selected_rows()
        
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
        self.wTree.get_object('colscroll').get_child().expand_all()

    def del_file(self, widget):
        self.status('')
        (colstore, rows) = self.wTree.get_object('colscroll').get_child().get_selection().get_selected_rows()
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
        treeview = self.wTree.get_object('colscroll').get_child()
        colmodel = treeview.get_model()
        colmodel.clear()
        self.get_collections(colmodel)
        treeview.expand_all()
        self.status("Kindle collections reloaded")

    def save(self, widget):
        now = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        backup = os.path.join(self.root, 'system', '%s-collections.json.backup' % (now))
        jsonfile = os.path.join(self.root, 'system', 'collections.json')
        if os.path.exists(jsonfile):
            os.rename(jsonfile, backup)
        with open(os.path.join(self.root, 'system', 'collections.json'), 'wb') as colfile:
            json.dump(self.db.toKindleDb(), colfile, separators=(',', ':'), ensure_ascii=True)
        self.status("Collections saved to Kindle")

    def get_filenodes(self, tree, nodes):
        if len(nodes) > 1:
            if not nodes[0] in tree:
                tree[nodes[0]] = dict()
            self.get_filenodes(tree[nodes[0]], nodes[1:])
        elif len(nodes) == 1:
            if not 'files' in tree:
                tree['files'] = list()
            tree['files'].append(nodes[0])

    def get_nodes(self, tree, nodes):
        for node in tree:
            print node
        #if 'files' in tree:
            #for filename in tree['files']:
                #pass

    def get_files(self, filemodel, tree, piter=None, path=""):
        for node in tree:
            if node == 'files':
                for filename in tree['files']:
                    filehash = self.kindle.get_hash('/mnt/us' + '/'.join([path, filename]))
                    filemodel.append(piter, [filename, filehash])
            else:
                #print node
                niter = filemodel.append(piter, [node, ""])
                #print "do something", niter
                #print node
                #print tree[node].keys()
                self.get_files(filemodel, tree[node], niter, '/'.join([path,node]))
                #print node
                #print tree[node].keys()
                #piter = filemodel.append(piter, [node, ""])
                #for cnode in tree[node]:
                    #if not cnode == 'files':
                        #print "add subnode", cnode
                        #citer = filemodel.append(piter, [cnode, ""])
                        #print tree[node][cnode]
                        #self.get_files(filemodel, tree[node][cnode], citer)
                #print
        #print self.kindle.filetree
        #get files from kindle object
        #filetree = dict()
        #for filehash in self.kindle.files:
            #filesplit = re.sub(r'.*?(documents|pictures)/', '', self.kindle.files[filehash]).split('/')
            #for part in filesplit:
                
                #print part, filesplit.index(part) == len(filesplit)-1
        """roots = dict()
        for root, dirs, files in os.walk(os.path.join(self.root, 'documents')):
            for subdir in dirs:
                roots[os.path.join(root, subdir)] = filemodel.append(roots.get(root, None), [subdir, ""])
            for filename in files:
                if os.path.splitext(filename)[1][1:] in FILTER:
                    kindlepath = self.kindle.get_kindle_path(root, filename)
                    kindlehash = self.kindle.get_hash(kindlepath)
                    filemodel.append(roots.get(root, None), [filename, kindlehash])
        if os.path.exists(os.path.join(self.root, 'pictures')):
            for root, dirs, files in os.walk(os.path.join(self.root, 'pictures')):
                for subdir in dirs:
                    roots[os.path.join(root, subdir)] = filemodel.append(roots.get(root, None), [subdir, ""])
                for filename in files:
                    if os.path.splitext(filename)[1][1:] in FILTER:
                        kindlepath = self.kindle.get_kindle_path(root, filename)
                        kindlehash = self.kindle.get_hash(kindlepath)
                        filemodel.append(roots.get(root, None), [filename, kindlehash])
        return roots"""

    def refresh(self, widget):
        self.kindle.init_data()
        treeview = self.wTree.get_object('filescroll').get_child()
        filemodel = treeview.get_model()
        filemodel.clear()
        self.get_files(filemodel, self.kindle.filetree)
        treeview.expand_all()
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

    def quit(self):
        sys.exit(0)

KindleUI()
