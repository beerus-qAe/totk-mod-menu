"""Build a private item catalog from the player's extracted RomFS index.

Includes named actor packages and icon-backed inventory records from this install.
Output stays under build/. Presence does not establish successful item delivery.
"""
import argparse
import json
import struct
from pathlib import Path
from compression import zstd

from shader_census import sarc


PREFIXES = {
    'Weapon_Sword_': 'Armas', 'Weapon_Lsword_': 'Armas', 'Weapon_Spear_': 'Armas',
    'Weapon_Bow_': 'Arcos', 'Weapon_Shield_': 'Escudos', 'Armor_': 'Armaduras',
    'Item_': 'Materiais', 'Animal_Insect_': 'Materiais', 'SpObj_Capsule_': 'Dispositivos Zonai',
    'Obj_ArrowNormal_': 'Flechas', 'Obj_ArrowBundle_': 'Flechas',
}

EXTRA_ITEMS = {
    'ConfusionFruit':'Materiais','ElectricalFruit':'Materiais','SmokeFruit':'Materiais',
    'FireFruit':'Materiais','WaterFruit':'Materiais','BombFruit':'Materiais','IceFruit':'Materiais',
    'LightFruit':'Materiais','LightBall_Large':'Materiais','LightBall_Small':'Materiais',
    'BeeHome':'Materiais','FldObj_Pinecone_A_01':'Materiais','Obj_FireWoodBundle':'Materiais',
}

def extra_category(actor):
    if actor.startswith('Item_Cook_'):return 'Alimentos'
    if actor in EXTRA_ITEMS:return EXTRA_ITEMS[actor]
    if actor.startswith('SpObj_'):
        return 'Dispositivos Zonai' if '_Capsule_' in actor else 'Objetos Zonai'
    if actor.startswith('Energy_Material_'):return 'Energia Zonai'
    if actor.startswith(('PutRupee','MinusRupee')):return 'Moedas'
    if actor.startswith('Obj_SubstituteCloth_'):return 'Tecidos'
    if actor.startswith(('GameRomHorseSaddle_','GameRomHorseReins_')):return 'Equipamento de cavalo'
    return None


def messages(data):
    if data[:8] != b'MsgStdBn' or data[0x0c] != 1:
        raise ValueError('Expected UTF-16 MSBT')
    sections, pos = {}, 0x20
    for _ in range(struct.unpack_from('<H', data, 0x0e)[0]):
        size = struct.unpack_from('<I', data, pos + 4)[0]
        sections[data[pos:pos + 4]] = data[pos + 16:pos + 16 + size]
        pos = (pos + 16 + size + 15) & ~15
    labels, text = sections[b'LBL1'], sections[b'TXT2']
    offsets = struct.unpack_from('<' + str(struct.unpack_from('<I', text)[0]) + 'I', text, 4)
    result = {}
    for group in range(struct.unpack_from('<I', labels)[0]):
        count, at = struct.unpack_from('<II', labels, 4 + group * 8)
        for _ in range(count):
            length = labels[at]
            label = labels[at + 1:at + 1 + length].decode('utf-8')
            index = struct.unpack_from('<I', labels, at + 1 + length)[0]
            at += length + 5
            if not label.endswith('_Name'):
                continue
            p, chars = offsets[index], []
            while p + 2 <= len(text):
                unit = struct.unpack_from('<H', text, p)[0]
                p += 2
                if not unit:
                    break
                if unit == 0x0e:  # start tag: group, type, argument byte count, arguments
                    size = struct.unpack_from('<H', text, p + 4)[0]
                    p += 6 + size
                elif unit == 0x0f:  # end tag: group and type
                    p += 4
                else:
                    chars.append(chr(unit))
            result[label[:-5]] = ''.join(chars).replace('\t', ' ').replace('\n', ' ').strip()
    return result


def names_from_romfs(romfs, manifest, language):
    files = {e['path']: e for e in manifest['files']}
    with (romfs / 'romfs.bin').open('rb') as image:
        def read(path):
            entry = files[path]
            image.seek(entry['offset'])
            return image.read(entry['size'])
        dictionaries = {}
        for raw in sarc(zstd.decompress(read('Pack/ZsDic.pack.zs'))).values():
            dictionary = zstd.ZstdDict(raw)
            dictionaries[dictionary.dict_id] = dictionary
        archive = next(p for p in files if p.startswith(f'Mals/{language}.') and p.endswith('.sarc.zs'))
        raw = read(archive)
        dictionary = dictionaries.get(zstd.get_frame_info(raw).dictionary_id)
        result = {}
        for path, raw in sarc(zstd.decompress(raw, zstd_dict=dictionary)).items():
            if path.startswith('ActorMsg/') and path.endswith('.msbt'):
                result.update(messages(raw))
        return result


def catalog(manifest, names=None):
    names = names or {}
    names=dict(names)
    if 'NormalArrow' in names:
        names['Obj_ArrowNormal_A_01']=names['NormalArrow']
    rows = {}
    paths={entry['path'] for entry in manifest['files']}
    for entry in manifest['files']:
        path = entry['path']
        if not path.startswith('Pack/Actor/') or not path.endswith('.pack.zs'):
            continue
        actor = path.rsplit('/', 1)[1][:-8]
        category = extra_category(actor) or next((v for k, v in PREFIXES.items() if actor.startswith(k)), None)
        # Include remaining named/icon-backed inventory-like objects, excluding house modules.
        if not category and actor.startswith('Obj_') and not actor.startswith('Obj_LinkHouse_'):
            if actor in names and f'UI/Tex/Icon/{actor}.bntx.zs' in paths:category='Itens especiais'
        if category:
            # Only named actors are candidates when a message catalog is supplied.
            # Unnamed helper actors and actor variants are excluded.
            if names and actor not in names:
                continue
            display=names.get(actor,actor)
            if category=='Dispositivos Zonai':display+=' (cápsula)'
            rows[actor] = (category, actor, display)
    # Cooked dishes and several key inventory records have icons/messages but
    # no standalone actor pack. They are delivered through a chest, not spawned.
    for actor,display in names.items():
        if actor in rows or f'UI/Tex/Icon/{actor}.bntx.zs' not in paths:continue
        if actor.startswith('Item_Cook_'):rows[actor]=('Alimentos',actor,display)
        elif actor.startswith('Obj_') and not actor.startswith('Obj_LinkHouse_'):
            rows[actor]=('Itens especiais',actor,display)
    return [rows[k] for k in sorted(rows)]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--romfs', type=Path, required=True)
    ap.add_argument('--out', type=Path, default=Path('build/item-catalog/items.tsv'))
    ap.add_argument('--language', default='USpt')
    args = ap.parse_args()
    manifest = json.loads((args.romfs / 'index.json').read_text(encoding='utf-8'))
    names = names_from_romfs(args.romfs, manifest, args.language)
    if not names:
        raise ValueError('No actor names found; refusing an unnamed catalog')
    rows = catalog(manifest, names)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text('# category\tactor_id\tdisplay_name\n' +
                        ''.join('\t'.join(row) + '\n' for row in rows), encoding='utf-8')
    print(f'{len(rows)} actor candidates written to {args.out}')


if __name__ == '__main__':
    main()
