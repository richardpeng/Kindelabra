#!/usr/bin/env python
#author:Richard Peng
#project:Kindelabra
#website:http://www.richardpeng.com/projects/kindelabra/
#repository:https://github.com/richardpeng/Kindelabra
#license:Creative Commons GNU GPL v2
# (http://creativecommons.org/licenses/GPL/2.0/)

import struct

import zipfile
import re

class Sectionizer:
    def __init__(self, filename, perm):
        self.f = file(filename, perm)
        header = self.f.read(78)
        self.ident = header[0x3C:0x3C+8]
        if self.ident != 'BOOKMOBI':
            raise ValueError('invalid file format')
        num_sections, = struct.unpack_from('>H', header, 76)
        sections = self.f.read(num_sections*8)
        self.sections = struct.unpack_from('>%dL' % (num_sections*2), sections, 0)[::2] + (0xfffffff, )

    def loadSection(self, section):
        before, after = self.sections[section:section+2]
        self.f.seek(before)
        return self.f.read(after - before)

class Mobi:
    def __init__(self, filename):
        try:
            sections = Sectionizer(filename, 'rb')
            header = sections.loadSection(0)
            len_mobi = struct.unpack_from('>L', header, 20)[0] + 16
            mobi_raw = header[:len_mobi]
            titleoffset, titlelen = struct.unpack_from('>LL', mobi_raw, 84)
            self.title = header[titleoffset:titleoffset+titlelen]
            len_exth, = struct.unpack_from('>L', header, len_mobi+4)
            exth_records = header[len_mobi:len_mobi+len_exth][12:]
            self.exth = dict()
            while len(exth_records) > 8:
                rectype, reclen = struct.unpack_from('>LL', exth_records)
                recdata = exth_records[8:reclen]
                self.exth[rectype] = recdata
                exth_records = exth_records[reclen:]
        except ValueError:
            self.title = None

'''Kindlet metadata parsing
'''
class Kindlet:
    def __init__(self, filename):
        # For official apps, ASIN is stored in the Amazon-ASIN field of META-INF/MANIFEST.MF, and title in the Implementation-Title field
        kindlet = zipfile.ZipFile( filename, 'r')
        kdkmanifest = kindlet.read( 'META-INF/MANIFEST.MF' )
        # Catch Title
        kdktitlem = re.search( '(^Implementation-Title: )(.*?$)', kdkmanifest, re.MULTILINE )
        if kdktitlem and kdktitlem.group(2):
            self.title = kdktitlem.group(2).strip()
        else:
            self.title = None
        # Catch ASIN
        kdkasinm = re.search( '(^Amazon-ASIN: )(.*?$)', kdkmanifest, re.MULTILINE )
        if kdkasinm and kdkasinm.group(2):
            self.asin = kdkasinm.group(2).strip()
        else:
            self.asin = None
        kindlet.close()

'''Topaz metadata parsing. Almost verbatim code by Greg Riker from Calibre
'''
class StreamSlicer(object):
    def __init__(self, stream, start=0, stop=None):
        self._stream = stream
        self.start = start
        if stop is None:
            stream.seek(0, 2)
            stop = stream.tell()
        self.stop = stop
        self._len = stop - start

    def __getitem__(self, key):
        stream = self._stream
        base = self.start
        if isinstance(key, (int, long)):
            stream.seek(base + key)
            return stream.read(1)
        if isinstance(key, slice):
            start, stop, stride = key.indices(self._len)
            if stride < 0:
                start, stop = stop, start
            size = stop - start
            if size <= 0:
                return ""
            stream.seek(base + start)
            data = stream.read(size)
            if stride != 1:
                data = data[::stride]
            return data
        raise TypeError("stream indices must be integers")

class Topaz(object):
    def __init__(self, filename):
        self.stream = open(filename, 'rb')
        self.data = StreamSlicer(self.stream)

        sig = self.data[:4]
        if not sig.startswith('TPZ'):
            raise ValueError("'%s': Not a Topaz file" % getattr(stream, 'name', 'Unnamed stream'))
        offset = 4

        self.header_records, consumed = self.decode_vwi(self.data[offset:offset+4])
        offset += consumed
        self.topaz_headers = self.get_headers(offset)

        # First integrity test - metadata header
        if not 'metadata' in self.topaz_headers:
            raise ValueError("'%s': Invalid Topaz format - no metadata record" % getattr(stream, 'name', 'Unnamed stream'))

        # Second integrity test - metadata body
        md_offset = self.topaz_headers['metadata']['blocks'][0]['offset']
        md_offset += self.base
        if self.data[md_offset+1:md_offset+9] != 'metadata':
            raise ValueError("'%s': Damaged metadata record" % getattr(stream, 'name', 'Unnamed stream'))

        # Get metadata, and store what we need
        self.title, self.asin, self.type = self.get_metadata()
        self.stream.close()

    def decode_vwi(self,bytes):
        pos, val = 0, 0
        done = False
        while pos < len(bytes) and not done:
            b = ord(bytes[pos])
            pos += 1
            if (b & 0x80) == 0:
                done = True
            b &= 0x7F
            val <<= 7
            val |= b
            if done: break
        return val, pos

    def get_headers(self, offset):
        # Build a dict of topaz_header records, list of order
        topaz_headers = {}
        for x in range(self.header_records):
            offset += 1
            taglen, consumed = self.decode_vwi(self.data[offset:offset+4])
            offset += consumed
            tag = self.data[offset:offset+taglen]
            offset += taglen
            num_vals, consumed = self.decode_vwi(self.data[offset:offset+4])
            offset += consumed
            blocks = {}
            for val in range(num_vals):
                hdr_offset, consumed = self.decode_vwi(self.data[offset:offset+4])
                offset += consumed
                len_uncomp, consumed = self.decode_vwi(self.data[offset:offset+4])
                offset += consumed
                len_comp, consumed = self.decode_vwi(self.data[offset:offset+4])
                offset += consumed
                blocks[val] = dict(offset=hdr_offset,len_uncomp=len_uncomp,len_comp=len_comp)
            topaz_headers[tag] = dict(blocks=blocks)
        self.eoth = self.data[offset]
        offset += 1
        self.base = offset
        return topaz_headers

    def get_metadata(self):
        ''' Return MetaInformation with title, author'''
        self.get_original_metadata()
        return self.metadata['Title'], self.metadata['ASIN'], self.metadata['CDEType']

    def get_original_metadata(self):
        offset = self.base + self.topaz_headers['metadata']['blocks'][0]['offset']
        self.md_header = {}
        taglen, consumed = self.decode_vwi(self.data[offset:offset+4])
        offset += consumed
        self.md_header['tag'] = self.data[offset:offset+taglen]
        offset += taglen
        self.md_header['flags'] = ord(self.data[offset])
        offset += 1
        self.md_header['num_recs'] = ord(self.data[offset])
        offset += 1

        self.metadata = {}
        for x in range(self.md_header['num_recs']):
            taglen, consumed = self.decode_vwi(self.data[offset:offset+4])
            offset += consumed
            tag = self.data[offset:offset+taglen]
            offset += taglen
            md_len, consumed = self.decode_vwi(self.data[offset:offset+4])
            offset += consumed
            metadata = self.data[offset:offset + md_len]
            offset += md_len
            self.metadata[tag] = metadata
