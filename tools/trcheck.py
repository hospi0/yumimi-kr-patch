# -*- coding: utf-8 -*-
r"""번역 TSV 검사 (쓰는 순간 강제) — my files/tsv/yumimi_*.tsv 의 «번역» 칸
  ⛔막음: 조각 수(¶ 로 나눈 수) ≠ 조각 열 · 가나·한자 남음 · 실제 탭/줄바꿈 · «+»(경칭 옵션 뺌) ·
         가사 행의 «< > { }» 순서가 원문과 다름(카라오케 구간 수·자리) ·
         ★인물 이름 표기 어긋남(거센소리 규칙: つ=츠·か행 ㅋ·た행 ㅌ — NAMES 의 바른 꼴에서 쓰/즈·된소리·예사소리 변형을 만들어 막음;
           2026-10-01 «마쓰자키» 8곳이 빌드까지 샘 — build.py 가 이 검사를 먼저 돌린다)
  ⚠경고: 조각 머리에 «이름：» 화자 표시 · 빈 조각
  python tools/trcheck.py [파일…]
"""
import glob, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
JP = re.compile(r'[぀-ヿ一-鿿ｦ-ﾟ]')
NAMES = ['마츠자키', '사쿠라코', '신이치', '요시자와', '유미미', '리에']
_ALT = {14: [10, 13, 12], 15: [1, 0], 16: [4, 3]}       # 초성 ㅊ→ㅆ·ㅉ·ㅈ · ㅋ→ㄲ·ㄱ · ㅌ→ㄸ·ㄷ


def _variants(name):
    out = set()
    for i, ch in enumerate(name):
        o = ord(ch) - 0xAC00; cho, rest = o // 588, o % 588
        for alt in _ALT.get(cho, []):
            v = name[:i] + chr(0xAC00 + alt * 588 + rest) + name[i + 1:]
            out.add(v)
        if cho == 14 and rest // 28 == 18:
            out.add(name[:i] + '즈' + name[i + 1:])
    return out - {name}


BAD = {v: n for n in NAMES for v in _variants(n)}


def check_row(c):
    err = []; warn = []
    iid, kind, n, src, tr = c[0], c[2], int(c[4]), c[5], c[6]
    if not tr.strip():
        return err, warn
    ps = tr.split('¶')
    if len(ps) != n:
        err.append('조각 %d개인데 번역은 %d개(¶ 로 나눔)' % (n, len(ps)))
    m = JP.findall(tr)
    if m:
        err.append('가나·한자 남음 «%s»' % ''.join(m[:8]))
    for v, n in BAD.items():
        if v in tr:
            err.append('이름 «%s» → «%s»(거센소리 규칙·표기 통일)' % (v, n))
    if '+' in tr:                           # 2026-10-01 사용자: 경칭 옵션 뺌 → 한 벌만 번역
        err.append('«+» 사용 — 경칭 옵션은 한국어판에서 뺐음(한 벌만 쓸 것)')
    if kind == '가사':
        sig = lambda s: ''.join(ch for ch in s if ch in '<>{}¶')
        if sig(tr) != sig(src):
            err.append('카라오케 표시 «< > { }» 가 원문과 다름')
    for k, p in enumerate(ps):
        if not p.strip():
            warn.append('%d번째 조각이 빔' % (k + 1))
        if re.match(r'^\s*[^\s：:]{1,8}[：:]', p) and kind != '가사':
            warn.append('%d번째 조각 머리에 화자 표시?' % (k + 1))
    return err, warn


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    files = sys.argv[1:] or sorted(glob.glob(os.path.join(ROOT, 'my files', 'tsv', 'yumimi_*.tsv')))
    ne = nw = done = total = 0
    for f in files:
        for ln, l in enumerate(open(f, encoding='utf-8').read().split('\n')[1:], 2):
            if not l:
                continue
            c = l.split('\t')
            if len(c) != 8:
                print('⛔ %s:%d 열 %d개(8개여야 — 번역 안 실제 탭?)' % (os.path.basename(f), ln, len(c))); ne += 1; continue
            total += 1; done += bool(c[6].strip())
            e, w = check_row(c)
            for x in e:
                print('⛔ %s %s %s' % (os.path.basename(f), c[0], x)); ne += 1
            for x in w:
                print('⚠️ %s %s %s' % (os.path.basename(f), c[0], x)); nw += 1
    print('번역 %d / %d행 · 오류 %d · 경고 %d' % (done, total, ne, nw))
    sys.exit(1 if ne else 0)


if __name__ == '__main__':
    main()
