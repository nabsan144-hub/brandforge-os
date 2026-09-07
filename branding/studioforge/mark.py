"""StudioForge mark — hand-built vector polygons, crisp at ANY size.
Block-forged S with anvil knockout + spark. Replaces AI raster everywhere."""
from PIL import Image, ImageDraw

GOLD=(232,181,74); BG=(7,13,17)

def draw_mark(size, bg=BG):
    S = 1000  # design grid
    img = Image.new('RGB', (S,S), bg)
    d = ImageDraw.Draw(img)
    ch = 70  # corner chamfer
    # top bar (chamfered outer top corners)
    d.polygon([(150+ch,80),(850-ch,80),(850,80+ch),(850,280),(150,280),(150,80+ch)], fill=GOLD)
    # left connector
    d.rectangle([150,80,350,600], fill=GOLD)
    # middle bar
    d.rectangle([150,400,850,600], fill=GOLD)
    # right connector
    d.rectangle([650,400,850,920], fill=GOLD)
    # bottom bar (chamfered outer bottom corners)
    d.polygon([(150,720),(850,720),(850,920-ch),(850-ch,920),(150+ch,920),(150,920-ch)], fill=GOLD)
    # anvil KNOCKOUT (bg color), contained in middle span between connectors
    d.polygon([(368,440),(632,440),(632,492),(560,492),(560,556),(600,556),(580,600),(420,600),(400,556),(440,556),(440,492),(368,492),(340,466)], fill=bg)
    # spark (4-point star) top-right
    cx,cy,r1,r2 = 905,105,72,20
    d.polygon([(cx,cy-r1),(cx+r2,cy-r2),(cx+r1,cy),(cx+r2,cy+r2),(cx,cy+r1),(cx-r2,cy+r2),(cx-r1,cy),(cx-r2,cy-r2)], fill=GOLD)
    return img.resize((size,size), Image.LANCZOS)

if __name__ == '__main__':
    for sz in (300,400,1024):
        draw_mark(sz).save(f'logo-{sz}.png')
    draw_mark(1024).save('logo-mark.png')
    print('vector mark exported')
