"""Decode real private BNTX icons and cache a small RGBA atlas for the menu.

Uses the official Arm astcenc executable supplied via --decoder; no game image is
stored outside ignored build/. Source files are read-only.
"""
import argparse,concurrent.futures,json,struct,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'build/icon-python-deps'))
from compression import zstd
from PIL import Image
from shader_census import sarc
from button_icons import gob_offset

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--romfs',type=Path,required=True)
    ap.add_argument('--decoder',type=Path,required=True)
    args=ap.parse_args()
    root=Path(__file__).resolve().parents[1]
    out=root/'build/icon-atlas';cache=out/'decoded';cache.mkdir(parents=True,exist_ok=True)
    files={r['path']:r for r in json.loads((args.romfs/'index.json').read_text())['files']}
    ids=[r.split('\t')[1] for r in (root/'build/item-catalog/items.tsv').read_text(encoding='utf-8').splitlines() if r and not r.startswith('#')]
    work=[];missing=[]
    with (args.romfs/'romfs.bin').open('rb') as source:
        def read(path):
            r=files[path];source.seek(r['offset']);return source.read(r['size'])
        dictionaries={}
        for data in sarc(zstd.decompress(read('Pack/ZsDic.pack.zs'))).values():
            d=zstd.ZstdDict(data);dictionaries[d.dict_id]=d
        for actor in ids:
            icon='NormalArrow' if actor=='Obj_ArrowNormal_A_01' else actor
            path=f'UI/Tex/Icon/{icon}.bntx.zs'
            if path not in files:missing.append(actor);continue
            png=cache/(icon+'.png')
            astc=cache/(icon+'.astc')
            if not png.exists():
                raw=read(path);data=zstd.decompress(raw,zstd_dict=dictionaries.get(zstd.get_frame_info(raw).dictionary_id))
                count,table=struct.unpack_from('<IQ',data,0x24)
                info=struct.unpack_from('<Q',data,table)[0]
                fmt=struct.unpack_from('<I',data,info+0x1c)[0]
                if fmt!=0x2d06:missing.append(actor);continue
                w,h=struct.unpack_from('<II',data,info+0x24)
                layout=struct.unpack_from('<I',data,info+0x34)[0]
                pointers=struct.unpack_from('<Q',data,info+0x70)[0]
                start=struct.unpack_from('<Q',data,pointers)[0]
                bx,by=(w+3)//4,(h+3)//4
                linear=bytearray(bx*by*16)
                for y in range(by):
                    for x in range(bx):
                        at=start+gob_offset(x*16,y,(bx*16+63)//64,1<<(layout&7))
                        block=data[at:at+16]
                        if len(block)!=16:raise ValueError('Truncated icon texture')
                        linear[(y*bx+x)*16:(y*bx+x+1)*16]=block
                header=struct.pack('<I',0x5ca1ab13)+bytes((4,4,1))+w.to_bytes(3,'little')+h.to_bytes(3,'little')+(1).to_bytes(3,'little')
                astc.write_bytes(header+linear)
            work.append((actor,astc,png))
    def decode(job):
        actor,astc,png=job
        if not png.exists():
            result=subprocess.run([str(args.decoder),'-ds',str(astc),str(png),'-silent','-j','1'],capture_output=True,text=True)
            if result.returncode:raise RuntimeError(actor+': '+result.stderr+result.stdout)
        with Image.open(png) as image:
            return actor,image.convert('RGBA').resize((48,48),Image.Resampling.LANCZOS)
    edge,cell=2048,52;columns=edge//cell
    if len(work)>columns**2:raise ValueError('Icon atlas capacity exceeded')
    atlas=Image.new('RGBA',(edge,edge));mapping=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for index,(actor,image) in enumerate(pool.map(decode,work)):
            atlas.paste(image,((index%columns)*cell+2,(index//columns)*cell+2))
            mapping.append(f'{actor}\t{index}\n')
            if (index+1)%200==0:print('Decoded',index+1,'icons',flush=True)
    (out/'item-icons.rgba').write_bytes(b'ITICONS1'+struct.pack('<4I',edge,cell,48,len(mapping))+atlas.tobytes())
    (out/'item-icons.tsv').write_text(''.join(mapping),encoding='utf-8')
    (out/'missing.json').write_text(json.dumps(missing,indent=2))
    atlas.save(out/'atlas-preview.png')
    preview=Image.new('RGBA',(384,96),(35,35,35,255))
    for i,(actor,astc,png) in enumerate(work[:8]):
        with Image.open(png) as image:preview.paste(image.convert('RGBA').resize((48,48)),(i*48,0),image.convert('RGBA').resize((48,48)))
    preview.save(out/'sample-preview.png')
    print('ICON_ATLAS_OK:',len(mapping),'real icons;',len(missing),'missing')

if __name__=='__main__':main()
