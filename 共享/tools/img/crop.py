from PIL import Image
import sys, os
d = r"D:\dsh工作区\电子实训\tools\img"
def crops(name, boxes, scale=4):
    im = Image.open(os.path.join(d, name + ".jpg"))
    print(name, im.size)
    w, h = im.size
    for i, (l, t, r, b) in enumerate(boxes):
        box = (int(l*w), int(t*h), int(r*w), int(b*h))
        c = im.crop(box)
        c = c.resize((c.width*scale, c.height*scale), Image.LANCZOS)
        out = os.path.join(d, f"{name}_c{i}.png")
        c.save(out)
        print(out, c.size)
# 正面：中部模块/SoC 区、右侧排针、底部接口、顶部接口
crops("front", [(0.35,0.35,0.75,0.75), (0.70,0.25,1.00,0.65), (0.40,0.70,0.85,1.00), (0.15,0.00,0.95,0.30)])
# 背面：丝印区、排针区
crops("back", [(0.50,0.20,1.00,0.50), (0.10,0.20,0.55,0.50), (0.60,0.45,1.00,0.80), (0.00,0.25,0.40,0.95)])
