import json,re,csv,datetime,html
pins=[p for p in json.load(open("pins.json")) if p['link']]
ORDER=["mxxt_ghost_nightlight","lightup_ghost_duo","miyuki_crock","ooit_vases","aiosscd_fridge_mats","sarlai_sink","forest_gravity_cabinet","baiestwang_vanity"]
pins.sort(key=lambda p:ORDER.index(p['slug']))
TAGS={"mxxt_ghost_nightlight":"#halloweendecor #nightlight #spookyseason #cutehalloween #homedecor",
"lightup_ghost_duo":"#halloweendecor #ghostdecor #mantledecor #fallhome #spookyseason",
"miyuki_crock":"#kitchendecor #farmhousekitchen #utensilholder #countertopstyle #cozykitchen",
"ooit_vases":"#shelfstyling #vasedecor #farmhousedecor #homestyling #cottagehome",
"aiosscd_fridge_mats":"#fridgeorganization #kitchenorganization #organizedhome #cleaninghacks #kitchenhacks",
"sarlai_sink":"#farmhousesink #kitchenreno #kitchendesign #dreamkitchen #kitchenupgrade",
"forest_gravity_cabinet":"#cornerdecor #displaycabinet #livingroomdecor #homedecor #smallspaces",
"baiestwang_vanity":"#smallbathroom #floatingvanity #bathroomreno #bathroomdecor #budgethome"}
def clean(h): return html.unescape(re.sub(r'<[^>]+>','',h))
start=datetime.date(2026,10,3); rows=[]
for i,p in enumerate(pins):
    hook=clean(p['h1'])
    clause=p['sub'].split(" — ")[0].rstrip(".")
    cav=re.sub(r'^Worth knowing:\s*','',p['honest']); cav=cav[0].upper()+cav[1:]
    cap=f"{hook}.\n\n{clause}.\n\nWhy it works: {p['why']}\n\nHonest note: {cav}\n\n👉 Link in bio → \"Shop our picks\" for this one.\n\n#ad · I earn from qualifying Amazon purchases.\n\n{TAGS[p['slug']]} #inglenookvibes #budgethome"
    n=i+1
    rows.append(dict(day=n,date=(start+datetime.timedelta(days=i)).isoformat(),product=f"{p['brand']} – {p['name']}",
      slides=";".join(f"slides/{n:02d}_{p['slug']}_{j}.png" for j in range(1,6)),amazon_link=p['link'],caption=cap))
w=csv.DictWriter(open("schedule.csv","w",newline=""),fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
open("captions.md","w").write("# Inglenook Vibes – Instagram carousels\n\n"+"\n\n---\n\n".join(f"## Day {r['day']} · {r['date']} · {r['product']}\n\nSlides: `{r['slides']}`\n\nAmazon link (for link-in-bio page, not the caption): {r['amazon_link']}\n\n```\n{r['caption']}\n```" for r in rows))
print(rows[0]['caption'])
