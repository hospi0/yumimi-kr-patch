# -*- coding: utf-8 -*-
r"""유미미 장면 파일(ABLK / oneshot) 그림 풀기·다시 굽기 (2026-10-01) — libmd YmmScene·YmmSubscene·YmmCompress 이식
  장면 파일(영문 적용본) = [SUBS 블록] + 본체
  본체 ABLK: 'ABLK' + 색인 u32…[부장면 오프셋(최상위 니블 0) → PCM 오프셋들(0x80000000|…)]… + 끝(0xF0000000|전체) — 오프셋은 'ABLK' 뒤(+4) 기준
        oneshot: 'ABLK' 없이 부장면 하나
  부장면(주 덩어리) = 팔레트 4줄×16색 u16 · u16 타일 수 · u16 배경맵 수−1(0xFFFF=없음) · u16 물체맵 수 ·
        타일(8×8 4bpp 32 B, cmpYmmRleTypes) · 배경맵 80×64 u16 «타일 번호 그대로»(열 우선 생성, cmpYmmTilemap)×n ·
        물체맵(x,y,픽셀 w,h u16 + 번호 w×h) · 스크립트 머리(u16 크기+1, 0x80) + 스크립트 · 4 정렬 · (PCM 있으면) 0x800 정렬
        그 뒤 PCM(각 0x800 정렬)
  다시 굽기(영문 빌더 load 와 같게): 타일 0 = 빈칸, 배경맵들 → 물체맵들 순으로 열 우선 8×8 조각을 같은 것끼리 묶어 번호.
"""
import struct

BGW, BGH = 80, 64


# ---------------- 압축 ----------------
def dec_rle8(b, o):
    out = bytearray()
    while True:
        c = b[o]; o += 1
        cmd, n = c & 0xC0, (c & 0x3F) + 1
        if cmd == 0x00:
            out += bytes(n)
        elif cmd == 0x40:
            out += b'\xff' * n
        elif cmd == 0x80:
            if n == 1:
                return bytes(out), o
            out += bytes([b[o]]) * n; o += 1
        else:
            out += b[o:o + n]; o += n


def dec_ymm4(b, o):
    size = struct.unpack_from('>I', b, o)[0]; o += 4
    nyb = []; out = bytearray(); pend = None
    def nib():
        nonlocal o
        if nyb:
            return nyb.pop()
        v = b[o]; o += 1; nyb.append(v & 0xF); return v >> 4
    while True:
        fill = nib(); cmd = nib()
        n = ((((cmd & 7) << 4) | nib()) + 9) if cmd & 8 else cmd + 1
        for _ in range(n):
            if pend is None:
                pend = fill
            else:
                out.append(pend << 4 | fill); pend = None
                if len(out) >= size:
                    return bytes(out), o


def dec_rletypes(b, o):
    if b[o] == 0x80:
        return dec_ymm4(b, o + 1)
    return dec_rle8(b, o)


def cmp_rle8(src):
    out = bytearray(); ab = bytearray(); i = 0; n = len(src)
    def flush():
        if ab:
            out.append(0xC0 | (len(ab) - 1)); out.extend(ab); ab.clear()
    while i < n:
        v = src[i]; r = 1
        while i + r < n and r < 0x40 and src[i + r] == v:
            r += 1
        if r >= 2 and v in (0, 0xFF):
            flush(); out.append((0x00 if v == 0 else 0x40) | (r - 1))
        elif r >= 3:
            flush(); out += bytes([0x80 | (r - 1), v])
        else:
            for _ in range(r):
                ab.append(v)
                if len(ab) >= 0x40:
                    flush()
        i += r
    flush(); out.append(0x80)
    return bytes(out)


def cmp_ymm4(src):
    ny = []
    for v in src:
        ny += [v >> 4, v & 0xF]
    out = bytearray(struct.pack('>I', len(src))); w = []
    i = 0
    while i < len(ny):
        v = ny[i]; r = 1
        while i + r < len(ny) and r < 0x88 and ny[i + r] == v:
            r += 1
        w.append(v)
        c = r - 1
        if r >= 9:
            c -= 8; w += [0x8 | ((c & 0x70) >> 4), c & 0xF]
        else:
            w.append(c & 7)
        i += r
    if len(w) % 2:
        w.append(0)
    for k in range(0, len(w), 2):
        out.append(w[k] << 4 | w[k + 1])
    return bytes(out)


