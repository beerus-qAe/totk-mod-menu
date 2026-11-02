"""Read-only Player candidate discovery and movement recording on Windows.

Uses a private configuration made from the installed NSO. Candidate identity and
motion must be validated interactively; a finite vector alone is not proof.
"""
import argparse
import ctypes as c
import datetime
import json
import math
import os
import struct
import time
from pathlib import Path


def validate_actor(data, names, rodata):
    if len(data) < 0x2f0:
        return None
    vtable, = struct.unpack_from('<Q', data)
    name, = struct.unpack_from('<Q', data, 0x218)
    if name not in names or not rodata[0] <= vtable < rodata[1]:
        return None
    position = struct.unpack_from('<3f', data, 0x2b4)
    rotation = struct.unpack_from('<9f', data, 0x2c0)
    if not all(math.isfinite(x) and abs(x) < 100000 for x in position):
        return None
    if not all(math.isfinite(x) for x in rotation):
        return None
    if not all(.7 < sum(rotation[row*3+j]**2 for j in range(3)) < 1.3 for row in range(3)):
        return None
    return list(position)


class Memory:
    class Region(c.Structure):
        _fields_ = [('base',c.c_void_p),('allocation',c.c_void_p),('allocation_protect',c.c_ulong),
                    ('partition',c.c_ushort),('size',c.c_size_t),('state',c.c_ulong),
                    ('protect',c.c_ulong),('type',c.c_ulong)]

    def __init__(self, pid, executable):
        self.k = c.WinDLL('kernel32', use_last_error=True)
        self.k.OpenProcess.argtypes = [c.c_ulong,c.c_bool,c.c_ulong]
        self.k.OpenProcess.restype = c.c_void_p
        self.k.ReadProcessMemory.argtypes = [c.c_void_p,c.c_void_p,c.c_void_p,c.c_size_t,c.POINTER(c.c_size_t)]
        self.k.VirtualQueryEx.argtypes = [c.c_void_p,c.c_void_p,c.POINTER(self.Region),c.c_size_t]
        self.k.VirtualQueryEx.restype = c.c_size_t
        self.k.QueryFullProcessImageNameW.argtypes = [c.c_void_p,c.c_ulong,c.c_wchar_p,c.POINTER(c.c_ulong)]
        self.k.CloseHandle.argtypes = [c.c_void_p]
        self.k.GetExitCodeProcess.argtypes=[c.c_void_p,c.POINTER(c.c_ulong)]
        self.handle = self.k.OpenProcess(0x1010, False, pid)
        if not self.handle:
            raise OSError(c.get_last_error(), 'Cannot open diagnostic process for read-only access')
        path, size = c.create_unicode_buffer(32768), c.c_ulong(32768)
        if not self.k.QueryFullProcessImageNameW(self.handle, 0, path, c.byref(size)) or Path(path.value).resolve() != executable.resolve():
            self.close()
            raise ValueError('Process does not match the selected diagnostic executable')

    def close(self):
        if self.handle:
            self.k.CloseHandle(self.handle)
            self.handle = None

    def read(self, address, size):
        data, got = c.create_string_buffer(size), c.c_size_t()
        self.k.ReadProcessMemory(self.handle, c.c_void_p(address), data, size, c.byref(got))
        return data.raw[:got.value]

    def regions(self, low, high):
        address = low
        while address < high:
            region = self.Region()
            if not self.k.VirtualQueryEx(self.handle, c.c_void_p(address), c.byref(region), c.sizeof(region)):
                break
            end = int(region.base or 0) + region.size
            if end <= address:
                break
            if region.state == 0x1000 and not region.protect & (0x100|1):
                yield address, min(end, high)
            address = end


