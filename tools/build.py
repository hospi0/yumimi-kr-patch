# -*- coding: utf-8 -*-
r"""유미미 믹스 리믹스 한글 빌드 (2026-10-01) — 영문 패치 적용본(work/en/en_full.bin)을 직접 고친다
  ① 번역: my files/tsv/yumimi_*.tsv «번역» 열 + work/trans/poc.tsv(덮어씀) → 칸(ID) → 조각 목록
     ids.tsv 로 칸 ID(scene:C101C2.DAT-ss0-4) 를 찾고, 영어 칸 조각 순서대로 «<» 든 조각 = 가사 행, 나머지 = 대사/노래 행.
     번역 없는 칸·조각은 영문 그대로.
  ② 장면마다: SUBS 블록 스크립트의 문자열만 교체(명령 바이트 그대로) — tools/subs.py 가 1:1 검증.
     한국어 음절(글꼴 표에 없는 글자 전부)은 장면별 번호 i → 2바이트 A0+i/200, 1+i%200, 글리프(1bpp 28 B, 실행 중 테두리·그림자 생성)는 블록 뒤 → 적재 때 높은 RAM(GLY)으로 복사.
     블록 = 'SUBS'·전체 크기·소리 수·색인(+12 기준)·스크립트… (4 정렬 = 복사 크기) + 글리프 + (4 정렬) + [복사 크기]['HANG']
  ③ SATANIME.BIN: tools/hookk.py (copyWrap·remap·폭·커닝) + tools/gfx.py 그림(일시정지·인터페이스·장면 그림·퍼즐)
  ④ 트랙 1 전체 재배치(tools/iso.py) → work/out/Yumimi Mix Remix (Japan) (Track 1).bin
  ⛔쓰는 순간 막음: 블록 ≤0x3000 · 장면 글리프 ≤ GLY 버퍼 · 조각 수 · 문자열 0xBF B 초과 · 자리별 음절 칸 초과(아래 46 / 위 29) · 복사 크기 0x2000 초과 · 갈무리에 없는 글자
  ⚠경고: 원래 적재 창(0xF8000) 안이던 장면이 창을 넘음
  python tools/build.py [--write]
"""
import csv, glob, os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, r'C:\claude\project\cyberdoll-kr-patch\tools')
import disc, subs, kfont, hookk, iso, rules, gfx

EN_BIN = os.path.join(ROOT, 'work', 'en', 'en_full.bin')
N_TRACK1 = 134992                   # 영문 적용본 트랙 1 섹터 수
OUT = os.path.join(ROOT, 'work', 'out', 'Yumimi Mix Remix (Japan) (Track 1).bin')
WINDOW = 0xF8000
POOL = {0: hookk.POOL_A[1], 1: hookk.POOL_B[1]}
GLY_MAX = hookk.build()[1]['GLY_MAX']
NORM = {'…': '...', '！': '!', '？': '?', '、': ',', '，': ',', '。': '.', '．': '.', '：': ':', '；': ';', '（': '(', '）': ')',
        '　': ' ', '―': '―', '－': '-', '〜': '~', '～': '~', '─': '―', '━': '―', 'ー': '―'}
NORM.update({chr(c): chr(c - 0xFEE0) for c in range(0xFF01, 0xFF5F) if chr(c) not in NORM})   # 전각 영숫자·부호 → 반각(영문 글꼴로)


class Err(Exception):
    pass


def load_tr():
    tr = {}
    for f in sorted(glob.glob(os.path.join(ROOT, 'my files', 'tsv', 'yumimi_*.tsv'))):
        for ln in open(f, encoding='utf-8').read().split('\n')[1:]:
            c = ln.split('\t')
            if len(c) == 8 and c[6].strip():
                tr[c[0]] = c[6]
    poc = os.path.join(ROOT, 'work', 'trans', 'poc.tsv')
    if os.path.exists(poc):
        for ln in open(poc, encoding='utf-8').read().split('\n')[1:]:
            c = ln.split('\t')
            if len(c) >= 2 and c[1].strip():
                tr[c[0]] = c[1]
    return tr


