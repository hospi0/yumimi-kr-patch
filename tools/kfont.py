# -*- coding: utf-8 -*-
r"""한글 자막 글리프 (2026-10-01) — 갈무리11 Bold 비트맵 → 16×14 칸, 영문 글꼴과 같은 칠 방식
  영문 글꼴 칠(4bpp): F = 흰 몸 · 1 = 8방향 테두리 · 2 = (몸∪테두리)를 (+1,+1) 민 그림자 · 0 = 투명
  장면 글리프는 2bpp(56 B)로 싣고 실행 중 4bpp(112 B)로 펼친다: 0→0 · 1→1 · 2→2 · 3→F
  2bpp 바이트 = p0<<6 | p1<<4 | p2<<2 | p3 (왼쪽 픽셀이 높은 비트)
"""
import os, sys
sys.path.insert(0, r'C:\claude\project\anearth-kr-patch\tools')
import bdf

FONT = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri11-Bold.bdf'
CW, CH = 16, 14
ADV = 12                        # 한글 전진폭(폭 표 0x51‥0x9B 에 씀)
_F = None


def font():
    global _F
    if _F is None:
        _F = bdf.Font(FONT)
    return _F


def cell(ch):
    """글자 → 16×14 값 격자(0 투명·1 테두리·2 그림자·3 몸)"""
    pts, adv = font().draw(ch, 0, 0)
    if not pts:
        raise ValueError('갈무리에 없는 글자 %r' % ch)
    # 갈무리11: 한글 y 3‥13 · x 0‥10 → 칸 (x+1, y−2): 테두리 1px 여유, 아래 그림자 1줄
    body = set((x + 1, y - 2) for x, y in pts)
    for x, y in body:
        assert 0 <= x < CW and 0 <= y < CH, ('칸 밖', ch, x, y)
    ol = set()
    for x, y in body:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                q = (x + dx, y + dy)
                if q not in body and 0 <= q[0] < CW and 0 <= q[1] < CH:
                    ol.add(q)
    solid = body | ol
    sh = set((x + 1, y + 1) for x, y in solid if x + 1 < CW and y + 1 < CH) - solid
    g = [[0] * CW for _ in range(CH)]
    for x, y in sh:
        g[y][x] = 2
    for x, y in ol:
        g[y][x] = 1
    for x, y in body:
        g[y][x] = 3
    return g


def pack2(g):
    out = bytearray()
    for row in g:
        for i in range(0, CW, 4):
            out.append(row[i] << 6 | row[i + 1] << 4 | row[i + 2] << 2 | row[i + 3])
    return bytes(out)


MAP = (0, 1, 2, 0xF)


def expand_table():
    """2bpp 바이트 → 4bpp 2바이트(u16 BE) × 256 = 512 B"""
    out = bytearray()
    for b in range(256):
        p = [(b >> s) & 3 for s in (6, 4, 2, 0)]
        out += bytes([MAP[p[0]] << 4 | MAP[p[1]], MAP[p[2]] << 4 | MAP[p[3]]])
    return bytes(out)


def expand(b2):
    t = expand_table(); out = bytearray()
    for b in b2:
        out += t[b * 2:b * 2 + 2]
    return bytes(out)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    for ch in sys.argv[1] if len(sys.argv) > 1 else '한글뷁':
        for row in cell(ch):
            print(''.join('.12F'[v] for v in row))
        print()