def discover(memory, config):
    import numpy as np
    names = {int(v,16) for v in config['names']}
    rodata = [int(v,16) for v in config['rodata']]
    found = set()
    regions = list(memory.regions(*[int(v,16) for v in config['heap']]))
    # Actor names may be interned/copied into the game heap instead of retaining
    # the NSO literal address. Find those exact strings before resolving owners.
    for lo, hi in regions:
        for start in range(lo, hi, 4*1024*1024):
            data = memory.read(start,min(4*1024*1024+7,hi-start))
            offset=0
            while (offset:=data.find(b'Player\0',offset))>=0:
                if offset==0 or data[offset-1]==0:
                    names.add(start+offset)
                offset+=1
                if len(names)>256:
                    raise ValueError('Too many Player strings; refusing an unbounded pointer scan')
    config['names'] = [hex(p) for p in sorted(names)]
    needles = np.asarray(sorted(names),dtype=np.uint64)
    high_words = np.asarray(sorted({p>>32 for p in names}),dtype=np.uint64)
    for lo, hi in regions:
        for start in range(lo, hi, 4*1024*1024):
            # Overlap handles an eight-byte pointer at a block boundary.
            data = memory.read(start, min(4*1024*1024+7,hi-start))
            words = np.frombuffer(data[:len(data)//8*8],dtype='<u8')
            slots = np.flatnonzero(np.isin(words>>32,high_words))
            slots = slots[np.isin(words[slots],needles)]
            for slot in slots:
                actor = start + int(slot)*8 - 0x218
                if validate_actor(memory.read(actor,0x300),names,rodata) is not None:
                    found.add(actor)
    return sorted(found)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pid',type=int,required=True)
    ap.add_argument('--exe',type=Path,required=True)
    ap.add_argument('--config',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--seconds',type=int,default=600)
    ap.add_argument('--publish',type=Path,help='Private diagnostic folder receiving a live identity hint')
    ap.add_argument('--status-only',action='store_true',help='Do not accumulate movement samples during beta play')
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1] / 'build'
    if not args.out.resolve().is_relative_to(root):
        ap.error('Private observations must stay under this checkout build/')
    if args.publish and not args.publish.resolve().is_relative_to(root):
        ap.error('Identity hints must stay under this checkout build/')
    config = json.loads(args.config.read_text())
    args.out.mkdir(parents=True,exist_ok=True)
    memory = Memory(args.pid,args.exe)
    deadline, scan_at, candidates = time.monotonic()+args.seconds, 0, []
    names, rodata = {int(v,16) for v in config['names']}, [int(v,16) for v in config['rodata']]
    try:
        with (args.out/'positions.jsonl').open('a',encoding='utf-8') as log:
            while (args.seconds==0 or time.monotonic()<deadline) and not (args.out/'stop').exists():
                exit_code=c.c_ulong()
                if not memory.k.GetExitCodeProcess(memory.handle,c.byref(exit_code)) or exit_code.value!=259:break
                if not candidates and time.monotonic()>=scan_at:
                    candidates=discover(memory,config)
                    names={int(v,16) for v in config['names']}
                    (args.out/'resolved-names.json').write_text(json.dumps(config['names']))
                    scan_at=time.monotonic()+10
                positions=[]
                valid=[]
                for actor in candidates:
                    position=validate_actor(memory.read(actor,0x300),names,rodata)
                    if position is not None:
                        positions.append({'actor':hex(actor),'position':position})
                        valid.append(actor)
                candidates=valid
                if args.publish and len(valid)==1:
                    actor=valid[0]
                    identity=memory.read(actor,0x220)
                    vtable=struct.unpack_from('<Q',identity)[0]
                    name=struct.unpack_from('<Q',identity,0x218)[0]
                    memory.k.GetTickCount64.restype=c.c_uint64
                    token=struct.pack('<6Q',0x504c415945523031,args.pid,memory.k.GetTickCount64(),actor,name,vtable)
                    temp=args.publish/'player-position.tmp'
                    temp.write_bytes(token)
                    try:
                        os.replace(temp,args.publish/'player-position.bin')
                    except PermissionError:
                        pass # The game may briefly hold the previous hint open; retry next sample.
                stage=(args.out/'stage.txt').read_text().strip() if (args.out/'stage.txt').exists() else 'waiting'
                row={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'stage':stage,'candidates':positions}
                if not args.status_only:
                    log.write(json.dumps(row)+'\n');log.flush()
                (args.out/'status.json').write_text(json.dumps(row,indent=2))
                time.sleep(.25)
    finally:
        memory.close()


if __name__=='__main__':
    main()
