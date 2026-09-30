# -*- coding: utf-8 -*-
r"""받은 번역(my files/yumimi_ko/*.tsv) → 자막 «조각» 수에 맞춘 번역 (2026-10-01)
  받은 번역은 일본어 받아쓰기 «줄»마다 한 줄(화자 이름 «엄마:» 포함) — 게임 자막은 영어 칸 «조각»(#명령 사이) 단위라 수가 다를 수 있다.
  ① 화자 머리 «이름：»·«이름:» 과 이어진 줄 머리 전각 공백을 뗀다(자막엔 화자를 안 씀 — 영문판도 없음)
  ② 줄 수 = 조각 수면 그대로. 다르면 영어 조각 글자 수 비율로 나눔:
     줄 > 조각: 줄들을 순서대로 묶음(동적 계획: 각 묶음의 한국어 길이 비율 ≈ 영어 조각 길이 비율)
     줄 < 조각: 긴 줄을 낱말 경계에서 쪼갬(비율 맞춤) — ⛔글자 단위로 자르지 않음
  ③ «ー» → «―»(한국어에 남은 장음 표시는 줄임표 대시로) · «유미» → «유미미»(사용자) · 노래 뜻풀이는 work/trans/songs.tsv
  미리보기: python tools/trmerge.py → work/trans/merge_preview.tsv (ID · 조각 · 일본어 · 영어 조각 · 받은 번역 · 바뀐 번역)
  적용:    python tools/trmerge.py --apply → my files/tsv/yumimi_*.tsv «번역» 열 채움(백업 work/trans/tsv_before_merge/)
"""
import glob, os, re, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import subs

SPK = re.compile(r'^\s*[^\s：:]{1,12}[：:]\s*')


def load_given():
    rows = {}
    for f in sorted(glob.glob(os.path.join(ROOT, 'my files', 'yumimi_ko', '*.tsv'))):
        for ln in open(f, encoding='utf-8').read().split('\n')[1:]:
            c = ln.split('\t')
            if len(c) == 8 and c[6].strip():
                rows[c[0]] = c
    return rows


def en_pieces_for(iid, ids, cells):
    """행 ID → 첫 칸의 영어 조각(가사 행이면 '<' 든 것, 아니면 나머지)"""
    kind, locs = ids[iid]
    for loc in locs:
        tab, rid = loc.split(':', 1)
        if tab == 'scene' and rid in cells:
            ps = subs.pieces(cells[rid])
            return [p for p in ps if ('<' in p) == (kind == '가사')]
    return None


def clean(line):
    line = SPK.sub('', line)
    line = re.sub(r'(?<!유)유미(?!미)', '유미미', line)          # 사용자 2026-10-01: 주인공 이름 «유미미» 로 통일(弓美 = ゆみみ)
    return line.strip(' 　').replace('ー', '―')


def group(lines, weights):
    """lines 를 순서대로 len(weights) 묶음으로 — 누적 길이 비율 차이 최소(DP)"""
    n, m = len(lines), len(weights)
    L = [max(1, len(x)) for x in lines]; tot = sum(L); wt = sum(weights) or 1
    tgt = []; acc = 0
    for w in weights:
        acc += w; tgt.append(acc / wt)
    pre = [0]
    for x in L:
        pre.append(pre[-1] + x)
    INF = float('inf')
    dp = [[INF] * (n + 1) for _ in range(m + 1)]; bk = [[0] * (n + 1) for _ in range(m + 1)]
    dp[0][0] = 0
    for j in range(1, m + 1):
        for i in range(j, n - (m - j) + 1):
            for k in range(j - 1, i):
                v = dp[j - 1][k] + (pre[i] / tot - tgt[j - 1]) ** 2
                if v < dp[j][i]:
                    dp[j][i] = v; bk[j][i] = k
    out = []; i = n
    for j in range(m, 0, -1):
        k = bk[j][i]; out.append(' '.join(lines[k:i])); i = k
    return out[::-1]


