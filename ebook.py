#!/usr/bin/env python
#author:Richard Peng
#project:Kindelabra
#website:http://www.richardpeng.com/projects/kindelabra/
#repository:https://github.com/richardpeng/Kindelabra
#license:Creative Commons GNU GPL v2
# (http://creativecommons.org/licenses/GPL/2.0/)

import struct

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
        sections = Sectionizer(filename, 'rb')
        header = sections.loadSection(0)
        len_mobi = struct.unpack_from('>L', header, 20)[0] + 16
        mobi_raw = header[:len_mobi]
        titleoffset, titlelen = struct.unpack_from('>LL', mobi_raw, 84)
        self.title = header[titleoffset:titleoffset+titlelen]
        print ">>>",header
        len_exth, = struct.unpack_from('>L', header, len_mobi+4)
        exth_records = header[len_mobi:len_mobi+len_exth][12:]
        self.exth = dict()
        while len(exth_records) > 8:
            rectype, reclen = struct.unpack_from('>LL', exth_records)
            recdata = exth_records[8:reclen]
            self.exth[rectype] = recdata
            exth_records = exth_records[reclen:]

def main():
    m = Mobi('book.azw')
    if 113 in m.exth:
        print m.exth[113]

if __name__ == "__main__":
    main()