def cmp_rletypes(src):
    a = cmp_rle8(src); b = cmp_ymm4(src)
    return a if len(a) < len(b) + 1 else b'\x80' + b


def dec_tilemap(b, o):
    out = []; prev = 0
    while True:
        v = struct.unpack_from('>H', b, o)[0]; o += 2
        if v == 0xFFFF:
            return out, o
        c = v & 0xC000
        if c == 0:
            out.append(v)
        elif c == 0x4000:
            out += [prev] * ((v & 0xFF) + 1)
        else:
            n = b[o] + 1; o += 1; val = v & 0x3FFF
            if c == 0x8000:
                out += [val] * n; prev = val
            else:
                out += list(range(val, val + n))


def cmp_tilemap(words):
    out = bytearray(); prev = 0xFFFF; i = 0; n = len(words)
    while i < n:
        v = words[i]; r = 1
        while i + r < n and r < 0x100 and words[i + r] == v:
            r += 1
        if r == 1:
            k = 1
            while i + k < n and k < 0x100 and words[i + k] == v + k:
                k += 1
            if k >= 2:
                out += struct.pack('>HB', 0xC000 | v, k - 1); i += k; continue
            out += struct.pack('>H', v)
        elif v == prev:
            out += struct.pack('>H', 0x4000 | (r - 1))
        else:
            out += struct.pack('>HB', 0x8000 | v, r - 1); prev = v
        i += r
    out += b'\xff\xff'
    return bytes(out)


