"""Build the bundled photo library from licensed Wikimedia Commons photographs.

Network is used only while curating, never during presentation generation.
"""
import concurrent.futures
import hashlib
import html
import io
import json
import re
import time
from pathlib import Path

import httpx
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
# Search results require visual/semantic review before copying to the bundled library.
DEST = ROOT/'storage/photo-curation'
TOPICS = [
 ('forest','森林生态',['forest trees photography','forest road woodland'],['森林','生态','保护','生物多样性','可持续','forest','ecology']),
 ('water','水与海洋',['wetland lake landscape','ocean coastline aerial'],['湿地','水','海洋','河流','海岸','water','ocean','wetland']),
 ('mountain','山川景观',['mountain landscape photography','desert landscape photography'],['山','地理','旅行','自然','mountain','landscape']),
 ('energy','绿色能源',['wind turbines landscape','solar panels field'],['能源','风电','光伏','低碳','电力','energy','solar']),
 ('city','城市空间',['city skyline buildings photograph','urban architecture modern'],['城市','建筑','规划','空间','地产','city','architecture']),
 ('business','办公与协作',['office workspace photograph','conference meeting room interior'],['办公','协作','商业','团队','工作','business','office']),
 ('education','学习与知识',['library books reading room','university lecture classroom'],['教育','学习','课堂','培训','研究','education','library']),
 ('technology','技术与计算',['computer circuit board photograph','server datacenter photograph'],['计算机','技术','芯片','人工智能','数字','technology','computer']),
 ('industry','工业与制造',['factory machinery photograph','industrial robot manufacturing'],['制造','工业','生产','机器人','industry','manufacturing']),
 ('science','科学与探索',['laboratory microscope photograph','telescope observatory photograph'],['实验','科学','医疗','探索','science','laboratory']),
 ('transport','交通与物流',['container ship port aerial','railway train landscape'],['交通','运输','物流','供应链','transport','logistics']),
 ('agriculture','农业与食物',['agricultural crop field aerial','wheat field agriculture'],['农业','粮食','乡村','农田','食物','agriculture','food']),
]
UA={'User-Agent':'Folio-photo-curation/0.1 (https://lightsmile.ink)'}

def clean(value):
 return html.unescape(re.sub('<[^>]*>','',value or '')).strip()

def candidates(topic):
 key,label,queries,tags=topic; results=[]
 for query in queries:
  params=dict(action='query',format='json',generator='search',gsrnamespace=6,gsrsearch=query+' filetype:bitmap',gsrlimit=40,prop='imageinfo',iiprop='url|size|extmetadata',iiurlwidth=1280)
  response=httpx.get('https://commons.wikimedia.org/w/api.php',params=params,headers=UA,timeout=40); response.raise_for_status()
  for page in sorted(response.json().get('query',{}).get('pages',{}).values(),key=lambda p:p.get('index',9999)):
   info=page.get('imageinfo',[{}])[0]; metadata=info.get('extmetadata',{})
   license=clean(metadata.get('LicenseShortName',{}).get('value'))
   title=page['title']
   if license not in {'Public domain','CC0','CC BY 4.0','CC BY 3.0','CC BY 2.0','CC BY-SA 4.0','CC BY-SA 3.0','CC BY-SA 2.0'}: continue
   if any(word in title.lower() for word in ['painting','engraving','oil on','canvas','diagram','drawing','map of','portrait','logo','poster','museum','archive','1920','1930','1940','1950','1941','1942','1943','smn.']): continue
   width,height=info.get('width',0),info.get('height',0)
   if width<900 or height<550 or not .8<width/max(1,height)<2.6: continue
   results.append(dict(category=key,category_name=label,tags=tags,title=title.removeprefix('File:'),author=clean(metadata.get('Artist',{}).get('value')),license=license,license_url=metadata.get('LicenseUrl',{}).get('value','https://creativecommons.org/publicdomain/mark/1.0/'),source_url=info['descriptionurl'],download_url=info.get('thumburl') or info['url']))
 return sorted(results,key=lambda item: (item['license']=='Public domain',item['title'].lower().count('black')))

def main():
 DEST.mkdir(parents=True,exist_ok=True)
 pools={}
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
  jobs={executor.submit(candidates,topic):topic for topic in TOPICS}
  for job in concurrent.futures.as_completed(jobs):
   topic=jobs[job]; pools[topic[0]]=job.result(); print(topic[0],len(pools[topic[0]]),'licensed candidates',flush=True)
 manifest=[]; seen=set(); hashes=set()
 for key,label,_,tags in TOPICS:
  taken=0
  for candidate in pools[key]:
   if candidate['source_url'] in seen: continue
   try:
    response=httpx.get(candidate['download_url'],headers=UA,timeout=40,follow_redirects=True); response.raise_for_status()
    if len(response.content)>12*1024*1024: continue
    with Image.open(io.BytesIO(response.content)) as source:
     source.load(); image=ImageOps.exif_transpose(source).convert('RGB'); image.thumbnail((1280,960))
     if image.width<600 or image.height<400: continue
     output=io.BytesIO(); image.save(output,'JPEG',quality=85,optimize=True)
    data=output.getvalue(); digest=hashlib.sha256(data).hexdigest()
    if digest in hashes: continue
    taken+=1; pid=f'{key}-{taken:02}'
    (DEST/(pid+'.jpg')).write_bytes(data)
    manifest.append(dict(id=pid,filename=pid+'.jpg',width=image.width,height=image.height,sha256=digest,**candidate))
    seen.add(candidate['source_url']); hashes.add(digest); print('saved',pid,flush=True)
    if taken==4: break
   except (httpx.HTTPError,OSError) as error: print('skip',type(error).__name__,flush=True)
   time.sleep(.2)
  if taken<4: print('CATEGORY SHORTFALL',key,taken,flush=True)
 (DEST/'catalog.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
 print('TOTAL',len(manifest),flush=True)
 if len(manifest)<40: raise RuntimeError('Need at least 40 validated licensed photos')

if __name__=='__main__': main()
