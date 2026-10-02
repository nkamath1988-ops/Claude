import glob,subprocess,os
from PIL import Image,ImageDraw
PAPER=(241,238,231)
DUR=[3.0,4.5,4.0,5.0,4.5]; FADE=0.4; FPS=30
slugs=sorted({os.path.basename(f).rsplit('_',1)[0] for f in glob.glob("slides/*.png")})
for base in slugs:
    scenes=[]
    for j in range(1,6):
        s=Image.open(f"slides/{base}_{j}.png").convert("RGB")
        if j==1: ImageDraw.Draw(s).rectangle((50,1250,420,1330),fill=PAPER)   # remove "Swipe" cue
        else: ImageDraw.Draw(s).rectangle((780,1250,1040,1330),fill=PAPER)     # remove page numbers
        s=s.resize((972,1215),Image.LANCZOS)
        c=Image.new("RGB",(1080,1920),PAPER); c.paste(s,(54,200))
        p=f"frames/{base}_{j}.png"; c.save(p); scenes.append(p)
    ins=[];fl=[]
    for k,(p,d) in enumerate(zip(scenes,DUR)):
        n=int((d+FADE)*FPS)
        ins+=["-i",p]
        fl.append(f"[{k}:v]zoompan=z='1+0.0004*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s=1080x1920:fps={FPS},format=yuv420p[v{k}]")
    cur="v0";off=0
    for k in range(1,5):
        off+=DUR[k-1]
        fl.append(f"[{cur}][v{k}]xfade=transition=fade:duration={FADE}:offset={off:.2f}[x{k}]");cur=f"x{k}"
    total=sum(DUR)+FADE
    out=f"reels/{base}.mp4"
    cmd=["ffmpeg","-y","-loglevel","error",*ins,"-f","lavfi","-i",f"anullsrc=r=44100:cl=stereo","-filter_complex",";".join(fl),"-map",f"[{cur}]","-map",f"{len(scenes)}:a","-t",f"{total:.2f}","-c:v","libx264","-preset","medium","-crf","18","-r",str(FPS),"-pix_fmt","yuv420p","-c:a","aac","-shortest","-movflags","+faststart",out]
    subprocess.run(cmd,check=True); print(out)
