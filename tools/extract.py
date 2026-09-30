# -*- coding: utf-8 -*-
r"""유미미 믹스 리믹스 번역 TSV 추출 (2026-10-01 2판 — «일본어 원문» 기준) → my files/tsv/yumimi_001‥.tsv
  원본 표: work/en/yumimiremixtools/yumimi/script/script_scene.csv · script_choice.csv
    열 = 종류(string) · ID(C101C2.DAT-ss0-4 / C117.DAT-choice-1-0) · 매개 · 화자 · 일본어 받아쓰기 · 영어 · 메모 · 상태
  자막 «조각» = 영어 칸에서 «#명령» 줄 사이의 글 줄 묶음(YmmScriptReader: 명령이 문자열을 끊는다, 빈 줄·// 주석 무시).
    조각마다 표시 시각(#w)이 붙어 있으므로 번역도 같은 수의 조각이어야 한다 → 번역 칸은 조각을 «¶» 로 이어 쓴다.
  행 = 칸(음성 한 토막) 하나. 원문 = 일본어 받아쓰기(줄 = ¶).
    구분: 대사 · 선택지 · 노래(가사 칸의 뜻 번역·대사 조각) · 가사(윗줄 카라오케 «<…>» 발음 — 로마자 → 한글 발음으로 미리 채움)
  같은 (구분·일본어·조각 수) 칸은 한 행(공유 = 칸 수), 전 위치는 work/trans/ids.tsv.
  열: ID · 위치 · 구분 · 공유 · 조각 · 원문 · 번역 · 화자
  파일은 29KB(UTF-8) 이하로 나누고 마지막 자투리는 앞 파일과 합칠 수 있으면 합친다.
  python tools/extract.py
"""
import csv, os, re, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import kana
SRC = os.path.join(ROOT, 'work', 'en', 'yumimiremixtools', 'yumimi', 'script')
OUT = os.path.join(ROOT, 'my files', 'tsv')
HEAD = 'ID\t위치\t구분\t공유\t조각\t원문\t번역\t화자\n'
LIMIT = 29 * 1024


def esc(s):
    return s.replace('\t', ' ').replace('\r', '').replace('\n', '¶')


def pieces(cell):
    """영어 칸 → 조각 목록 [[글 줄…]] — «#» 줄이 끊고, 빈 줄·// 주석 줄은 건너뛴다(끊지 않음)"""
    out = []; cur = []
    for ln in cell.split('\n'):
        s = ln.strip()
        if s.startswith('#'):
            if cur:
                out.append(cur); cur = []
            continue
        if not s or s.startswith('//'):
            continue
        body = ln.split('//')[0].rstrip()
        if body.strip():
            cur.append(body)
    if cur:
        out.append(cur)
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    rows = {}; order = []

    def add(kind, jp, n, tr, spk, loc):
        k = (kind, jp, n)
        if k not in rows:
            rows[k] = {'kind': kind, 'jp': jp, 'n': n, 'tr': tr, 'spk': spk, 'file': loc.split(':')[1].split('-')[0], 'locs': []}
            order.append(k)
        rows[k]['locs'].append(loc)

    for tab, kind0 in (('script_scene.csv', '대사'), ('script_choice.csv', '선택지')):
        t = tab.split('_')[1].split('.')[0]
        for r in csv.reader(open(os.path.join(SRC, tab), encoding='utf-8')):
            if not r or r[0] != 'string' or len(r) < 6:
                continue
            rid, spk, jp, en = r[1], r[3], r[4], r[5]
            ps = pieces(en)
            if not ps:
                continue
            song = [p for p in ps if '<' in ''.join(p)]
            talk = [p for p in ps if '<' not in ''.join(p)]
            loc = '%s:%s' % (t, rid)
            if song:
                roma = '¶'.join(''.join(p) for p in song)
                add('가사', roma, len(song), '¶'.join(kana.line(''.join(p)) for p in song), '', loc)
                if talk:
                    add('노래', jp, len(talk), '', spk, loc)
            else:
                add(kind0, jp, len(talk), '', spk, loc)

    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.startswith('yumimi_') and f.endswith('.tsv'):
            os.remove(os.path.join(OUT, f))
    lines = []; ids = ['ID\t구분\t조각\t위치…\n']
    for n, k in enumerate(order):
        e = rows[k]; iid = '%05d' % (n + 1)
        lines.append('%s\t%s\t%s\t%d\t%d\t%s\t%s\t%s\n' % (iid, e['file'], e['kind'], len(e['locs']), e['n'], esc(e['jp']), esc(e['tr']), esc(e['spk'])))
        ids.append('%s\t%s\t%d\t%s\n' % (iid, e['kind'], e['n'], '\t'.join(e['locs'])))
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
    kc = collections.Counter(rows[k]['kind'] for k in order)
    jc = sum(len(re.sub(r'\s', '', rows[k]['jp'])) for k in order if rows[k]['kind'] != '가사')
    split = sum(1 for k in order if rows[k]['kind'] != '가사'
                and len([l for l in rows[k]['jp'].split('\n') if l.strip()]) != rows[k]['n'])
    print('행 %d(칸 %d) · %s · 일본어 %d자 · 조각 수 ≠ 일본어 줄 수 %d행 · 파일 %d개 → my files/tsv/yumimi_001‥%03d.tsv'
          % (len(order), sum(len(rows[k]['locs']) for k in order), dict(kc), jc, split, len(files), len(files)))


if __name__ == '__main__':
    main()
