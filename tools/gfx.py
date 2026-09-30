# -*- coding: utf-8 -*-
r"""유미미 그림 글자 한글화 (2026-10-01) — 장면 그림(배경맵) 값 이미지에 한글을 그리고 다시 굽는다
  값 이미지 = 4bpp 색 번호(0‥15) 640×512(배경맵 80×64 타일). 글자 = 갈무리 비트맵 + 8방향 1px 테두리(원문과 같은 방식).
  작업 표(JOBS): 장면 파일·부장면·배경맵 번호 → 그리기 명령들
  python tools/gfx.py            → work/gfx/<장면>_bg<n>.png 미리보기(영문 색으로 칠함)
  from gfx import build_all; build_all(disc) → {'/C000A.CUT': 새 파일 바이트, …}
"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, r'C:\claude\project\anearth-kr-patch\tools')
sys.path.insert(0, r'C:\claude\project\cyberdoll-kr-patch\tools')
import bdf, scene, rules

FD = r'C:\claude\utils\font\Galmuri-v2.40.3'
_fonts = {}
W = 640


def font(name):
    if name not in _fonts:
        _fonts[name] = bdf.Font(os.path.join(FD, name + '.bdf'))
    return _fonts[name]


class Img:
    def __init__(self, px, w=640, h=512):
        self.px = bytearray(px); self.w = w; self.h = h

    def get(self, x, y):
        return self.px[y * self.w + x]

    def put(self, x, y, v):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y * self.w + x] = v

    def fill(self, x, y, w, h, v):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.put(xx, yy, v)

    def erase(self, x, y, w, h, colors, v):
        """영역 안에서 글자 색(colors)만 바탕색 v 로 — 손·테두리 등 다른 그림은 그대로"""
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                if 0 <= xx < self.w and 0 <= yy < self.h and self.px[yy * self.w + xx] in colors:
                    self.px[yy * self.w + xx] = v

    def copy(self, sx, sy, w, h, dx, dy, src=None):
        src = src or self
        blk = [[src.get(sx + i, sy + j) for i in range(w)] for j in range(h)]
        for j in range(h):
            for i in range(w):
                self.put(dx + i, dy + j, blk[j][i])

    def checker(self, x, y, w, h, v):
        """영문 ymm_erase_pixel_pattern: (x+y) 짝수 픽셀을 바탕색으로(흐린 항목)"""
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                if (xx + yy) % 2 == 0:
                    self.put(xx, yy, v)


def text_points(text, fname, spacing=0):
    F = font(fname); pts = []; x = 0
    for ch in text:
        p, x_end = F.draw(ch, x, 0)                 # bdf.draw 는 «끝 x» 를 돌려준다
        pts += p; x = x_end + spacing
    return pts, x - spacing


def text_size(text, fname, spacing=0):
    pts, adv = text_points(text, fname, spacing)
    xs = [a for a, _ in pts]; ys = [b for _, b in pts]
    return max(xs) - min(xs) + 1 + 2, max(ys) - min(ys) + 1 + 2      # 테두리 포함


def draw(img, text, x, y, fill, outline, fname='Galmuri11-Bold', spacing=0, align='left', box_w=None):
    """(x,y) = 테두리 포함 왼쪽 위. align='center' 면 box_w 안 가운데."""
    pts, adv = text_points(text, fname, spacing)
    xs = [a for a, _ in pts]; ys = [b for _, b in pts]
    ox = x + 1 - min(xs); oy = y + 1 - min(ys)
    if align == 'center':
        tw = max(xs) - min(xs) + 1 + 2
        ox += (box_w - tw) // 2
    elif align == 'right':
        tw = max(xs) - min(xs) + 1 + 2
        ox += box_w - tw
    body = set((a + ox, b + oy) for a, b in pts)
    for a, b in body:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if (a + dx, b + dy) not in body:
                    img.put(a + dx, b + dy, outline)
    for a, b in body:
        img.put(a, b, fill)
    return max(xs) - min(xs) + 1 + 2


# ---------------- 작업 ----------------
def job_mainmenu(bgs):
    """C000A.CUT 부장면 0: bg1 메뉴 · bg2 흐린 메뉴(이어하기·다시 보기) · bg4 내장/카트리지 고르기 · 모든 판의 (336,224) 라벨"""
    BG, OL, FG = 3, 5, 2
    b1 = bgs[1]
    items = ['새 게임', '이어하기', '다시 보기', '보너스']
    for k, t in enumerate(items):
        y0 = 80 + 24 * k
        b1.erase(40, y0, 142, 24, (FG, OL), BG)     # 판 안쪽(x 36‥182)의 글자 색만 지움
        draw(b1, t, 78, y0 + 5, FG, OL)
    # 라벨(40×16 두 칸): 내장 / 카트리지
    def labels(img):
        img.fill(336, 224, 80, 16, BG)
        draw(img, '내장', 336, 225, FG, OL, 'Galmuri11-Condensed', align='center', box_w=40)
        draw(img, '카트리지', 376, 225, FG, OL, 'Galmuri11-Condensed', align='center', box_w=40)
    labels(b1)
    b2 = bgs[2]
    b2.erase(40, 80, 142, 96, (FG, OL), BG)
    b2.copy(72, 80, 100, 96, 72, 80, src=b1)
    b2.checker(72, 104, 100, 48, BG)                 # 이어하기·다시 보기 흐리게(저장 데이터 없을 때)
    labels(b2)
    labels(bgs[3])
    b4 = bgs[4]
    b4.erase(40, 76, 142, 24, (FG, OL), BG)
    b4.copy(336, 224, 40, 16, 64, 80, src=b1)
    b4.copy(376, 224, 40, 16, 128, 80, src=b1)
    labels(b4)


def _warning(img, BG, OL, FG):
    img.erase(80, 26, 51, 13, (OL, FG), BG)
    draw(img, '주의', 80, 26, FG, OL, 'Galmuri11-Condensed', align='center', box_w=51)


def _lines(img, y0, lines, BG, OL, FG, x=16):
    for k, t in enumerate(lines):
        if isinstance(t, tuple):                     # (왼쪽 글, 오른쪽 끝 x, 뒤 글, 뒤 시작 x) — 라벨 자리 비우기
            a, ax, b, bx = t
            wa = text_size(a, 'Galmuri11-Condensed')[0]
            draw(img, a, ax - wa + 1, y0 + 16 * k, FG, OL, 'Galmuri11-Condensed')
            draw(img, b, bx, y0 + 16 * k, FG, OL, 'Galmuri11-Condensed')
        else:
            w = draw(img, rules.squeeze(t), x, y0 + 16 * k, FG, OL, 'Galmuri11-Condensed')
            assert x + w <= 183, ('줄 넘침', t, x + w)


def job_format(bgs):
    """C000C.CUT bg1: 백업 RAM 포맷 안내 — 넷째 줄 (95,102) 40×16 에 «내장/카트리지» 라벨 스프라이트가 얹힘"""
    BG, OL, FG = 3, 1, 2
    b = bgs[1]
    _warning(b, BG, OL, FG)
    b.erase(16, 54, 180, 112, (OL, FG), BG); b.erase(16, 166, 167, 16, (OL, FG), BG)   # 판 오른쪽 끝(x 195)까지, 손(아래 오른쪽)은 피함
    _lines(b, 55, ['「유미미 믹스」의 데이터를', '저장하려면 백업 RAM을', '완전히 지워야(포맷) 합니다.',
                   ('지울 곳: 백업 RAM(', 94, ')', 135), 'START 버튼을 누르면', '강제로 지웁니다(포맷).'], BG, OL, FG)


def job_spacelow(bgs):
    """C000B.CUT bg1: 백업 RAM 용량 부족 안내"""
    BG, OL, FG = 3, 1, 2
    b = bgs[1]
    _warning(b, BG, OL, FG)
    b.erase(16, 40, 180, 126, (OL, FG), BG); b.erase(16, 166, 167, 16, (OL, FG), BG)
    _lines(b, 41, ['백업 RAM의 빈 공간이 부족합니다.', '저장 데이터 관리 화면에서', '데이터를 옮기거나 지워서',
                   '빈 블록을 5개 이상 만들어 주세요.', 'START 버튼을 누르면', '「유미미 믹스」를 억지로 시작할 수',
                   '있지만, 저장은 할 수 없습니다.'], BG, OL, FG)


def job_advert(bgs):
    """C021.DAT bg1: 게임 아츠 주소 판(흰 판 x29‥197 · y17‥202, 파랑 몸 9 · 테두리 a)"""
    BG, OL, FG = 0xF, 0xA, 9
    b = bgs[1]
    b.erase(29, 17, 169, 186, (OL, FG), BG)
    lines = [('〒171', 'l'), ('도쿄도 도시마구', 'l'), ('미나미이케부쿠로', 'l'), ('2-9-9', 'r'),
             ('이케부쿠로 화이트', 'l'), ('빌딩 1호관 7층', 'l'), ('보내실 곳:', 'c'), ('게임 아츠', 'c')]
    for k, (t, al) in enumerate(lines):
        draw(b, t, 34, 21 + 22 * k, FG, OL, 'Galmuri14',
             align={'l': 'left', 'r': 'right', 'c': 'center'}[al], box_w=158)


JOBS = [
    ('/C000A.CUT', 0, job_mainmenu),
    ('/C000C.CUT', 0, job_format),
    ('/C000B.CUT', 0, job_spacelow),
    ('/C021.DAT', 0, job_advert),
]


LOGO_FONT = r'C:\claude\utils\font\nanum-gothic\NanumGothicBold.ttf'   # ⛔구기는 «유» 를 ㅇ+ㄱㅣ 로 그려 잘려 보임(사용자)


def _bg_bands(img, x0, x1, y0, y1, bands=(10, 11, 12, 13)):
    """배경 하늘 띠(색 10→11→12→13, 위에서 아래)를 글자 없이 다시 그림 — 띠 경계는 보이는 열에서 재고 가려진 열은 선형 보간"""
    bounds = []
    for a, b in zip(bands, bands[1:]):
        known = {}
        for x in range(x0, x1):
            for y in range(y0, y1 - 1):
                if img.get(x, y) == a and img.get(x, y + 1) == b:
                    known[x] = y + 1; break
        xs = sorted(known)
        row = {}
        for x in range(x0, x1):
            if x in known:
                row[x] = known[x]; continue
            lo = max([k for k in xs if k < x], default=None); hi = min([k for k in xs if k > x], default=None)
            if lo is None:
                row[x] = known[hi]
            elif hi is None:
                row[x] = known[lo]
            else:
                row[x] = round(known[lo] + (known[hi] - known[lo]) * (x - lo) / (hi - lo))
        bounds.append(row)
    for x in range(x0, x1):
        for y in range(y0, y1):
            k = sum(1 for r in bounds if y >= r[x])
            img.put(x, y, bands[k])


def _blob_letter(ch, size, angle):
    """둥근 굵은 글자 모양(제목 로고용): 나눔고딕 Bold 흐렸다가 낮은 문턱으로 잘라 «둥글게 부풀린» 1bit 마스크"""
    from PIL import Image as PI, ImageDraw, ImageFont, ImageFilter
    F = ImageFont.truetype(LOGO_FONT, size)
    pad = size // 2                                   # 여유 크게(돌리거나 부풀릴 때 모서리 잘림 방지)
    g = PI.new('L', (size + pad * 2, size + pad * 2), 0)
    d = ImageDraw.Draw(g)
    l, t, r, b = d.textbbox((0, 0), ch, font=F)
    d.text(((g.width - (r - l)) // 2 - l, (g.height - (b - t)) // 2 - t), ch, font=F, fill=255)
    g = g.filter(ImageFilter.GaussianBlur(3.0))
    g = g.rotate(angle, resample=PI.BICUBIC, expand=True)
    return set((x, y) for y in range(g.height) for x in range(g.width) if g.getpixel((x, y)) > 44), g.width, g.height


def _disk(r):
    return [(dx, dy) for dx in range(-r, r + 1) for dy in range(-r, r + 1) if dx * dx + dy * dy <= r * r + r]


def job_title(bgs):
    """OP_YUMI.DAT 부장면 0 bg0 오른쪽 반(320‥640 × 0‥224): 제목 로고 «유미미 믹스»(원본 ゆみみみ みっくす 처럼 글자마다 색)
       + 저작권 줄 «©1992,1995 타케모토 이즈미/GAME ARTS»"""
    b = bgs[0]
    X0 = 320
    cat = {(x, y): b.get(x, y) for y in range(70, 117) for x in range(462, 516)
           if b.get(x, y) in (1, 7, 14, 15) and (x - 488) ** 2 + (y - 93) ** 2 <= 19 * 19}   # 동그라미 안·방울 색만(옆 글자 조각 빼기)
    _bg_bands(b, X0, 640, 0, 224)
    OL, EDGE = 1, 14
    # (글자, 색, 가운데 x, 가운데 y, 크기, 기울기)
    letters = [('유', 6, X0 + 88, 52, 74, 8), ('미', 4, X0 + 160, 46, 74, -5), ('미', 5, X0 + 232, 52, 74, 6),
               ('믹', 7, X0 + 124, 138, 74, -6), ('스', 8, X0 + 196, 140, 74, 5)]
    for ch, col, cx, cy, size, ang in letters:
        m, w, h = _blob_letter(ch, size, ang)
        ox, oy = cx - w // 2, cy - h // 2
        body = set((x + ox, y + oy) for x, y in m)
        dark = set()
        for x, y in body:
            for dx, dy in _disk(3):
                dark.add((x + dx, y + dy)); dark.add((x + dx, y + dy + 3))     # 3px 테두리 + 아래로 3px 그림자
        dark -= body
        solid = body | dark
        edge = set()
        for x, y in solid:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if (x + dx, y + dy) not in solid:
                    edge.add((x + dx, y + dy))
        for x, y in edge:
            if X0 <= x < 640:
                b.put(x, y, EDGE)
        for x, y in dark:
            if X0 <= x < 640:
                b.put(x, y, OL)
        for x, y in body:
            if X0 <= x < 640:
                b.put(x, y, col)
    # 고양이 방울: 윗줄과 아랫줄 사이 한가운데(영문판처럼) — 사용자 2026-10-01
    dx, dy = (X0 + 160) - 488, 94 - 93
    for (x, y), v in cat.items():
        b.put(x + dx, y + dy, v)
    # 저작권 줄: 몸 f(검정) · 오른쪽 아래 그림자 2
    b.erase(X0, 176, 320, 40, (0xF, 2), 13)
    pts, _ = text_points(rules.squeeze('©1992,1995 타케모토 이즈미/GAME ARTS'), 'Galmuri11-Bold')
    xs = [a for a, _ in pts]; ys = [c for _, c in pts]
    ox = X0 + (320 - (max(xs) - min(xs) + 1)) // 2 - min(xs); oy = 184 - min(ys)
    body = set((a + ox, c + oy) for a, c in pts)
    for a, c in body:
        if (a + 1, c + 1) not in body:
            b.put(a + 1, c + 1, 2)
    for a, c in body:
        b.put(a, c, 0xF)


JOBS.append(('/OP_YUMI.DAT', 0, job_title))


# ---------------- SATANIME 안 그림 ----------------
LOAD = 0x06012000
PAUSE_GFX = 0x0605883C + 0x4600      # fontBitmap 뒤: 경칭·자막·간판·장면넘기기·설명·ON·OFF·커서 (4bpp 가로줄 순)
PAUSE_ITEMS = [('hon', 64, 10), ('sub', 56, 10), ('sig', 80, 10), ('skip', 96, 10), ('desc', 152, 10),
               ('on', 16, 10), ('off', 24, 10), ('cur', 16, 16)]
IFACE = 0x060200FA                   # interface_block + 0x800: 304×16, 8px 열마다 위·아래 타일(32 B) 2개


def _lin_draw(w, h, text, fname, align, shadow=True):
    """일시정지 메뉴 글: 몸 F · (+1,+1) 그림자 1(10줄 안에 테두리까지는 안 들어감 — 갈무리9 몸 9줄)"""
    img = Img(bytes(w * h), w, h)
    pts, _ = text_points(text, fname)
    xs = [a for a, _ in pts]; ys = [b for _, b in pts]
    tw = max(xs) - min(xs) + 1 + (1 if shadow else 0)
    ox = {'left': 0, 'right': w - tw, 'center': (w - tw) // 2}[align] - min(xs); oy = -min(ys)
    assert tw <= w and max(ys) - min(ys) + 1 + (1 if shadow else 0) <= h, ('칸 넘침', text)
    body = set((a + ox, b + oy) for a, b in pts)
    if shadow:
        for a, b in body:
            if (a + 1, b + 1) not in body:
                img.put(a + 1, b + 1, 1)
    for a, b in body:
        img.put(a, b, 0xF)
    return img


def _pack_lin(img):
    return bytes(img.px[i] << 4 | img.px[i + 1] for i in range(0, len(img.px), 2))


def patch_pause(exe):
    """일시정지 메뉴: 글 그림 한글 + 경칭 줄 숨기기(사용자 2026-10-01 «경칭x») — 나머지 줄을 한 줄(12px)씩 위로"""
    exe = bytearray(exe)
    texts = {'sub': ('자막', 'right'), 'sig': ('간판·카라오케', 'right'), 'skip': ('장면 넘기기', 'right'),
             'desc': ('(선택지 없는 장면에서)', 'left'), 'on': ('켬', 'center'), 'off': ('끔', 'center')}
    o = PAUSE_GFX - LOAD
    for n, w, h in PAUSE_ITEMS:
        size = w * h // 2
        if n == 'hon':
            exe[o:o + size] = bytes(size)
        elif n in texts:
            t, al = texts[n]
            exe[o:o + size] = _pack_lin(_lin_draw(w, h, t, 'Galmuri9', al))
        o += size
    # 코드: renderPauseMenu(0x06060170‥) — 경칭(0번) 그리기는 화면 밖(y −32), 1‥3번·설명 y −12, 선택 범위 1‥3
    lo, hi = 0x06060170 - LOAD, 0x06060600 - LOAD
    n_imm = n_lit = 0; seen = set()
    for a in range(lo, hi, 2):
        w_ = int.from_bytes(exe[a:a + 2], 'big')
        if w_ in (0xE77C, 0xE77A):                   # mov #124/#122,r7 = 0번 줄 y
            exe[a:a + 2] = (0xE7E0).to_bytes(2, 'big'); n_imm += 1
        elif w_ >> 8 == 0x97:                        # mov.w @(disp,pc),r7
            la = a + 4 + (w_ & 0xFF) * 2
            if la in seen:
                continue
            v = int.from_bytes(exe[la:la + 2], 'big')
            if v in (134, 136, 146, 148, 158, 160, 172):
                exe[la:la + 2] = (v - 12).to_bytes(2, 'big'); n_lit += 1; seen.add(la)
    assert n_imm == 4 and n_lit == 10, (n_imm, n_lit)      # 라벨 풀 4 + 1번(y·커서) 2 + 2·3번 4
    def put16(addr, old, new):
        a = addr - LOAD
        assert int.from_bytes(exe[a:a + 2], 'big') == old, hex(addr)
        exe[a:a + 2] = new.to_bytes(2, 'big')
    put16(0x06060190, 0xE200, 0xE201)               # 위: 1 이하에서 감싸기 → 3
    put16(0x060601B4, 0xE1FF, 0xE100)               # 아래: 3 에서 감싸기 → 1
    put16(0x0606058E, 0x0000, 0x0001)               # pauseMenu_selectedIndex 처음 1
    return bytes(exe)


def patch_iface(exe):
    """게임 안 인터페이스 줄(저장/불러오기·내장/카트리지·PAUSE): 바탕 f · 글 e(테두리 없음)"""
    exe = bytearray(exe); o = IFACE - LOAD
    W, H = 304, 16
    img = Img(bytes(W * H), W, H)
    for c in range(38):
        for t in range(2):
            p = exe[o + (c * 2 + t) * 32:o + (c * 2 + t) * 32 + 32]
            for y in range(8):
                for x in range(4):
                    v = p[y * 4 + x]
                    img.put(c * 8 + x * 2, t * 8 + y, v >> 4); img.put(c * 8 + x * 2 + 1, t * 8 + y, v & 15)
    F, E = 0xF, 0xE
    def slot(x0, text, keep=0):
        img.fill(x0 + keep, 0, 40 - keep, 16, F)
        pts, _ = text_points(text, 'Galmuri11-Condensed')
        xs = [a for a, _ in pts]; ys = [b for _, b in pts]
        ox = x0 + keep + 1 - min(xs); oy = 2 - min(ys)
        assert max(xs) + ox < x0 + 40, ('칸 넘침', text)
        for a, b in pts:
            img.put(a + ox, b + oy, E)
    slot(96, '저장'); slot(136, '불러오기'); slot(176, '내장', keep=5)
    img.copy(176, 0, 5, 16, 216, 0)                  # ▶ 는 «내장» 칸 것을 복사(영문 Internal 꼬리가 216 칸에 걸쳐 있음)
    slot(216, '카트리지', keep=5)
    # PAUSE(256‥303): 투명 바탕 0 · 몸 f · 테두리 e
    img.fill(256, 0, 48, 16, 0)
    draw(img, '일시정지', 256, 1, F, E, 'Galmuri11-Condensed', align='center', box_w=48)
    for c in range(38):
        for t in range(2):
            p = bytearray(32)
            for y in range(8):
                for x in range(4):
                    p[y * 4 + x] = img.get(c * 8 + x * 2, t * 8 + y) << 4 | img.get(c * 8 + x * 2 + 1, t * 8 + y)
            exe[o + (c * 2 + t) * 32:o + (c * 2 + t) * 32 + 32] = p
    return bytes(exe), img


# ---------------- 퍼즐(MINISND.ABK 끝, 영문 패치가 붙인 8bpp 타일+맵) ----------------
PUZ = [('title', 0x49AFC, 283), ('kabe0', 0x4EA7C, 44), ('osimai', 0x4FE3C, 108), ('tease', 0x521FC, 161)]
TTF = r'C:\claude\utils\font\nanum-gothic\NanumGothicExtraBold.ttf'


def _puz_dec(m, o, N):
    tiles = [m[o + k * 64:o + k * 64 + 64] for k in range(N)]
    mp = struct.unpack_from('>1120H', m, o + N * 64)
    img = Img(bytes(320 * 224), 320, 224)
    for k, t in enumerate(mp):
        tx, ty = k % 40, k // 40
        for y in range(8):
            img.px[(ty * 8 + y) * 320 + tx * 8:(ty * 8 + y) * 320 + tx * 8 + 8] = tiles[t][y * 8:y * 8 + 8]
    return img


def _puz_enc(img, N):
    """영문 sat_8bpp_tileconv 와 같은 순서(행 우선, 같은 타일 묶음) — 타일 수는 원래 N 에 맞춰 0 으로 채움(코드 속 크기 그대로)"""
    tiles = []; index = {}; mp = []
    for j in range(28):
        for i in range(40):
            t = bytes(img.px[(j * 8 + y) * 320 + i * 8 + x] for y in range(8) for x in range(8))
            if t not in index:
                index[t] = len(tiles); tiles.append(t)
            mp.append(index[t])
    assert len(tiles) <= N, ('타일 넘침', len(tiles), N)
    tiles += [bytes(64)] * (N - len(tiles))
    return b''.join(tiles) + struct.pack('>1120H', *mp)


def _ttf_draw(img, text, cx, cy, size, fill, outline, ow=2):
    from PIL import Image as PI, ImageDraw, ImageFont
    F = ImageFont.truetype(TTF, size)
    l, t, r, b = ImageDraw.Draw(PI.new('1', (1, 1))).textbbox((0, 0), text, font=F)
    w, h = r - l, b - t
    g = PI.new('1', (w + 2 * ow + 2, h + 2 * ow + 2)); d = ImageDraw.Draw(g)
    d.fontmode = '1'; d.text((ow + 1 - l, ow + 1 - t), text, font=F, fill=1)
    body = set((x, y) for y in range(g.height) for x in range(g.width) if g.getpixel((x, y)))
    ox, oy = cx - g.width // 2, cy - g.height // 2
    for x, y in body:
        for dx in range(-ow, ow + 1):
            for dy in range(-ow, ow + 1):
                if (x + dx, y + dy) not in body:
                    img.put(ox + x + dx, oy + y + dy, outline)
    for x, y in body:
        img.put(ox + x, oy + y, fill)


def patch_minisnd(m):
    """퍼즐: 끝(THE END) · 예고 화면 글 — 로고(YUMIMI PUZZLE)는 사용자 판단 전이라 그대로"""
    m = bytearray(m)
    for n, o, N in PUZ:
        if n == 'osimai':
            img = _puz_dec(m, o, N)
            img.fill(0, 0, 320, 80, 0)
            _ttf_draw(img, '끝', 104, 44, 40, 1, 5)
        elif n == 'tease':
            img = _puz_dec(m, o, N)
            img.fill(0, 148, 320, 70, 0)
            for k, t in enumerate(['타케모토 월드 신작, 제작 개시!', '기대해 주세요!']):
                draw(img, rules.squeeze(t), 10, 154 + 28 * k, 3, 1, 'Galmuri14', align='right', box_w=296)
        else:
            continue
        m[o:o + N * 64 + 2240] = _puz_enc(img, N)
    return bytes(m)


def patch_exe(exe):
    exe = patch_pause(exe)
    exe, _ = patch_iface(exe)
    return exe


def run_job(D, name, sub, fn, f=None):
    f = f if f is not None else D.read(name)
    sb, body = scene.split_subs(f)
    kind, ents, end = scene.parse_body(body)
    s = scene.Sub().parse(body, ents[sub][0])
    bgs = [Img(s.bg_image(k)) for k in range(len(s.bg))]
    objs = [bytes(s.obj_image(k)) for k in range(len(s.obj))]
    fn(bgs)
    s.rebuild([bytes(b.px) for b in bgs], objs)
    return sb + scene.rebuild_body(body, {sub: s}), bgs


def build_all(D, repl=None):
    """repl(이미 자막을 바꾼 파일)이 있으면 그 위에 그림을 고친다"""
    out = {}
    for name, sub, fn in JOBS:
        out[name] = run_job(D, name, sub, fn, (repl or {}).get(name))[0]
    return out


def preview(D):
    """영문 png 색을 빌려 칠한 미리보기(값→색 대응은 영문 그림 픽셀에서 뽑음)"""
    from PIL import Image
    os.makedirs(os.path.join(ROOT, 'work', 'gfx'), exist_ok=True)
    for name, sub, fn in JOBS:
        new, bgs = run_job(D, name, sub, fn)
        f = D.read(name); sb, body = scene.split_subs(f); k_, ents, e_ = scene.parse_body(body)
        s = scene.Sub().parse(body, ents[sub][0])
        pal = {}
        ref = {'/C000A.CUT': 'mainmenu_1', '/C000C.CUT': 'backup_format', '/C000B.CUT': 'backup_spacelow', '/C021.DAT': 'advertise', '/OP_YUMI.DAT': None}.get(name)
        if ref:
            im = Image.open(os.path.join(ROOT, 'work', 'en', 'yumimiremixtools', 'yumimi', 'rsrc', ref + '.png')).convert('RGB')
            px = s.bg_image(1)
            for y in range(0, 512, 3):
                for x in range(0, 640, 3):
                    pal.setdefault(px[y * 640 + x], im.getpixel((x, y)))
        for k, b in enumerate(bgs):
            o = Image.new('RGB', (640, 512))
            o.putdata([pal.get(v, (v * 17,) * 3) for v in b.px])
            o.crop((0, 0, 440, 256)).resize((880, 512), Image.NEAREST).save(
                os.path.join(ROOT, 'work', 'gfx', '%s_bg%d.png' % (name.strip('/').split('.')[0], k)))


if __name__ == '__main__':
    import disc
    sys.stdout.reconfigure(encoding='utf-8')
    preview(disc.Disc(os.path.join(ROOT, 'work', 'en', 'en_full.bin')))
    print('ok')
