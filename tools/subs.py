# -*- coding: utf-8 -*-
r"""유미미 자막 블록(SUBS) 읽기·검증 (2026-10-01)
  영문 패치(ymm_scriptbuild)는 자막 스크립트를 컴파일해 장면 파일 «앞»에 SUBS 블록으로 붙인다:
    +0 'SUBS' · +4 u32 블록 크기(4 정렬) · +8 u32 소리 수 N · +12 u32 오프셋 × (1 + N + 추가)  [+12 기준, 0 = 없음]
    오프셋 순서 = [장면 시작 스크립트, 소리 0‥N-1 스크립트, 추가 스크립트…]  (spec_scene.txt 순서: 소리들 → start → 추가)
  스크립트 = 바이트 흐름: F0 wait(u16 프레임) · F1 off · F2 slot(u8) · F3 pal(u8) · F4 points(u16,u16 — 문자열 바로 뒤) ·
    F5 align(u8) · F6 sync(u8,u16,u16) · F7 startstream(u8,u8) · 00 = 스크립트 끝 · 그 밖 = 문자열(00 까지, 글꼴 표 코드)
  CSV 영어 칸 조각(#명령 사이 글 줄)과 컴파일된 문자열이 «순서대로 1:1» 인지 검증 → 한국어는 문자열만 갈아 끼우면 된다.
  python tools/subs.py            → 전 장면 검증 요약
"""
import csv, os, re, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, r'C:\claude\project\cyberdoll-kr-patch\tools')
import disc
YT = os.path.join(ROOT, 'work', 'en', 'yumimiremixtools', 'yumimi')
EN_BIN = os.path.join(ROOT, 'work', 'en', 'en_full.bin')
ARGS = {0xF0: 2, 0xF1: 0, 0xF2: 1, 0xF3: 1, 0xF4: 4, 0xF5: 1, 0xF6: 5, 0xF7: 2}


def load_table(path=os.path.join(YT, 'font', 'scene', 'table.tbl')):
    t = {}
    for ln in open(path, encoding='utf-8').read().split('\n'):
        if '=' in ln and not ln.startswith('#'):
            k, v = ln.split('=', 1)
            c = int(k, 16)
            if v and 0 < c < 0xF0:              # 00·F0~ = 제어 이름([null]·[wait]…) — 글이 아님, 9D=[*] 는 글자
                t[v] = c
    return t


def encode(s, table):
    """YmmScriptReader.outputNextSymbol 과 같게: '*' 버림, 표에서 가장 긴 일치"""
    out = bytearray(); i = 0
    keys = sorted(table, key=len, reverse=True)
    while i < len(s):
        if s[i] == '*':
            i += 1; continue
        for k in keys:
            if s.startswith(k, i):
                out.append(table[k]); i += len(k); break
        else:
            raise ValueError('표에 없는 글자 %r «%s»' % (s[i], s))
    return bytes(out)


def pieces(cell):
    """영어 칸 → 조각(#줄이 끊음, 빈 줄·// 주석 무시, 줄 끝 // 주석 뗌) — 조각 = 글 줄들을 그대로 이은 것"""
    out = []; cur = []
    for ln in cell.split('\n'):
        s = ln.strip()
        if s.startswith('#'):
            if cur:
                out.append(''.join(cur)); cur = []
            continue
        if not s or s.startswith('//'):
            continue
        body = ln.split('//')[0]
        if body.strip():
            cur.append(body)
    if cur:
        out.append(''.join(cur))
    return out


def parse_script(b, o):
    """o 부터 스크립트 → [('s', 시작, 끝) | ('op', 코드, 시작, 끝)], 끝 위치"""
    toks = []
    while True:
        c = b[o]
        if c == 0:
            return toks, o + 1
        if c >= 0xF0:
            n = ARGS[c]; toks.append(('op', c, o, o + 1 + n)); o += 1 + n; continue
        e = b.index(0, o)
        toks.append(('s', o, e)); o = e + 1


def parse_block(b):
    """→ 크기, 소리 수, [스크립트 절대 위치 | 0] — 오프셋은 «+12(색인 시작)» 기준, 색인 칸 수 = 첫 오프셋 / 4"""
    assert b[:4] == b'SUBS'
    size, nsnd = struct.unpack_from('>II', b, 4)
    offs = []; k = 0; first = None
    while (first is None or k < first) and 12 + k < size:
        v = struct.unpack_from('>I', b, 12 + k)[0]; offs.append(12 + v if v else 0); k += 4
        if v and (first is None or v < first):
            first = v
    return size, nsnd, offs


def regions():
    """spec_scene.txt → {파일: (소리 수, [스크립트 ID…] 블록 순서)}"""
    out = {}; cur = None; ids = []
    txt = open(os.path.join(YT, 'script', 'spec_scene.txt'), encoding='utf-8').read()
    for ln in txt.split('\n'):
        m = re.match(r'#SETFILE\("([^"]+)"\)', ln)
        if m:
            cur = m.group(1); out[cur] = [0, []]; continue
        m = re.match(r'#SETSOUNDCOUNT\((\d+)\)', ln)
        if m and cur:
            out[cur][0] = int(m.group(1)); continue
        m = re.match(r'#STARTSTRING\("([^"]+)"\)', ln)
        if m and cur:
            out[cur][1].append(m.group(1))
        if ln.startswith('#STARTREGION'):
            cur = None
    res = {}
    for f, (n, ids) in out.items():
        snd = ids[:n]; rest = ids[n:]
        start = rest[:1]; extra = rest[1:]
        res[f] = (n, (start or [None]) + snd + extra)
    return res


def csv_cells():
    cells = {}
    for r in csv.reader(open(os.path.join(YT, 'script', 'script_scene.csv'), encoding='utf-8')):
        if r and r[0] == 'string' and len(r) > 5:
            cells[r[1]] = r[5]
    return cells


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    table = load_table(); cells = csv_cells(); reg = regions()
    D = disc.Disc(EN_BIN)
    fmap = {nm.lstrip('/'): (l, s) for nm, l, s in D.files()}
    ok = bad = nostr = 0; nblk = 0; worst = []
    for f, (nsnd, ids) in sorted(reg.items()):
        if f not in fmap:
            continue
        l, s = fmap[f]
        b = D.sec(l, (s + 2047) // 2048)[:s]
        if b[:4] != b'SUBS':
            continue
        nblk += 1
        size, n2, offs = parse_block(b)
        assert n2 == nsnd, (f, n2, nsnd)
        for k, off in enumerate(offs):
            sid = ids[k] if k < len(ids) else None
            if not off:
                continue
            toks, _ = parse_script(b, off)
            strs = [b[t[1]:t[2]] for t in toks if t[0] == 's']
            want = [encode(p, table) for p in pieces(cells.get(sid, ''))] if sid else []
            if strs == want:
                ok += 1
            else:
                bad += 1
                if len(worst) < 8:
                    worst.append((f, k, sid, len(strs), len(want), strs[:2], want[:2]))
    print('SUBS 블록 %d개 · 스크립트 일치 %d · 불일치 %d' % (nblk, ok, bad))
    for w in worst:
        print('  ', w)


if __name__ == '__main__':
    main()
