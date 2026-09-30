# -*- coding: utf-8 -*-
r"""유미미 믹스 리믹스 번역 TSV 추출 (2026-10-01) — 영문 패치 소스의 자막 표 → my files/tsv/yumimi_001‥.tsv
  원본 표: work/en/yumimiremixtools/yumimi/script/script_scene.csv · script_choice.csv
    열 = 종류(string) · ID(C101C2.DAT-ss0-4 / C117.DAT-choice-1-0) · 매개 · 화자 · 일본어 받아쓰기 · 영어 · 메모 · 상태
  영어 칸 = 여러 줄. «#…» 줄 = 타이밍 명령(#w·#woff·#off·#slot·#kseg·#sync·#align·#pal …), 빈 줄 = 자막 비움, «//» 뒤 = 주석
    → 번역할 «글 줄»만 한 행으로 뽑는다(명령·빈 줄·주석은 빌더가 원래 자리에 그대로 둔다).
  글 줄 안 표기(번역에서 보존): «\n»(글자 그대로) = 게임 안 줄바꿈 · «+A+B+» = 경칭 옵션별 두 벌(보이기/숨기기) ·
    «<…>» = 노래 가사 로마자 구간 · «{…}» · «*» 는 게임이 버림(옛 기울임).
  같은 글 줄은 한 행(공유 = 나온 횟수), 전 위치는 work/trans/ids.tsv(ID → 표:행ID:줄번호 …).
  열: ID · 위치(장면 파일) · 구분(대사/노래/선택지) · 공유 · 원문(영어) · 번역 · 화자 · 일본어(참고, 그 칸 전체)
  파일은 29KB(UTF-8) 이하로 나누고 마지막 자투리는 앞 파일과 합칠 수 있으면 합친다.
  python tools/extract.py
"""
import csv, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, 'work', 'en', 'yumimiremixtools', 'yumimi', 'script')
OUT = os.path.join(ROOT, 'my files', 'tsv')
HEAD = 'ID\t위치\t구분\t공유\t원문\t번역\t화자\t일본어\n'
LIMIT = 29 * 1024


def esc(s):
    return s.replace('\t', ' ').replace('\r', '').replace('\n', '¶')


def text_lines(cell):
    """영어 칸 → [(줄 번호, 글)] — 명령·빈 줄·주석 줄 제외, 줄 끝 주석은 떼고"""
    out = []
    for k, ln in enumerate(cell.split('\n')):
        s = ln.strip()
        if not s or s.startswith('#') or s.startswith('//'):
            continue
        body = ln.split('//')[0].rstrip()
        if body.strip():
            out.append((k, body))
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    first = {}; order = []
    for tab, kind0 in (('script_scene.csv', '대사'), ('script_choice.csv', '선택지')):
        for r in csv.reader(open(os.path.join(SRC, tab), encoding='utf-8')):
            if not r or r[0] != 'string' or len(r) < 6:
                continue
            rid, spk, jp, en = r[1], r[3], r[4], r[5]
            kind = kind0
            if kind0 == '대사' and ('#kseg' in en or '<' in en):
                kind = '노래'
            for k, body in text_lines(en):
                loc = '%s:%s:%d' % (tab.split('_')[1].split('.')[0], rid, k)
                if body not in first:
                    first[body] = {'kind': kind, 'file': rid.split('-')[0], 'spk': spk, 'jp': jp, 'locs': []}
                    order.append(body)
                first[body]['locs'].append(loc)
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.startswith('yumimi_') and f.endswith('.tsv'):
            os.remove(os.path.join(OUT, f))
    lines = []; ids = ['ID\t위치…\n']
    for n, body in enumerate(order):
        e = first[body]; iid = '%05d' % (n + 1)
        lines.append('%s\t%s\t%s\t%d\t%s\t\t%s\t%s\n' % (iid, e['file'], e['kind'], len(e['locs']), esc(body), esc(e['spk']), esc(e['jp'])))
        ids.append(iid + '\t' + '\t'.join(e['locs']) + '\n')
    files = []; cur = []; size = len(HEAD.encode('utf-8'))
    for ln in lines:
        b = len(ln.encode('utf-8'))
        if cur and size + b > LIMIT:
            files.append(cur); cur = []; size = len(HEAD.encode('utf-8'))
        cur.append(ln); size += b
    if cur:
        files.append(cur)
    if len(files) > 1 and len((HEAD + ''.join(files[-2] + files[-1])).encode('utf-8')) <= LIMIT:
        files[-2] += files.pop()
    for k, fl in enumerate(files):
        open(os.path.join(OUT, 'yumimi_%03d.tsv' % (k + 1)), 'w', encoding='utf-8', newline='\n').write(HEAD + ''.join(fl))
    os.makedirs(os.path.join(ROOT, 'work', 'trans'), exist_ok=True)
    open(os.path.join(ROOT, 'work', 'trans', 'ids.tsv'), 'w', encoding='utf-8', newline='\n').write(''.join(ids))
    import collections
    kc = collections.Counter(first[b]['kind'] for b in order)
    words = sum(len(b.split()) for b in order)
    print('글 줄 %d(출현 %d) · %s · 영어 단어 %d · 파일 %d개 → my files/tsv/yumimi_001‥%03d.tsv'
          % (len(order), sum(len(first[b]['locs']) for b in order), dict(kc), words, len(files), len(files)))


if __name__ == '__main__':
    main()
