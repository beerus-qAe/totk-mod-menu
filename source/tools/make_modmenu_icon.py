"""Draw the original Mod Menu chest/plus icon and export Windows icon sizes.

The artwork is geometric, editable and contains no extracted game assets.
Requires Pillow, supplied by the private icon-tooling environment.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build/icon-python-deps'))
from PIL import Image, ImageDraw

SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
<title>TotK Mod Menu: chest and add symbol</title>
<rect x="16" y="16" width="480" height="480" rx="96" fill="#092e2c" stroke="#cba85e" stroke-width="8"/>
<path d="M80 226 L130 135 H359 L407 226 Z" fill="#f0ce80" stroke="#071f20" stroke-width="12" stroke-linejoin="round"/>
<path d="M116 212 L148 157 H340 L371 212 Z" fill="#153f38"/>
<rect x="76" y="240" width="331" height="145" rx="16" fill="#d5a44f" stroke="#071f20" stroke-width="12"/>
<path d="M102 261 H381 V363 H102 Z" fill="none" stroke="#f0ce80" stroke-width="10"/>
<path d="M151 247 V378 M332 247 V378" stroke="#8c6530" stroke-width="12"/>
<rect x="210" y="245" width="64" height="85" rx="12" fill="#092e2c" stroke="#f0ce80" stroke-width="8"/>
<path d="M242 271 V300" stroke="#f0ce80" stroke-width="13" stroke-linecap="round"/>
<path d="M194 87 L185 67 M245 78 V53 M295 87 L305 67" stroke="#74dcc0" stroke-width="9" stroke-linecap="round"/>
<circle cx="388" cy="379" r="84" fill="#11594c" stroke="#e5c987" stroke-width="10"/>
<path d="M388 338 V420 M347 379 H429" stroke="#a4f4ce" stroke-width="21" stroke-linecap="round"/>
</svg>'''


def main():
    out = ROOT / 'modmenu/assets'; out.mkdir(parents=True, exist_ok=True)
    scale = 4
    image = Image.new('RGBA', (512*scale, 512*scale))
    draw = ImageDraw.Draw(image)
    box = lambda values: tuple(int(v*scale) for v in values)
    def line(points, color, width):
        draw.line([box(p) for p in points], fill=color, width=width*scale, joint='curve')
        r = width*scale/2
        for x,y in (points[0], points[-1]):
            x,y=x*scale,y*scale;draw.ellipse((int(x-r),int(y-r),int(x+r),int(y+r)), fill=color)
    draw.rounded_rectangle(box((16,16,496,496)),radius=96*scale,fill='#092e2c',outline='#cba85e',width=8*scale)
    draw.polygon([box(p) for p in ((80,226),(130,135),(359,135),(407,226))],fill='#f0ce80')
    line([(80,226),(130,135),(359,135),(407,226),(80,226)],'#071f20',12)
    draw.polygon([box(p) for p in ((116,212),(148,157),(340,157),(371,212))],fill='#153f38')
    draw.rounded_rectangle(box((76,240,407,385)),radius=16*scale,fill='#d5a44f',outline='#071f20',width=12*scale)
    draw.rectangle(box((102,261,381,363)),outline='#f0ce80',width=10*scale)
    for x in (151,332):line([(x,247),(x,378)],'#8c6530',12)
    draw.rounded_rectangle(box((210,245,274,330)),radius=12*scale,fill='#092e2c',outline='#f0ce80',width=8*scale)
    line([(242,271),(242,300)],'#f0ce80',13)
    for points in ([(194,87),(185,67)],[(245,78),(245,53)],[(295,87),(305,67)]):line(points,'#74dcc0',9)
    draw.ellipse(box((304,295,472,463)),fill='#11594c',outline='#e5c987',width=10*scale)
    line([(388,338),(388,420)],'#a4f4ce',21);line([(347,379),(429,379)],'#a4f4ce',21)
    image=image.resize((512,512),Image.Resampling.LANCZOS)
    (out/'modmenu.svg').write_text(SVG,encoding='utf-8')
    image.save(out/'modmenu.png')
    image.save(out/'modmenu.ico',sizes=[(s,s) for s in (16,24,32,48,64,128,256)])
    print('MODMENU_ICON_OK:',out)


if __name__ == '__main__':
    main()
