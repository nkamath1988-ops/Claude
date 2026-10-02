import re,glob,base64,json,html,os
U="/root/.claude/uploads/bd281ea7-6e2f-5f84-8feb-7733fae3e9fb/"
out=[]
def txt(s): return html.unescape(re.sub(r'\s+',' ',re.sub(r'<[^>]+>','',s))).strip()
for f in sorted(glob.glob(U+"*pinterest_pin_*.html")):
    s=open(f).read()
    slug=re.search(r'pinterest_pin_(.+?)(?:-1)?\.html',f).group(1)
    m=re.search(r'data:image/(\w+);base64,([A-Za-z0-9+/=]+)',s)
    ext='jpg' if m.group(1)=='jpeg' else m.group(1)
    p=f"src/{slug}.{ext}"; open(p,'wb').write(base64.b64decode(m.group(2)))
    g=lambda pat:(re.search(pat,s,re.S) or [None,''])[1]
    d=dict(slug=slug,img=p,
      layout='full' if 'hero-full' in s else 'white',
      badge=txt(g(r'class="kicker-badge">(.*?)</div>')),
      kicker=txt(g(r'class="(?:scrim\s*"?>\s*<div class="kicker|kicker)">(.*?)</div>')),
      h1=html.unescape(re.sub(r'\s+',' ',g(r'<h1>(.*?)</h1>'))),
      sub=txt(g(r'class="sub">(.*?)</p>')),
      why=txt(g(r'class="mark">Why it works</div>\s*<p>(.*?)</p>')),
      good=txt(g(r'<strong>Good to know:</strong>(.*?)</div>')),
      honest=txt(g(r'class="honest">(.*?)</div>')),
      brand=txt(g(r'class="brand">(.*?)</span>')),
      name=txt(g(r'class="name"><span class="brand">.*?</span>(.*?)</div>')),
      link=g(r'class="cta" href="([^"]+)"'))
    out.append(d)
json.dump(out,open("pins.json","w"),indent=1)
for d in out: print(d['slug'],d['layout'],d['link'],d['kicker'][:40],'|',d['h1'])
