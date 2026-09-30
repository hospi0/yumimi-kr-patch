# -*- coding: utf-8 -*-
r"""유미미 한글 자막 SH-2 코드 (2026-10-01) — 영문 패치 적용본 SATANIME.BIN 에 덧붙인다
  ① copyWrap  — 적재 함수(0x0605DACC)의 memcpy 호출 리터럴 0x0605DB58 을 이것으로.
       r4=dst(subtitleBlockData) r5=src(0x20200000) r6=블록 전체 크기.
       블록 끝 8 B 가 [u32 복사 크기]['HANG'] 이면 r6=복사 크기, 글리프 주소(GB) = src + 복사 크기. 아니면 GB=0. → memcpy 로.
       (장면 기준 주소는 영문 코드가 r12=전체 크기로 밀어 준다 — 그대로)
  ② remap     — assignRenderBufString 의 wordWrapString 호출 리터럴 0x06068AA4 를 이것으로.
       r4=준비 버퍼(경칭 거른 뒤) r5=대상 버퍼(A=아래 자리) r6=폭. 준비 버퍼를 제자리에서
       2바이트 음절(A0+i/200, 1+i%200) → 1바이트 캐시 코드로 바꾸고, 새 칸마다 글리프(2bpp 56 B → 4bpp 112 B)를
       VDP1 글꼴 칸과 RAM 글꼴 원본 둘 다에 쓴다(장면마다 글꼴을 다시 올려도 캐시 유지). 끝나면 wordWrapString 으로.
       캐시 칸: 아래 자리 0x51‥0x7E(46) · 위 자리 0x7F‥0x9B(29) — 기울임꼴 자리(글에서 안 씀). 넘치면 마지막 칸 재사용(빌더가 막음).
"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, r'C:\claude\project\aww-kr-patch\tools')
import sh2asm, kfont

LOAD = 0x06012000
BASE = 0x06069398                   # 영문 SATANIME.BIN 끝
LIT_MEMCPY = 0x0605DB58             # 값 0x0601EA74
LIT_WW = 0x06068AA4                 # 값 0x06068ADE (wordWrapString)
MEMCPY = 0x0601EA74
WORDWRAP = 0x06068ADE
BUF_A = 0x06068860                  # subStringBufA (아래 자리)
FONT_RAM = 0x0605883C               # fontBitmap
FONT_VRAM = 0x25C1A800              # 비캐시 VDP1 0x1A800
WIDTH = 0x0606203C                  # 폭 표 160 B
KERN = 0x060620DC                   # 커닝 160×160
POOL_A = (0x51, 46)
POOL_B = (0x7F, 29)
CACHE = range(0x51, 0x9C)
SPACE_W = 5


class A(sh2asm.Asm):
    def movl_disp(self, d, m, n):   self.w(0x5000 | sh2asm.R[n] << 8 | sh2asm.R[m] << 4 | d // 4)   # mov.l @(d,Rm),Rn
    def movl_store(self, m, n):     self.w(0x2002 | sh2asm.R[n] << 8 | sh2asm.R[m] << 4)             # mov.l Rm,@Rn
    def movw_r0n_store(self, m, n): self.w(0x0005 | sh2asm.R[n] << 8 | sh2asm.R[m] << 4)             # mov.w Rm,@(R0,Rn)
    def push(self, r):              self.movl_predec(r, 'r15')
    def pop(self, r):               self.movl_postinc('r15', r)
    def stsmacl_push(self):         self.w(0x4F12)                                                   # sts.l macl,@-r15
    def ldsmacl_pop(self):          self.w(0x4F16)                                                   # lds.l @r15+,macl


def build():
    """→ (blob, {'copyWrap':주소, 'remap':주소})"""
    a = A(BASE)
    # 데이터 주소(코드·풀 뒤): 조립 두 번(길이 확정 후 주소 결정)
    for _pass in range(2):
        a = A(BASE)
        code_len = getattr(build, '_len', 0x200)
        EXP = BASE + ((code_len + 3) & ~3)
        SCR = EXP + 512
        GB = SCR + 128
        a.defl('MEMCPY', MEMCPY); a.defl('WW', WORDWRAP); a.defl('HANG', 0x48414E47)
        a.defl('GB', GB); a.defl('SCR', SCR); a.defl('EXP', EXP); a.defl('BUFA', BUF_A)
        a.defl('VRAM', FONT_VRAM); a.defl('FONT', FONT_RAM); a.defw('K200', 200)

        # ---- ① copyWrap
        a.label('copyWrap')
        a.mov('r5', 'r1'); a.add('r6', 'r1'); a.addi(-8, 'r1')
        a.movl_disp(4, 'r1', 'r0')
        a.movl_pc('HANG', 'r2'); a.cmpeq('r0', 'r2'); a.bf('cw_no')
        a.movl_load('r1', 'r6')                      # 복사 크기
        a.mov('r5', 'r0'); a.add('r6', 'r0')
        a.movl_pc('GB', 'r2'); a.movl_store('r0', 'r2')
        a.movl_pc('MEMCPY', 'r0'); a.jmp('r0'); a.nop()
        a.label('cw_no')
        a.movi(0, 'r0'); a.movl_pc('GB', 'r2'); a.movl_store('r0', 'r2')
        a.movl_pc('MEMCPY', 'r0'); a.jmp('r0'); a.nop()

        # ---- ② remap
        a.label('remap')
        a.stspr_predec('r15'); a.stsmacl_push()          # ★수직귀선 안에서 돈다 — 끼어든 코드의 MACL 보존(영문 코드도 그렇게 함)
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
        a.mov('r0', 'r2'); a.addi(-128, 'r2'); a.addi(-32, 'r2')      # r2 = 코드 − 0xA0
        a.movi(64, 'r3'); a.cmphs('r3', 'r2'); a.bt('rm_plain')         # 0‥63 만 음절 첫 바이트
        a.movb_postinc('r8', 'r1'); a.extub('r1', 'r1'); a.addi(-1, 'r1')
        a.movw_pc('K200', 'r3'); a.muluw('r3', 'r2'); a.sts_macl('r2'); a.add('r1', 'r2')   # r2 = 글리프 번호
        a.movl_pc('SCR', 'r3'); a.movi(0, 'r1')
        a.label('rm_srch')
        a.cmpeq('r10', 'r1'); a.bt('rm_new')
        a.mov('r1', 'r0'); a.shll('r0'); a.movw_r0m('r3', 'r7'); a.extuw('r7', 'r7')
        a.cmpeq('r2', 'r7'); a.bt('rm_found')
        a.addi(1, 'r1'); a.bra('rm_srch'); a.nop()
        a.label('rm_new')
        a.cmphs('r11', 'r10'); a.bt('rm_full')                          # 칸 다 씀
        a.mov('r10', 'r0'); a.shll('r0'); a.movw_r0n_store('r2', 'r3')
        a.mov('r10', 'r1'); a.addi(1, 'r10')
        # 글리프 올리기: src = GB + r2×56 · off = (r12+r1)×0x70
        a.movi(56, 'r0'); a.muluw('r0', 'r2'); a.sts_macl('r4'); a.add('r13', 'r4')
        a.mov('r12', 'r0'); a.add('r1', 'r0'); a.movi(0x70, 'r5'); a.muluw('r5', 'r0'); a.sts_macl('r5')
        a.movl_pc('VRAM', 'r6'); a.add('r5', 'r6')
        a.movl_pc('FONT', 'r7'); a.add('r5', 'r7')
        a.movl_pc('EXP', 'r5'); a.movi(56, 'r3')
        a.label('rm_up')
        a.movb_postinc('r4', 'r0'); a.extub('r0', 'r0'); a.shll('r0'); a.movw_r0m('r5', 'r0')
        a.movw_store('r0', 'r6'); a.addi(2, 'r6'); a.movw_store('r0', 'r7'); a.addi(2, 'r7')
        a.dt('r3'); a.bf('rm_up')
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
        code, clen = a.assemble()
        build._len = len(code)
    blob = bytearray(code)
    blob += bytes((-len(blob)) % 4)
    assert BASE + len(blob) == EXP
    blob += kfont.expand_table() + bytes(128) + bytes(4)
    return bytes(blob), {'copyWrap': a.labels['copyWrap'], 'remap': a.labels['remap'], 'GB': GB, 'end': BASE + len(blob)}


def patch_exe(exe):
    """영문 SATANIME.BIN → 한글 코드 덧붙이고 리터럴·폭·커닝 패치"""
    exe = bytearray(exe)
    assert LOAD + len(exe) == BASE, hex(LOAD + len(exe))
    u32 = lambda a: struct.unpack_from('>I', exe, a - LOAD)[0]
    assert u32(LIT_MEMCPY) == MEMCPY and u32(LIT_WW) == WORDWRAP
    blob, sym = build()
    assert sym['end'] <= 0x0606C000, hex(sym['end'])
    exe += blob
    struct.pack_into('>I', exe, LIT_MEMCPY - LOAD, sym['copyWrap'])
    struct.pack_into('>I', exe, LIT_WW - LOAD, sym['remap'])
    for c in CACHE:
        exe[WIDTH - LOAD + c] = kfont.ADV
        for q in range(160):
            exe[KERN - LOAD + c * 160 + q] = 0
            exe[KERN - LOAD + q * 160 + c] = 0
    exe[WIDTH - LOAD + 0x4F] = SPACE_W
    return bytes(exe), sym


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.path.insert(0, HERE)
    import sh2dis
    blob, sym = build()
    print({k: hex(v) for k, v in sym.items()}, len(blob))
    g = open(sh2dis.EXE, 'rb').read() + blob
    print('\n'.join(sh2dis.dis(BASE, (sym['end'] - BASE - 644) // 2, g)))
