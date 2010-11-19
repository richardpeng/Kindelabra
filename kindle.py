#!/usr/bin/env python

import hashlib
import os
import re
import json

KINDLEROOT = '/mnt/us'
FILTER = ['pdf', 'mobi', 'prc', 'txt', 'tpz', 'azw', 'manga']
FOLDERS = ['documents', 'pictures']
#FOLDERS = ['documents']

class Collection(dict):
    '''Holds a single collection
    '''
    def has_hash(self, filehash):
        for item in self['items']:
            if not item.find(filehash) == -1:
                return True
        return False

class CollectionDB(dict):
    '''Holds a collection database
    '''
    def __init__(self, colfile):
        with open(colfile) as colfile:
            tmpjson = json.load(colfile)
            tmpdict = dict()
            for key in iter(tmpjson.keys()):
                split = key.rpartition('@')
                colname = unicode(split[0])
                tmpdict[colname] = Collection(tmpjson[key])
                tmpdict[colname]['locale'] = split[2]
            dict.__init__(self, tmpdict)

    # Converts the collection back to Kindle JSON format
    def toKindleDb(self):
        tmpjson = dict()
        for key in self:
            tmpkey = '@'.join([key, self[key]['locale']])
            tmpvalue = self[key].copy()
            del tmpvalue['locale']
            tmpjson[tmpkey] = tmpvalue
        return tmpjson

    # Returns a list of collection names containing a given filehash
    def search(self, filehash):
        cols = list()
        for collection in self:
            if self[collection].has_hash(filehash):
                cols.append(collection)
        return cols

    def in_collection(self, collection, filehash):
        if self[collection].has_hash(filehash):
            return True
        else:
            return False

    def add_filehash(self, collection, filehash):
        filehash = '*'+filehash
        self[collection]['items'].append(filehash)

class Kindle:
    '''Access a Kindle filesystem
    '''
    def __init__(self, root):
        self.root = root
        #self.files = dict()
        #self.init_data()

    def init_data(self):
        self.files = dict()
        self.filetree = dict()
        if self.is_connected():
            for folder in FOLDERS:
                self.load_folder(folder)
            #self.load_folder('documents')
            #self.load_folder('pictures')
            """for root, dirs, files in os.walk(os.path.join(self.root, 'documents')):
                for filename in files:
                    kindlepath = self.get_kindle_path(root, filename)
                    self.get_filenodes(self.filetree, re.sub(r'.*?(?=/(documents|pictures))', '', kindlepath).split('/')[1:])
                    filehash = self.get_hash(kindlepath)
                    self.files[filehash] = kindlepath"""
            """if os.path.exists(os.path.join(self.root, 'pictures')):
                for root, dirs, files in os.walk(os.path.join(self.root, 'pictures')):
                    for filename in files:
                        if os.path.splitext(filename)[1][1:] in FILTER:
                            kindlepath = self.get_kindle_path(root, filename)
                            print re.sub(r'.*?(?=/documents|pictures)', '', kindlepath)
                            self.get_filenodes(self.filetree, re.sub(r'.*?(?=/(documents|pictures))', '', kindlepath).split('/')[1:])
                            #self.get_filenodes(self.filetree, kindlepath.split('/'))
                            filehash = self.get_hash(kindlepath)
                            self.files[filehash] = kindlepath"""
            
            for path in self.files:
                regex = re.compile(r'.*?/(%s)' % '|'.join(FOLDERS))
                self.get_filenodes(self.filetree, re.sub(regex, r'\1', self.files[path]).split('/'))
            #print self.filetree.keys()

    def load_folder(self, path):
        for root, dirs, files in os.walk(os.path.join(self.root, path)):
            for filename in files:
                if os.path.splitext(filename)[1][1:] in FILTER:
                    kindlepath = self.get_kindle_path(root, filename)
                    filehash = self.get_hash(kindlepath)
                    self.files[filehash] = kindlepath
                    #print "Loaded:", filename

    # Adds files to the dictionary: tree
    def get_filenodes(self, tree, nodes):
        if len(nodes) > 1:
            if not nodes[0] in tree:
                tree[nodes[0]] = dict()
            self.get_filenodes(tree[nodes[0]], nodes[1:])
        elif len(nodes) == 1:
            if not 'files' in tree:
                tree['files'] = list()
            tree['files'].append(nodes[0])

    # Returns a full path on the kindle filesystem
    def get_kindle_path(self, folder, filename):
        return '/'.join([KINDLEROOT, re.sub(r'.*(documents|pictures)', r'\1', folder), filename]).replace('\\', '/')

    # Returns a SHA-1 hash
    def get_hash(self, path):
        return hashlib.sha1(path).hexdigest()

    # Checks if the specified folder is a Kindle filestructure
    def is_connected(self):
        docs = os.path.exists(os.path.join(self.root, 'documents'))
        sys = os.path.exists(os.path.join(self.root, 'system'))
        return docs and sys

    def searchTitle(self, title):
        matches = list()
        for filehash in self.files:
            if re.search(title, self.files[filehash], re.IGNORECASE):
                matches.append((filehash, self.files[filehash]))
        return matches
