from PIL import Image, ImageDraw, ImageFont
import colorsys
F=[l for l in open('/tmp/claude-0/fonts.txt').read().split('\n') if l][0]
def hsl(h,s,l):
    r,g,b=colorsys.hls_to_rgb(h/360,l/100,s/100); return (round(r*255),round(g*255),round(b*255))
S=1024
im=Image.new('RGB',(S,S),hsl(208,52,34)); d=ImageDraw.Draw(im)
# 背景にうっすら山並み
d.polygon([(0,760),(230,560),(380,680),(600,430),(820,640),(1024,520),(1024,1024),(0,1024)],fill=hsl(208,46,28))
# しおり（栞）のリボン
x0,x1,y0,y1=322,702,150,860
d.rounded_rectangle([x0,y0,x1,y1-120],radius=36,fill=hsl(40,45,95))
d.polygon([(x0,y1-160),(x1,y1-160),(x1,y1),((x0+x1)//2,y1-110),(x0,y1)],fill=hsl(40,45,95))
f=ImageFont.truetype(F,300,index=0)
w=d.textlength('旅',font=f); d.text(((S-w)/2,250),'旅',font=f,fill=hsl(208,52,30))
# 赤丸シール
cx,cy,r=652,206,64
d.ellipse([cx-r,cy-r,cx+r,cy+r],fill=hsl(357,80,50))
d.ellipse([cx-r*.55,cy-r*.6,cx-r*.1,cy-r*.2],fill=hsl(5,95,72))
for n in (512,192,180):
    im.resize((n,n),Image.LANCZOS).save(f'/home/claude/archive/site/icon-{n}.png',optimize=True)
