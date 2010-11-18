#!/usr/bin/env python

import hashlib
import os
import re
import json

KINDLEROOT = '/mnt/us'

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
        #self.colfile = os.path.join(KINDLEROOT, 'system', 'collections.json')
        self.files = dict()
        for root, dirs, files in os.walk(os.path.join(self.root, 'documents')):
            for filename in files:
                kindlepath = self.get_kindle_path(root, filename)
                filehash = self.get_hash(kindlepath)
                self.files[filehash] = kindlepath
        for root, dirs, files in os.walk(os.path.join(self.root, 'pictures')):
            for filename in files:
                kindlepath = self.get_kindle_path(root, filename)
                filehash = self.get_hash(kindlepath)
                self.files[filehash] = kindlepath

    # Returns a full path on the kindle filesystem
    def get_kindle_path(self, folder, filename):
        return os.path.join(KINDLEROOT, re.sub(r'.*(documents|pictures)', r'\1', folder), filename)

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
