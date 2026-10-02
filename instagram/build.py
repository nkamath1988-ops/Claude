import json,os,re,asyncio,base64
from playwright.async_api import async_playwright
pins=[p for p in json.load(open("pins.json")) if p['link']]
ORDER=["mxxt_ghost_nightlight","lightup_ghost_duo","miyuki_crock","ooit_vases","aiosscd_fridge_mats","sarlai_sink","forest_gravity_cabinet","baiestwang_vanity"]
pins.sort(key=lambda p:ORDER.index(p['slug']))
FIX={"sarlai_sink":("33 White","33\" White")}
CSS="""
:root{--paper:#F1EEE7;--ink:#231F20;--soft:#5B5652;--rust:#9A3B2E;--sage:#5C6B4F;--line:rgba(35,31,32,.16)}
*{box-sizing:border-box}html,body{margin:0}
body{width:1080px;height:1350px;background:var(--paper);font-family:'Work Sans',sans-serif;color:var(--ink);position:relative;overflow:hidden}
h1,.serif{font-family:'Fraunces',serif;font-weight:500}
em{font-style:italic;color:var(--rust)}
.media{position:absolute;left:0;right:0;top:0;overflow:hidden;background:#fff}
.media img{width:100%;height:100%;display:block}
.badge{position:absolute;top:36px;left:36px;background:var(--rust);color:var(--paper);font-size:18px;font-weight:600;letter-spacing:.05em;padding:11px 22px;z-index:3;text-transform:uppercase}
.brand{position:absolute;top:36px;right:36px;z-index:3;font-family:'Fraunces',serif;font-size:26px;color:#fff;background:rgba(20,17,15,.6);padding:8px 18px}
.brand.dark{color:var(--ink);background:none}
.scrim{position:absolute;left:0;right:0;bottom:0;padding:170px 64px 44px;background:linear-gradient(0deg,rgba(20,17,15,.88),rgba(20,17,15,.55) 50%,rgba(20,17,15,0))}
.scrim .k{color:#E7DFD2;font-weight:600;font-size:21px;letter-spacing:.03em;margin-bottom:16px}
.scrim h1{color:#fff;font-size:68px;line-height:1.1;margin:0;letter-spacing:-.01em}
.scrim h1 em{color:#E9AE9B}
.lower{position:absolute;left:0;right:0;padding:0 72px}
.pg{position:absolute;bottom:44px;right:72px;font-size:20px;color:var(--soft);letter-spacing:.06em}
.foot{position:absolute;bottom:44px;left:72px;font-size:20px;color:var(--soft);font-family:'Fraunces',serif}
.tag{display:inline-block;background:var(--ink);color:var(--paper);font-size:19px;font-weight:600;letter-spacing:.07em;padding:10px 22px;text-transform:uppercase}
.tag.sage{background:var(--sage)}.tag.rust{background:var(--rust)}
.big{font-family:'Fraunces',serif;font-size:58px;line-height:1.3;margin:34px 0 0}
.mid{font-family:'Fraunces',serif;font-size:50px;line-height:1.38;margin:34px 0 0}
.swipe{font-size:22px;letter-spacing:.08em;color:var(--rust);font-weight:600;text-transform:uppercase}
.ad{font-size:19px;letter-spacing:.05em;color:var(--soft);text-transform:uppercase}
.btn{display:inline-block;background:var(--rust);color:var(--paper);font-size:30px;font-weight:600;padding:26px 44px}
"""
HEAD='<!doctype html><meta charset="utf-8"><link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,500;1,9..144,400;1,9..144,500&family=Work+Sans:wght@400;500;600&display=swap" rel="stylesheet"><style>'+CSS+'</style>'
def fit(p): return "object-fit:contain" if p['layout']=='white' else "object-fit:cover"
def slides(p,i):
    img="../"+p['img']; n=5
    name=p['name']; 
    if p['slug'] in FIX: name=name.replace(*FIX[p['slug']])
    bg="#fff" if p['layout']=='white' else "#222"
    out=[]
    # 1 cover
    if p['layout']=='full':
        cover=f'<div class="media" style="height:1090px"><div class="badge">{p["badge"]}</div><div class="brand">Inglenook Vibes</div><img src="{img}" style="object-fit:cover"><div class="scrim"><div class="k">{p["kicker"]}</div><h1>{p["h1"]}</h1></div></div>'
        low=f'<div class="lower" style="top:1130px"><p style="font-size:30px;line-height:1.45;color:var(--soft);margin:0">{p["sub"].split(" — ")[0].rstrip(".")}.</p></div>'
    else:
        cover=f'<div class="media" style="height:880px;background:#fff"><div class="badge">{p["badge"]}</div><div class="brand dark">Inglenook Vibes</div><img src="{img}" style="object-fit:contain;padding-top:60px"></div><div class="lower" style="top:915px"><div style="color:var(--sage);font-weight:600;font-size:21px;letter-spacing:.03em;margin-bottom:14px">{p["kicker"]}</div><h1 style="font-size:66px;line-height:1.08;margin:0;letter-spacing:-.01em">{p["h1"]}</h1></div>'
        low=''
    out.append(HEAD+f'<body>{cover}{low}<div class="foot swipe" style="font-family:Work Sans">Swipe →</div><div class="pg">#ad</div></body>')
    # 2-4 text slides with image band
    def band(pos):
        if p['layout']=='white': return f'<div class="media" style="height:560px"><img src="{img}" style="object-fit:contain;padding:14px"></div>'
        return f'<div class="media" style="height:560px"><img src="{img}" style="object-fit:cover;object-position:{pos}"></div>'
    for k,(tag,cls,text,sz,pos) in enumerate([("Why it works","",p['why'],'big',"50% 30%"),("Good to know","sage",p['good'],'mid',"50% 70%"),("Worth knowing","rust",re.sub(r'^Worth knowing:\s*','',p['honest']),'mid',"50% 50%")]):
        if k==2 and len(text)>200: sz='mid" style="font-size:43px'
        out.append(HEAD+f'<body>{band(pos)}<div class="lower" style="top:630px"><span class="tag {cls}">{tag}</span><p class="{sz}">{text[0].upper()+text[1:]}</p></div><div class="foot">Inglenook Vibes</div><div class="pg">{k+2} / {n}</div></body>')
    # 5 CTA
    out.append(HEAD+f'<body><div class="media" style="height:620px"><img src="{img}" style="{fit(p)}"></div><div class="lower" style="top:690px"><div class="serif" style="font-size:34px;color:var(--rust)">{p["brand"]}</div><p class="serif" style="font-size:40px;line-height:1.25;margin:10px 0 40px">{name}</p><div class="btn">Link in bio → Shop our picks</div><p class="ad" style="margin:40px 0 8px;color:var(--ink);font-weight:600">#ad · contains an affiliate link</p><p style="font-size:20px;line-height:1.45;color:var(--soft);margin:0">As an Amazon Associate, Inglenook Vibes earns from qualifying purchases.</p></div><div class="foot">Inglenook Vibes</div><div class="pg">5 / {n}</div></body>')
    return out
async def main():
    async with async_playwright() as pw:
        b=await pw.chromium.launch(executable_path='/opt/pw-browsers/chromium-1194/chrome-linux/chrome')
        pg=await b.new_page(viewport={'width':1080,'height':1350})
        for i,p in enumerate(pins,1):
            for j,h in enumerate(slides(p,i),1):
                f=f"build/{i:02d}_{p['slug']}_{j}.html"; open(f,'w').write(h)
                await pg.goto("file://"+os.path.abspath(f)); await pg.evaluate("document.fonts.ready"); await pg.wait_for_timeout(500)
                await pg.screenshot(path=f"slides/{i:02d}_{p['slug']}_{j}.png")
        await b.close()
asyncio.run(main())
