#!/usr/bin/env python3
"""Export the same localized manual shown by the authenticated web UI."""
import argparse
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/app'))
from user_docs import LANGS,categories
from release_version import VERSION

def render():
    files={}
    titles=('Dokumentation','Documentation','Documentación','Documentation')
    for index,lang in enumerate(LANGS):
        menu=['# '+titles[index]+' · '+VERSION,'']
        for category in categories(lang):
            menu+=['## '+category['title'],'']
            for doc in category['documents']:
                menu+=['- ['+doc['title']+']('+doc['slug']+'.md)']
                lines=['# '+doc['title'],'',category['title']+' · '+VERSION,'']
                for number,step in enumerate(doc['steps'],1):lines+=[str(number)+'. '+step,'']
                for command in doc['commands']:lines+=['```text',command,'```','']
                for label,link in doc['links']:lines+=['- ['+label+']('+link+')']
                files[ROOT/'docs'/lang/(doc['slug']+'.md')]='\n'.join(lines)+'\n'
            menu+=['']
        files[ROOT/'docs'/lang/'README.md']='\n'.join(menu)+'\n'
    return files

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    files=render()
    for path,text in files.items():
        if args.check:
            if not path.is_file() or path.read_text(encoding='utf-8')!=text:raise SystemExit('Documentation export differs: '+str(path.relative_to(ROOT)))
        else:path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8',newline='\n')
    print('Documentation: '+str(len(files))+' localized files '+('verified' if args.check else 'exported'))
if __name__=='__main__':main()
