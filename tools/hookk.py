# -*- coding: utf-8 -*-
r"""유미미 한글 자막 SH-2 코드 (2026-10-01, 2판) — 영문 패치 적용본 SATANIME.BIN 에 덧붙인다
  ① copyWrap  — 적재 함수(0x0605DACC)의 memcpy 호출 리터럴 0x0605DB58 을 이것으로.
       r4=dst(subtitleBlockData) r5=src(0x20200000) r6=블록 전체 크기.
       블록 끝 8 B 가 [u32 복사 크기]['HANG'] 이면: 글리프(복사 크기 ‥ 끝−8)를 GLY 로 복사, GB=GLY, 문자열 부분만 subtitleBlockData 로.
       ★1판은 글리프를 Low RAM(0x200000 영역)에서 바로 읽었는데, 큰 장면은 음성을 0x200000 에 다시 읽어 들여 글리프가 덮임
         (2026-10-01 실기: C102 에서 글자 깨짐) → 높은 RAM 으로 복사.
  ② remap     — assignRenderBufString 의 wordWrapString 호출 리터럴 0x06068AA4 를 이것으로.
       준비 버퍼를 제자리에서 2바이트 음절(A0+i/200, 1+i%200) → 1바이트 캐시 코드로. 새 칸마다 글리프(1bpp 28 B)를
       expand1 로 4bpp(몸 F·8방향 테두리 1·(+1,+1) 그림자 2)로 펼쳐 VDP1 글꼴 칸과 RAM 글꼴 원본 둘 다에 쓴다.
       캐시 칸: 아래 자리 0x51‥0x7E(46) · 위 자리 0x7F‥0x9B(29). 넘치면 마지막 칸 재사용(빌더가 막음). MACL 보존.
  ③ 음성 분할 읽기 섹터 수(0x0601AD6A «ADD #1,R5» → «ADD #7,R5»): 엔진은 색인 오프셋으로 섹터를 세는데 실제 데이터는
       SUBS 블록 크기만큼 뒤에 있어 꼬리가 덜 읽힌다(영문은 블록 < 0x800 이라 괜찮았음) → 6섹터(12 KB) 더 읽음. 블록 ≤ 0x3000.
"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, r'C:\claude\project\aww-kr-patch\tools')
import sh2asm, kfont

LOAD = 0x06012000
BASE = 0x06069398                   # 영문 SATANIME.BIN 끝
RAM_END = 0x0606C000
LIT_MEMCPY = 0x0605DB58             # 값 0x0601EA74
LIT_WW = 0x06068AA4                 # 값 0x06068ADE (wordWrapString)
MEMCPY = 0x0601EA74
WORDWRAP = 0x06068ADE
BUF_A = 0x06068860                  # subStringBufA (아래 자리)
FONT_RAM = 0x0605883C               # fontBitmap
FONT_VRAM = 0x25C1A800              # 비캐시 VDP1 0x1A800
WIDTH = 0x0606203C                  # 폭 표 160 B
KERN = 0x060620DC                   # 커닝 160×160
PCM_CNT = 0x0601AD6A                # ADD #1,R5 (7501)
PCM_EXTRA = 6
BLOCK_MAX = PCM_EXTRA * 0x800
POOL_A = (0x51, 46)
POOL_B = (0x7F, 29)
CACHE = range(0x51, 0x9C)
SPACE_W = 5
R = sh2asm.R


class A(sh2asm.Asm):
    def movl_disp(self, d, m, n):   self.w(0x5000 | R[n] << 8 | R[m] << 4 | d // 4)   # mov.l @(d,Rm),Rn
    def movl_store(self, m, n):     self.w(0x2002 | R[n] << 8 | R[m] << 4)             # mov.l Rm,@Rn
    def movw_r0n_store(self, m, n): self.w(0x0005 | R[n] << 8 | R[m] << 4)             # mov.w Rm,@(R0,Rn)
    def notr(self, m, n):           self.w(0x6007 | R[n] << 8 | R[m] << 4)
    def shll16(self, n):            self.w(0x4028 | R[n] << 8)
    def push(self, r):              self.movl_predec(r, 'r15')
    def pop(self, r):               self.movl_postinc('r15', r)
    def stsmacl_push(self):         self.w(0x4F12)
    def ldsmacl_pop(self):          self.w(0x4F16)
    def bsr(self, lab):             self.items.append(('bsr', lab))

    def assemble(self):
        marks = [k for k, it in enumerate(self.items) if it[0] == 'bsr']
        for k in marks:
            self.items[k] = ('bra', self.items[k][1])
        out, clen = super().assemble()
        out = bytearray(out); o = 0; ms = set(marks)
        for k, it in enumerate(self.items):
            if it[0] == 'label':
                continue
            if k in ms:
                out[o] = (out[o] & 0x0F) | 0xB0
            o += 2
        for k in marks:
            self.items[k] = ('bsr', self.items[k][1])
        return bytes(out), clen


def emit(a, EXPD):
    GB, SCR, GLY = EXPD['GB'], EXPD['SCR'], EXPD['GLY']
    a.defl('MEMCPY', MEMCPY); a.defl('WW', WORDWRAP); a.defl('HANG', 0x48414E47)
    a.defl('GB', GB); a.defl('SCR', SCR); a.defl('GLY', GLY); a.defl('BUFA', BUF_A)
    a.defl('VRAM', FONT_VRAM); a.defl('FONT', FONT_RAM); a.defw('K200', 200)

    # ---- ① copyWrap
    a.label('copyWrap')
    a.mov('r5', 'r1'); a.add('r6', 'r1'); a.addi(-8, 'r1')
    a.movl_disp(4, 'r1', 'r0')
    a.movl_pc('HANG', 'r2'); a.cmpeq('r0', 'r2'); a.bt('cw_yes')
    a.movi(0, 'r0'); a.movl_pc('GB', 'r2'); a.movl_store('r0', 'r2')
    a.movl_pc('MEMCPY', 'r0'); a.jmp('r0'); a.nop()
    a.label('cw_yes')
    a.stspr_predec('r15'); a.push('r4'); a.push('r5'); a.push('r1')
    a.movl_load('r1', 'r2')                          # r2 = 복사 크기
    a.mov('r1', 'r6'); a.sub('r5', 'r6'); a.sub('r2', 'r6')   # r6 = 글리프 바이트 = (끝−8) − src − 복사
    a.add('r2', 'r5')                                # r5 = src + 복사
    a.movl_pc('GLY', 'r4')
    a.movl_pc('MEMCPY', 'r0'); a.jsr('r0'); a.nop()
    a.movl_pc('GLY', 'r0'); a.movl_pc('GB', 'r2'); a.movl_store('r0', 'r2')
    a.pop('r1'); a.pop('r5'); a.pop('r4'); a.ldspr_postinc('r15')
    a.movl_load('r1', 'r6')                          # 문자열 부분만
    a.movl_pc('MEMCPY', 'r0'); a.jmp('r0'); a.nop()

    # ---- ② remap
    a.label('remap')
    a.stspr_predec('r15'); a.stsmacl_push()
    for r in ('r8', 'r9', 'r10', 'r11', 'r12', 'r13', 'r4', 'r5', 'r6'):
        a.push(r)
    a.movl_pc('GB', 'r0'); a.movl_load('r0', 'r13')
    a.tst('r13', 'r13'); a.bt('rm_done')
    a.movl_pc('BUFA', 'r0'); a.cmpeq('r5', 'r0'); a.bt('rm_a')
    a.movi(POOL_B[0], 'r12'); a.movi(POOL_B[1], 'r11'); a.bra('rm_go'); a.nop()
    a.label('rm_a')
    a.movi(POOL_A[0], 'r12'); a.movi(POOL_A[1], 'r11')
    a.label('rm_go')
    a.mov('r4', 'r8'); a.mov('r4', 'r9'); a.movi(0, 'r10')
    a.label('rm_loop')
    a.movb_postinc('r8', 'r0'); a.extub('r0', 'r0')
    a.tst('r0', 'r0'); a.bt('rm_end')
    a.mov('r0', 'r2'); a.addi(-128, 'r2'); a.addi(-32, 'r2')
    a.movi(64, 'r3'); a.cmphs('r3', 'r2'); a.bt('rm_plain')
    a.movb_postinc('r8', 'r1'); a.extub('r1', 'r1'); a.addi(-1, 'r1')
    a.movw_pc('K200', 'r3'); a.muluw('r3', 'r2'); a.sts_macl('r2'); a.add('r1', 'r2')
    a.movl_pc('SCR', 'r3'); a.movi(0, 'r1')
    a.label('rm_srch')
    a.cmpeq('r10', 'r1'); a.bt('rm_new')
    a.mov('r1', 'r0'); a.shll('r0'); a.movw_r0m('r3', 'r7'); a.extuw('r7', 'r7')
    a.cmpeq('r2', 'r7'); a.bt('rm_found')
    a.addi(1, 'r1'); a.bra('rm_srch'); a.nop()
    a.label('rm_new')
    a.cmphs('r11', 'r10'); a.bt('rm_full')
    a.mov('r10', 'r0'); a.shll('r0'); a.movw_r0n_store('r2', 'r3')
    a.mov('r10', 'r1'); a.addi(1, 'r10')
    # 글리프: src = GB + r2×28 · off = (r12+r1)×0x70
    a.movi(28, 'r0'); a.muluw('r0', 'r2'); a.sts_macl('r4'); a.add('r13', 'r4')
    a.mov('r12', 'r0'); a.add('r1', 'r0'); a.movi(0x70, 'r5'); a.muluw('r5', 'r0'); a.sts_macl('r5')
    a.movl_pc('VRAM', 'r6'); a.add('r5', 'r6')
    a.movl_pc('FONT', 'r7'); a.add('r5', 'r7')
    a.push('r1')
    a.bsr('expand1'); a.nop()
    a.pop('r1')
    a.label('rm_found')
    a.mov('r12', 'r0'); a.add('r1', 'r0'); a.movb_store('r0', 'r9'); a.addi(1, 'r9')
    a.bra('rm_loop'); a.nop()
    a.label('rm_full')
    a.mov('r11', 'r1'); a.addi(-1, 'r1'); a.bra('rm_found'); a.nop()
    a.label('rm_plain')
    a.movb_store('r0', 'r9'); a.addi(1, 'r9'); a.bra('rm_loop'); a.nop()
    a.label('rm_end')
    a.movb_store('r0', 'r9')
    a.label('rm_done')
    for r in ('r6', 'r5', 'r4', 'r13', 'r12', 'r11', 'r10', 'r9', 'r8'):
        a.pop(r)
    a.ldsmacl_pop(); a.ldspr_postinc('r15')
    a.movl_pc('WW', 'r0'); a.jmp('r0'); a.nop()

    # ---- expand1: r4 = 1bpp 28 B · r6 = VRAM · r7 = RAM 글꼴 → 4bpp 112 B 둘 다에
    #   줄마다 B(몸) · O = 8방향 넓힘 & ~B · S = (윗줄 solid >> 1) & ~solid, 픽셀 우선 F > 1 > 2
    a.label('expand1')
    a.stspr_predec('r15')                           # 안에서 rd16 을 bsr 로 부르므로 PR 보존
    for r in ('r8', 'r9', 'r10', 'r11', 'r12', 'r13'):
        a.push(r)
    a.movi(0, 'r9'); a.movi(0, 'r12')                # r9 = 윗줄 B · r12 = 윗줄 solid
    a.bsr('rd16'); a.nop(); a.mov('r0', 'r10')       # r10 = 이 줄
    a.bsr('rd16'); a.nop(); a.mov('r0', 'r11')       # r11 = 아랫줄
    a.movi(14, 'r8')
    a.label('ex_row')
    a.mov('r9', 'r0'); a.orr('r10', 'r0'); a.orr('r11', 'r0')
    a.mov('r0', 'r1'); a.shll('r1'); a.mov('r0', 'r2'); a.shlr('r2'); a.orr('r1', 'r0'); a.orr('r2', 'r0')
    a.extuw('r0', 'r0')
    a.notr('r10', 'r1'); a.andr('r1', 'r0'); a.mov('r0', 'r13')          # r13 = O
    a.mov('r10', 'r3'); a.orr('r13', 'r3')                                # r3 = solid
    a.mov('r12', 'r2'); a.shlr('r2'); a.notr('r3', 'r1'); a.andr('r1', 'r2')   # r2 = S
    a.mov('r3', 'r12')
    a.mov('r10', 'r5'); a.shll16('r5'); a.shll16('r13'); a.shll16('r2')
    a.movi(8, 'r3')
    a.label('ex_px')
    for sh_, dst in ((True, 'hi'), (False, 'lo')):
        lab = 'ex_%s' % dst
        a.movi(0, 'r0')
        a.shll('r2'); a.bf(lab + '1'); a.movi(2, 'r0'); a.label(lab + '1')
        a.shll('r13'); a.bf(lab + '2'); a.movi(1, 'r0'); a.label(lab + '2')
        a.shll('r5'); a.bf(lab + '3'); a.movi(15, 'r0'); a.label(lab + '3')
        if dst == 'hi':
            a.shll2('r0'); a.shll2('r0'); a.mov('r0', 'r1')
        else:
            a.orr('r1', 'r0')
    a.movb_store('r0', 'r6'); a.addi(1, 'r6'); a.movb_store('r0', 'r7'); a.addi(1, 'r7')
    a.dt('r3'); a.bf('ex_px')
    # 다음 줄
    a.mov('r10', 'r9'); a.mov('r11', 'r10')
    a.movi(0, 'r11')
    a.movi(2, 'r0'); a.cmphs('r0', 'r8'); a.bf('ex_nord')                 # r8 ≥ 2 → 남은 줄 있음(r8 = 이번 줄 포함 남은 수)
    a.movi(3, 'r0'); a.cmphs('r0', 'r8'); a.bf('ex_nord')
    a.bsr('rd16'); a.nop(); a.mov('r0', 'r11')
    a.label('ex_nord')
    a.dt('r8'); a.bf('ex_row')
    for r in ('r13', 'r12', 'r11', 'r10', 'r9', 'r8'):
        a.pop(r)
    a.ldspr_postinc('r15')
    a.rts(); a.nop()
    # rd16: r4 에서 u16 BE 읽기 → r0 (r1 씀)
    a.label('rd16')
    a.movb_postinc('r4', 'r0'); a.extub('r0', 'r0'); a.shll8('r0')
    a.movb_postinc('r4', 'r1'); a.extub('r1', 'r1'); a.orr('r1', 'r0')
    a.rts(); a.nop()


def build():
    code_len = 0x400
    for _ in range(3):
        EXPD = {}
        SCR = BASE + ((code_len + 3) & ~3)
        EXPD['SCR'] = SCR; EXPD['GB'] = SCR + 128; EXPD['GLY'] = SCR + 132
        a = A(BASE)
        a.shll8 = lambda n, a=a: a.w(0x4018 | R[n] << 8)
        emit(a, EXPD)
        code, clen = a.assemble()
        if len(code) == code_len:
            break
        code_len = len(code)
    blob = bytearray(code) + bytes((-len(code)) % 4)
    assert BASE + len(blob) == EXPD['SCR']
    blob += bytes(128 + 4)
    sym = {'copyWrap': a.labels['copyWrap'], 'remap': a.labels['remap'], 'expand1': a.labels['expand1'],
           'GB': EXPD['GB'], 'GLY': EXPD['GLY'], 'GLY_MAX': RAM_END - EXPD['GLY'], 'end': BASE + len(blob)}
    return bytes(blob), sym


def patch_exe(exe):
    exe = bytearray(exe)
    assert LOAD + len(exe) == BASE, hex(LOAD + len(exe))
    u32 = lambda a: struct.unpack_from('>I', exe, a - LOAD)[0]
    assert u32(LIT_MEMCPY) == MEMCPY and u32(LIT_WW) == WORDWRAP
    assert exe[PCM_CNT - LOAD:PCM_CNT - LOAD + 2] == b'\x75\x01'
    blob, sym = build()
    exe += blob
    struct.pack_into('>I', exe, LIT_MEMCPY - LOAD, sym['copyWrap'])
    struct.pack_into('>I', exe, LIT_WW - LOAD, sym['remap'])
    exe[PCM_CNT - LOAD + 1] = 1 + PCM_EXTRA
    for c in CACHE:
        exe[WIDTH - LOAD + c] = kfont.ADV
        for q in range(160):
            exe[KERN - LOAD + c * 160 + q] = 0
            exe[KERN - LOAD + q * 160 + c] = 0
    exe[WIDTH - LOAD + 0x4F] = SPACE_W
    return bytes(exe), sym


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    import sh2dis
    blob, sym = build()
    print({k: hex(v) for k, v in sym.items()}, len(blob))
    g = open(sh2dis.EXE, 'rb').read() + blob
    print('\n'.join(sh2dis.dis(sym['expand1'], 110, g)))