# ---------------- 부장면 ----------------
class Sub:
    def parse(self, b, o0):
        o = o0
        self.pal = b[o:o + 128]; o += 128
        nt, nb, no = struct.unpack_from('>HHH', b, o); o += 6
        raw, o = dec_rletypes(b, o)
        self.tiles = [raw[k * 32:(k + 1) * 32] for k in range(nt)]
        self.bg = []
        if nb != 0xFFFF:
            for _ in range(nb + 1):
                m, o = dec_tilemap(b, o); self.bg.append(m)
        self.obj = []
        for _ in range(no):
            x, y, pw, ph = struct.unpack_from('>HHHH', b, o); o += 8
            w, h = pw // 8, ph // 8
            ids = list(struct.unpack_from('>%dH' % (w * h), b, o)); o += 2 * w * h
            self.obj.append((x, y, w, h, ids))
        sz = struct.unpack_from('>H', b, o)[0]
        assert b[o + 2] == 0x80
        self.script = b[o:o + 3 + sz - 1]; o += 3 + sz - 1
        self.end = o
        return self

    # 타일 번호 격자 → 4bpp 값 이미지(행 우선 리스트)
    def image(self, ids, w, h, colmajor=True):
        W, H = w * 8, h * 8; px = bytearray(W * H)
        for k, t in enumerate(ids):
            tx, ty = (k // h, k % h) if colmajor else (k % w, k // w)
            p = self.tiles[t]
            for y in range(8):
                for x in range(4):
                    v = p[y * 4 + x]
                    px[(ty * 8 + y) * W + tx * 8 + x * 2] = v >> 4
                    px[(ty * 8 + y) * W + tx * 8 + x * 2 + 1] = v & 0xF
        return px

    def bg_image(self, i):
        return self.image(self.bg[i], BGW, BGH)

    def obj_image(self, i):
        x, y, w, h, ids = self.obj[i]
        return self.image(ids, w, h, colmajor=False)

    def colors(self):
        """팔레트 4줄 RGB — 저장값 << 1 = MD 색(0BGR, 각 3비트)"""
        out = []
        for k in range(64):
            v = struct.unpack_from('>H', self.pal, k * 2)[0] << 1
            r, g, bb = (v >> 1) & 7, (v >> 5) & 7, (v >> 9) & 7
            out.append((r * 36, g * 36, bb * 36))
        return out

    def rebuild(self, bg_imgs, obj_imgs):
        """값 이미지들 → 타일·맵 다시 만들기(영문 빌더 순서)"""
        tiles = [bytes(32)]; index = {bytes(32): 0}
        def grab(px, W, tx, ty):
            p = bytearray(32)
            for y in range(8):
                for x in range(4):
                    a = px[(ty * 8 + y) * W + tx * 8 + x * 2]; c = px[(ty * 8 + y) * W + tx * 8 + x * 2 + 1]
                    p[y * 4 + x] = a << 4 | c
            p = bytes(p)
            if p not in index:
                index[p] = len(tiles); tiles.append(p)
            return index[p]
        bg = []
        for px in bg_imgs:
            m = [0] * (BGW * BGH); k = 0
            for tx in range(BGW):
                for ty in range(BGH):
                    m[k] = grab(px, BGW * 8, tx, ty); k += 1
            bg.append(m)
        obj = []
        for (x, y, w, h, _), px in zip(self.obj, obj_imgs):
            ids = [0] * (w * h)
            for tx in range(w):                 # 영문 fromGrayscaleGraphic: 열 우선으로 만들지만 저장은 행 우선
                for ty in range(h):
                    ids[ty * w + tx] = grab(px, w * 8, tx, ty)
            obj.append((x, y, w, h, ids))
        self.tiles, self.bg, self.obj = tiles, bg, obj
        return self

    def sub1(self):
        o = bytearray(self.pal)
        o += struct.pack('>HHH', len(self.tiles), (len(self.bg) - 1) & 0xFFFF if self.bg else 0xFFFF, len(self.obj))
        o += cmp_rletypes(b''.join(self.tiles))
        for m in self.bg:
            o += cmp_tilemap(m)
        for x, y, w, h, ids in self.obj:
            o += struct.pack('>HHHH', x, y, w * 8, h * 8) + struct.pack('>%dH' % len(ids), *ids)
        return bytes(o)


# ---------------- 장면 파일 ----------------
def split_subs(f):
    """장면 파일 → (SUBS 블록, 본체)"""
    if f[:4] == b'SUBS':
        n = struct.unpack_from('>I', f, 4)[0]
        return f[:n], f[n:]
    return b'', f


def parse_body(body):
    """→ ('ablk', [(부장면 시작, [pcm 시작…])…], 끝) | ('one', …)"""
    if body[:4] != b'ABLK':
        return 'one', [(0, [])], len(body)
    ents = []; k = 4
    while True:
        v = struct.unpack_from('>I', body, k)[0]; k += 4
        if v & 0xF0000000 == 0xF0000000:
            end = (v & 0xFFFFFF) + 4; break
        if v & 0x80000000:
            ents[-1][1].append((v & 0xFFFFFF) + 4)
        else:
            ents.append(((v & 0xFFFFFF) + 4, []))
    return 'ablk', ents, end


def rebuild_body(body, newsubs):
    """newsubs = {부장면 번호: Sub(rebuild 된 것)} → 새 본체(색인 오프셋 다시 계산)"""
    kind, ents, end = parse_body(body)
    if kind == 'one':
        s = newsubs.get(0)
        if s is None:
            return body
        old = Sub().parse(body, 0)
        main = s.sub1() + s.script
        main += bytes((-len(main)) % 4)
        return main + body[old.end + ((-old.end) % 4):]
    starts = [e[0] for e in ents]
    parts = []
    for i, (st, pcms) in enumerate(ents):
        nxt = starts[i + 1] if i + 1 < len(starts) else end
        pend = pcms[0] if pcms else nxt
        if i in newsubs:
            old = Sub().parse(body, st)
            main = bytearray(newsubs[i].sub1() + newsubs[i].script)   # 선택지 창 폭 등 스크립트 수정 반영
            main += bytes((-len(main)) % 4)
            if pcms:
                main += bytes((-len(main)) % 0x800)
        else:
            main = bytearray(body[st:pend])
        pcm_rel = [(p - st - (pend - st), body[p:(pcms[j + 1] if j + 1 < len(pcms) else nxt)]) for j, p in enumerate(pcms)]
        parts.append((bytes(main), pcm_rel, body[pend:nxt]))
    n_idx = len(ents) + sum(len(e[1]) for e in ents) + 1
    idx = bytearray(); data = bytearray(); off = n_idx * 4
    for main, pcm_rel, tail in parts:
        idx += struct.pack('>I', off)
        for rel, _ in pcm_rel:
            idx += struct.pack('>I', 0x80000000 | (off + len(main) + rel))
        data += main + tail; off += len(main) + len(tail)
    idx += struct.pack('>I', 0xF0000000 | off)
    return b'ABLK' + bytes(idx) + bytes(data)