def cell_pieces(tr):
    """칸 ID → {'talk': [조각…] | None, 'song': [조각…] | None}"""
    out = {}; errs = []
    for ln in open(os.path.join(ROOT, 'work', 'trans', 'ids.tsv'), encoding='utf-8').read().split('\n')[1:]:
        c = ln.split('\t')
        if len(c) < 4:
            continue
        iid, kind, n = c[0], c[1], int(c[2])
        if iid not in tr:
            continue
        ps = tr[iid].split('¶')
        if len(ps) != n:
            errs.append('%s 조각 %d개인데 번역 %d개' % (iid, n, len(ps))); continue
        for loc in c[3:]:
            tab, rid = loc.split(':', 1)
            if tab != 'scene':
                continue                    # 선택지는 그림(따로)
            d = out.setdefault(rid, {'talk': None, 'song': None})
            d['song' if kind == '가사' else 'talk'] = ps
    return out, errs


class Enc:
    """장면 하나의 인코더 — 음절 번호·글리프"""
    def __init__(self, table):
        self.table = table; self.keys = sorted(table, key=len, reverse=True)
        self.gid = {}; self.glyphs = []

    def glyph_code(self, ch):
        if ch not in self.gid:
            i = len(self.glyphs)
            if i >= 64 * 200:
                raise Err('장면 음절 너무 많음')
            self.glyphs.append(kfont.pack1(kfont.cell(ch)))
            self.gid[ch] = i
        i = self.gid[ch]
        return bytes([0xA0 + i // 200, 1 + i % 200])

    def encode(self, s):
        s = ''.join(NORM.get(ch, ch) for ch in s)
        s = rules.squeeze(s)
        out = bytearray(); i = 0; used = set()
        while i < len(s):
            ch = s[i]
            if ch == '*':
                raise Err('«*» 는 게임이 버림 «%s»' % s)
            for k in self.keys:
                if s.startswith(k, i):
                    out.append(self.table[k]); i += len(k); break
            else:
                out += self.glyph_code(ch); used.add(ch); i += 1
        return bytes(out), used


def script_slot_strings(b, off, slot0):
    """스크립트 → [(문자열 시작, 끝, 자리)]"""
    toks, _ = subs.parse_script(b, off); slot = slot0; out = []
    for t in toks:
        if t[0] == 'op':
            if t[1] == 0xF2:
                slot = b[t[2] + 1]
        else:
            out.append((t[1], t[2], slot))
    return toks, out


def build_scene(name, b, ids, cells, pieces, table, errs, stat):
    size, nsnd, offs = subs.parse_block(b)
    enc = Enc(table)
    newscripts = []; changed = False
    for k, off in enumerate(offs):
        if not off:
            newscripts.append(None); continue
        sid = ids[k] if k < len(ids) else None
        toks, strs = script_slot_strings(b, off, 1 if k == 0 else 0)
        rep = {}
        if sid and sid in pieces:
            en = subs.pieces(cells.get(sid, ''))
            assert len(en) == len(strs), (name, sid)
            talk = list(pieces[sid]['talk'] or []); song = list(pieces[sid]['song'] or [])
            has_t = pieces[sid]['talk'] is not None; has_s = pieces[sid]['song'] is not None
            for j, p in enumerate(en):
                src = song if '<' in p else talk
                if (has_s if '<' in p else has_t):
                    if not src:
                        errs.append('%s %s 조각 모자람' % (name, sid)); break
                    t = src.pop(0)
                    try:
                        enc_b, used = enc.encode(t)
                    except Exception as e:
                        errs.append('%s %s %s' % (name, sid, e)); continue
                    s0, s1, slot = strs[j]
                    if len(enc_b) > 0xBF:
                        errs.append('%s %s 문자열 %d B > 0xBF «%s»' % (name, sid, len(enc_b), t))
                    if len(used) > POOL[slot]:
                        errs.append('%s %s %s 자리 음절 %d > %d «%s»' % (name, sid, '아래' if slot == 0 else '위', len(used), POOL[slot], t))
                    rep[s0] = enc_b; stat['str'] += 1
        # 스크립트 다시 쓰기
        o = bytearray()
        for t in toks:
            if t[0] == 'op':
                o += b[t[2]:t[3]]
            else:
                o += rep.get(t[1], b[t[1]:t[2]]) + b'\x00'
        o += b'\x00'
        if rep:
            changed = True
        newscripts.append(bytes(o))
    if not changed:
        return None
    # 블록 조립
    idx = bytearray(); body = bytearray(); base = 4 * len(offs)
    for s in newscripts:
        if s is None:
            idx += struct.pack('>I', 0)
        else:
            idx += struct.pack('>I', base + len(body)); body += s
    blk = bytearray(b'SUBS' + bytes(4) + struct.pack('>I', nsnd)) + idx + body
    blk += bytes((-len(blk)) % 4)
    copy = len(blk)
    if copy > 0x2000:
        errs.append('%s 복사 크기 0x%X > 0x2000' % (name, copy))
    for g in enc.glyphs:
        blk += g
    blk += bytes((-len(blk)) % 4 or 4)          # 글리프 부분 최소 4 B(copyWrap 의 memcpy 크기 0 방지)
    gbytes = len(blk) - copy
    if gbytes > GLY_MAX:
        errs.append('%s 글리프 %d개 = %d B > %d B(높은 RAM 버퍼)' % (name, len(enc.glyphs), gbytes, GLY_MAX))
    blk += struct.pack('>I', copy) + b'HANG'
    if len(blk) & 0xFFFF == 0:              # subtitleBlockExists 는 크기 하위 16비트(0이면 «없음»)
        blk[-8:-8] = bytes(4)
    struct.pack_into('>I', blk, 4, len(blk))
    if len(blk) > hookk.BLOCK_MAX:
        errs.append('%s SUBS 블록 0x%X > 0x%X(음성 분할 읽기 여분 섹터)' % (name, len(blk), hookk.BLOCK_MAX))
    new = bytes(blk) + b[size:]
    stat['scene'] += 1; stat['glyph'] += len(enc.glyphs)
    if len(b) <= WINDOW < len(new):
        stat['warn'].append('%s 적재 창 0xF8000 을 넘음(0x%X → 0x%X)' % (name, len(b), len(new)))
    return new


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    write = '--write' in sys.argv
    table = subs.load_table(); cells = subs.csv_cells(); reg = subs.regions()
    tr = load_tr()
    pieces, errs = cell_pieces(tr)
    print('규칙: 조각 수 · 문자열 ≤0xBF B · 아래 자리 음절 ≤%d · 위 ≤%d · 블록 복사부 ≤0x2000 · 부호 뒤 공백 삭제' % (POOL[0], POOL[1]))
    print('번역 행 %d · 번역 든 칸 %d' % (len(tr), len(pieces)))
    D = disc.Disc(EN_BIN)
    fmap = {nm.lstrip('/'): (l, s) for nm, l, s in D.files()}
    repl = {}; stat = {'scene': 0, 'glyph': 0, 'str': 0, 'warn': []}
    for name, (nsnd, ids) in sorted(reg.items()):
        if name not in fmap or not any(i in pieces for i in ids if i):
            continue
        l, s = fmap[name]
        b = D.sec(l, (s + 2047) // 2048)[:s]
        if b[:4] != b'SUBS':
            continue
        new = build_scene(name, b, ids, cells, pieces, table, errs, stat)
        if new:
            repl['/' + name] = new
    exe, sym = hookk.patch_exe(D.read('/SATANIME.BIN'))
    repl['/SATANIME.BIN'] = gfx.patch_exe(exe)          # 일시정지 메뉴(경칭 줄 숨김)·인터페이스 줄
    repl.update(gfx.build_all(D, repl))                 # 장면 그림: 메인 메뉴·백업 안내 2·광고
    repl['/MINISND.ABK'] = gfx.patch_minisnd(D.read('/MINISND.ABK'))   # 퍼즐 끝·예고
    print('장면 %d · 문자열 %d · 글리프 %d · SATANIME +%d B (copyWrap %X · remap %X)'
          % (stat['scene'], stat['str'], stat['glyph'], len(exe) - (hookk.BASE - hookk.LOAD), sym['copyWrap'], sym['remap']))
    for w in stat['warn']:
        print('⚠️', w)
    if errs:
        print('⛔ 오류 %d건' % len(errs))
        for e in errs[:40]:
            print('  ', e)
        sys.exit(1)
    if write:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        iso.rebuild(EN_BIN, N_TRACK1, repl, OUT)
        print('→', OUT)


if __name__ == '__main__':
    main()
