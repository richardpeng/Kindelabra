#!/usr/bin/env python
#author:Richard Peng
#project:Kindelabra
#website:http://www.richardpeng.com/projects/kindelabra/
#repository:https://github.com/richardpeng/Kindelabra
#license:Creative Commons GNU GPL v2
# (http://creativecommons.org/licenses/GPL/2.0/)

import hashlib
import os
import re
import json
import sys

import ebook

KINDLEROOT = '/mnt/us'
FILTER = ['pdf', 'mobi', 'prc', 'txt', 'tpz', 'azw', 'manga']
FOLDERS = ['documents', 'pictures']

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

    def in_collection(self, collection, filehash):
        if self[collection].has_hash(filehash):
            return True
        else:
            return False

    def add_filehash(self, collection, filehash):
        filehash = '*'+filehash
        self[collection]['items'].append(filehash)

    def add_asin(self, collection, asin, booktype):
        asin = "#%s^%s" % (asin, booktype)
        self[collection]['items'].append(asin)

class Ebook():
    def __init__(self, path):
        self.path = get_kindle_path(path)
        self.hash = get_hash(self.path)
        self.title = None
        self.meta = None
        self.asin = None
        self.type = None
        ext = os.path.splitext(path)[1][1:]
        if ext in ['mobi', 'azw', 'prc']:
            self.meta = ebook.Mobi(path)
            self.title = self.meta.title
            if 113 in self.meta.exth:
                self.asin = self.meta.exth[113]
            if 501 in self.meta.exth:
                self.type = self.meta.exth[501]
            if 503 in self.meta.exth:
                self.title = self.meta.exth[503]

class Kindle:
    '''Access a Kindle filesystem
    '''
    def __init__(self, root):
        self.root = unicode(root)

    def init_data(self):
        self.files = dict()
        self.filetree = dict()
        if self.is_connected():
            for folder in FOLDERS:
                self.load_folder(folder)
            
            for path in self.files:
                regex = re.compile(r'.*?/(%s)' % '|'.join(FOLDERS))
                self.get_filenodes(self.filetree, re.sub(regex, r'\1', self.files[path].path).split('/'))

    def load_folder(self, path):
        sys.stdout.write("Loading " + path)
        for root, dirs, files in os.walk(os.path.join(self.root, path)):
            for filename in files:
                if os.path.splitext(filename)[1][1:] in FILTER:
                    fullpath = os.path.abspath(os.path.join(root, filename))
                    book = Ebook(fullpath)
                    self.files[book.hash] = book
                    sys.stdout.write(".")
        sys.stdout.write("\n")

    def searchAsin(self, asin):
        '''Returns the Ebook with asin
        '''
        for filehash in self.files:
            if self.files[filehash].asin:
                return self.files[filehash]

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

    # Checks if the specified folder is a Kindle filestructure
    def is_connected(self):
        docs = os.path.exists(os.path.join(self.root, 'documents'))
        sys = os.path.exists(os.path.join(self.root, 'system'))
        return docs and sys

# Returns a full path on the kindle filesystem
def get_kindle_path(path):
    path = os.path.normpath(path)
    folder = os.path.dirname(path)
    filename = os.path.basename(path)
    return '/'.join([KINDLEROOT, re.sub(r'.*(documents|pictures)', r'\1', folder), filename]).replace('\\', '/')

# Returns a SHA-1 hash
def get_hash(path):
    path = unicode(path).encode('utf-8')
    return hashlib.sha1(path).hexdigest()

if __name__ == "__main__":
    k = Kindle("Kindle")
    k.init_data()
