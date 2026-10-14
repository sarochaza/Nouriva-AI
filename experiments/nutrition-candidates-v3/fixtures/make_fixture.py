import json,struct,zlib,binascii
from pathlib import Path

def write_png(path,index):
    def chunk(tag,data):return struct.pack('>I',len(data))+tag+data+struct.pack('>I',binascii.crc32(tag+data)&0xffffffff)
    pixels=b''.join(b'\0'+bytes([50+index%150,90,150])*32 for _ in range(32))
    Path(path).write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',32,32,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(pixels))+chunk(b'IEND',b''))

def make_fixture(root):
    root=Path(root);(root/'test').mkdir(parents=True,exist_ok=True)
    rows=[]
    for i in range(5):
        dish=f'mock_{i:04}';g=100+10*i;write_png(root/'test'/f'{dish}.png',i)
        rows.append({'file_name':f'test/{dish}.png','id':dish,'split':'test',
                     'ingredients':[{'id':'TEST_CARROT','name':'Carrots, raw','grams':g,'calories':g*.41,'fat':g*.0024,'carb':g*.0958,'protein':g*.0093}],
                     'total_calories':g*.41,'total_mass':g,'total_fat':g*.0024,'total_carb':g*.0958,'total_protein':g*.0093})
    (root/'metadata.jsonl').write_text('\n'.join(json.dumps(r) for r in rows)+'\n',encoding='utf-8')
    (root/'SYNTHETIC_TEST_ONLY.txt').write_text('Colored squares and known arithmetic. No actual food images or real dataset ground truth. Not a benchmark result.\n')
    return root

if __name__=='__main__':
    from src.common import ROOT
    print(make_fixture(ROOT/'fixtures/dataset'))