def split(lines, weights):
    """줄 < 조각: 낱말 경계(문장부호 뒤 우선, ⛔글자 단위 금지)에서 잘라 조각 수를 맞춤 —
       자를 곳 조합을 모두 따져 «누적 길이 비율 ≈ 영어 조각 비율» 이 가장 잘 맞는 것(부호 아닌 띄어쓰기 자리는 벌점)"""
    import itertools
    need = len(weights) - len(lines)
    cands = []                                       # (줄 번호, 위치, 벌점)
    for k, s in enumerate(lines):
        for m in re.finditer(r'[,.!?…―~、。！？]+\s*|\s+', s):
            if 0 < m.end() < len(s):
                cands.append((k, m.end(), 0 if re.match(r'[,.!?…―~、。！？]', s[m.start()]) else 0.03))
    if len(cands) < need:
        return None
    wt = sum(weights); tgt = []; acc = 0
    for w in weights:
        acc += w; tgt.append(acc / wt)
    best = None
    for combo in itertools.combinations(cands, need):
        parts = []
        for k, s in enumerate(lines):
            cs = sorted(p for kk, p, _ in combo if kk == k); prev = 0
            for p in cs:
                parts.append(s[prev:p].strip()); prev = p
            parts.append(s[prev:].strip())
        if any(not p for p in parts):
            continue
        tot = sum(len(p) for p in parts); acc = 0; err = sum(b for _, _, b in combo)
        for p, t in zip(parts, tgt):
            acc += len(p); err += (acc / tot - t) ** 2
        if best is None or err < best[0]:
            best = (err, parts)
    return best[1] if best else None


def convert(c, en):
    n = int(c[4])
    lines = [clean(x) for x in c[6].split('¶')]
    lines = [x for x in lines if x] or ['']
    if len(lines) == n:
        return lines, 'same'
    w = [len(p) for p in en] if en and len(en) == n else [1] * n
    if len(lines) > n:
        return group(lines, w), 'merge'
    r = split(lines, w)
    return (r, 'split') if r else (None, 'fail')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    apply_ = '--apply' in sys.argv
    given = load_given(); cells = subs.csv_cells()
    ids = {}
    for ln in open(os.path.join(ROOT, 'work', 'trans', 'ids.tsv'), encoding='utf-8').read().split('\n')[1:]:
        c = ln.split('\t')
        if len(c) >= 4:
            ids[c[0]] = (c[1], c[3:])
    out = {}; stat = {}; prev = ['ID\t조각\t방식\t일본어\t영어 조각\t받은 번역\t바뀐 번역\n']
    for iid, c in sorted(given.items()):
        en = en_pieces_for(iid, ids, cells)
        ps, how = convert(c, en)
        stat[how] = stat.get(how, 0) + 1
        if ps is None:
            continue
        out[iid] = '¶'.join(ps)
        if how != 'same' or SPK.match(c[6]) or 'ー' in c[6]:
            prev.append('%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (iid, c[4], how, c[5], ' ‖ '.join(en or []), c[6], out[iid]))
    # 노래 아랫줄 뜻풀이(받은 번역에 빈 6행 + 줄바꿈 살린 00387) — work/trans/songs.tsv 가 우선
    songs = os.path.join(ROOT, 'work', 'trans', 'songs.tsv')
    for ln in open(songs, encoding='utf-8').read().split('\n')[1:]:
        c = ln.split('\t')
        if len(c) >= 2 and c[1].strip():
            out[c[0]] = c[1]; stat['song'] = stat.get('song', 0) + 1
    open(os.path.join(ROOT, 'work', 'trans', 'merge_preview.tsv'), 'w', encoding='utf-8', newline='\n').write(''.join(prev))
    print('받은 번역 %d행 · %s · 미리보기 work/trans/merge_preview.tsv (%d행)' % (len(given), stat, len(prev) - 1))
    if apply_:
        bak = os.path.join(ROOT, 'work', 'trans', 'tsv_before_merge'); os.makedirs(bak, exist_ok=True)
        n = 0
        for f in sorted(glob.glob(os.path.join(ROOT, 'my files', 'tsv', 'yumimi_*.tsv'))):
            shutil.copy2(f, bak)
            L = open(f, encoding='utf-8').read().split('\n'); o = [L[0]]
            for ln in L[1:]:
                c = ln.split('\t')
                if len(c) == 8 and c[0] in out and c[2] != '가사':
                    c[6] = out[c[0]]; n += 1
                o.append('\t'.join(c))
            open(f, 'w', encoding='utf-8', newline='\n').write('\n'.join(o))
        print('적용 %d행 → my files/tsv (가사 행은 미리 채운 한글 발음 유지)' % n)


if __name__ == '__main__':
    main()
