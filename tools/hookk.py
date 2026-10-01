# -*- coding: utf-8 -*-
r"""유미미 한글 자막 SH-2 코드 (2026-10-01, 3판) — 영문 패치 적용본 SATANIME.BIN 에 덧붙인다
  ① loadK     — 부팅 때 YUMISND.BIN 적재 함수(0x060124D4)의 «파일 읽기» 호출 리터럴 0x06012540(값 0x06019EF0)을 이것으로.
       YUMISND.BIN 을 원래대로 읽은 뒤, 같은 함수로 BIB.TXT(★게임이 안 읽는 ISO 서지 파일 — 내용을 한글 글리프 전체로 바꿈)를
       높은 RAM KBASE(0x060F0000, 아무도 안 쓰는 곳 — 장면 상태 5개 모두 0)로 읽는다. 글리프 = 게임 전체 음절 하나씩(2bpp 56 B).
       ★2판은 장면마다 글리프를 SUBS 블록 뒤에 붙여 장면 파일 앞머리가 영문판보다 커졌고, 그 때문에 음성 분할 읽기 장면(30개)에서
         섹터 보정(pcmExtra)·12 KB 덧붙임이 필요했음 → C104·C102 멈춤(2026-10-01 실기 4회). 3판은 장면 파일 배치를 영문판과 똑같이 둔다
         (분할 장면은 SUBS 크기도 영문과 같게 0 으로 채움) — 영문 패치의 적재 코드는 손대지 않음.
  ② remap     — assignRenderBufString 의 wordWrapString 호출 리터럴 0x06068AA4 를 이것으로.
       준비 버퍼를 제자리에서 2바이트 음절(A0+i/200, 1+i%200) → 1바이트 캐시 코드로. 새 칸마다 글리프(2bpp 56 B)를
       표 조회로 4bpp 로 펼쳐(2bpp: 0 투명·1 테두리·2 그림자·3→F) VDP1 글꼴 칸과 RAM 글꼴 원본 둘 다에 쓴다.
       캐시 칸: 아래 자리 0x51‥0x7E(46) · 위 자리 0x7F‥0x9B(29). 넘치면 마지막 칸 재사용(빌더가 막음). MACL 보존.
  음절 코드 = 게임 전체 번호 i → 2바이트 A0+i/200, 1+i%200 (영문 글꼴 표는 0xA0‥0xDF 를 안 씀 — 영문 문자열은 remap 을 그냥 지나감).
"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, r'C:\claude\project\aww-kr-patch\tools')
import sh2asm, kfont

LOAD = 0x06012000
BASE = 0x06069398                   # 영문 SATANIME.BIN 끝
RAM_END = 0x0606C000
LIT_LOADSND = 0x06012540            # 값 0x06019EF0 (YUMISND.BIN 읽기 — 0x060124E8 에서만 씀)
LOADFILE = 0x06019EF0               # (r4=이름 버퍼, r5=목적지) 파일 통째 읽기
STRCPY = 0x0601EDB4                 # (r4=dst, r5=src)
NAMEBUF = 0x06032DDC
KBASE = 0x060F0000                  # 한글 글리프 전체(부팅 때 한 번)
KEND = 0x060FD000                   # 스택(0x06100000 아래, 상태 5개 관측 최저 0x060FF400 이상) 여유 12 KB
KFILE = 'BIB.TXT'
LIT_WW = 0x06068AA4                 # 값 0x06068ADE (wordWrapString)
WORDWRAP = 0x06068ADE
BUF_A = 0x06068860                  # subStringBufA (아래 자리)
FONT_RAM = 0x0605883C               # fontBitmap
FONT_VRAM = 0x25C1A800              # 비캐시 VDP1 0x1A800
WIDTH = 0x0606203C                  # 폭 표 160 B
KERN = 0x060620DC                   # 커닝 160×160
KMAX = (KEND - KBASE - 0x1000) // 56    # 음절 최대 877 — 읽기 함수가 «섹터 수+1» 을 읽으므로 섹터 반올림+1섹터(0x1000) 여유
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
    a.defl('WW', WORDWRAP); a.defl('KB', KBASE); a.defl('SCR', EXPD['SCR']); a.defl('BUFA', BUF_A); a.defl('EXP', EXPD['EXP'])
    a.defl('VRAM', FONT_VRAM); a.defl('FONT', FONT_RAM); a.defw('K200', 200)
    a.defl('LOADF', LOADFILE); a.defl('STRCPY', STRCPY); a.defl('NBUF', NAMEBUF); a.defl('KNAME', EXPD['KNAME'])

    # ---- ① loadK — r4=이름 버퍼(«YUMISND.BIN» 이미 복사됨) r5=0x06082000. 반환 r0 = YUMISND 결과(호출자가 오류 검사)
    a.label('loadK')
    a.stspr_predec('r15')
    a.movl_pc('LOADF', 'r0'); a.jsr('r0'); a.nop()
    a.push('r0')
    a.movl_pc('NBUF', 'r4'); a.movl_pc('KNAME', 'r5'); a.movl_pc('STRCPY', 'r0'); a.jsr('r0'); a.nop()
    a.movl_pc('NBUF', 'r4'); a.movl_pc('KB', 'r5'); a.movl_pc('LOADF', 'r0'); a.jsr('r0'); a.nop()
    a.pop('r0'); a.ldspr_postinc('r15'); a.rts(); a.nop()

    # ---- ② remap
    a.label('remap')
    a.stspr_predec('r15'); a.stsmacl_push()
    for r in ('r8', 'r9', 'r10', 'r11', 'r12', 'r13', 'r4', 'r5', 'r6'):
        a.push(r)
    a.movl_pc('KB', 'r13')
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
    # 글리프: src = KBASE + r2×56(2bpp) · off = (r12+r1)×0x70 — 표(512 B)로 바이트마다 4bpp 2바이트
    #   ★1bpp + 실행 중 테두리 계산(expand1)은 수직귀선 인터럽트 안에서 너무 오래 걸려 소리 처리를 놓침(C104 멈춤 3회, 2026-10-01)
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



def build():
    code_len = 0x400
    for _ in range(3):
        EXPD = {}
        SCR = BASE + ((code_len + 3) & ~3)
        EXPD['EXP'] = SCR; SCR += 512
        EXPD['SCR'] = SCR; EXPD['KNAME'] = SCR + 128
        a = A(BASE)
        a.shll8 = lambda n, a=a: a.w(0x4018 | R[n] << 8)
        emit(a, EXPD)
        code, clen = a.assemble()
        if len(code) == code_len:
            break
        code_len = len(code)
    blob = bytearray(code) + bytes((-len(code)) % 4)
    assert BASE + len(blob) == EXPD['EXP']
    blob += kfont.expand_table()
    assert BASE + len(blob) == EXPD['SCR']
    blob += bytes(128)
    blob += (KFILE.encode() + b'\0').ljust(16, b'\0')
    sym = {'loadK': a.labels['loadK'], 'remap': a.labels['remap'], 'end': BASE + len(blob)}
    assert sym['end'] <= RAM_END
    return bytes(blob), sym


def patch_exe(exe):
    exe = bytearray(exe)
    assert LOAD + len(exe) == BASE, hex(LOAD + len(exe))
    u32 = lambda a: struct.unpack_from('>I', exe, a - LOAD)[0]
    assert u32(LIT_LOADSND) == LOADFILE and u32(LIT_WW) == WORDWRAP
    assert u32(0x0601252C) == 0x0601F368 and u32(0x0601253C) == 0x06082000     # «YUMISND.BIN» · 0x06082000
    blob, sym = build()
    exe += blob
    struct.pack_into('>I', exe, LIT_LOADSND - LOAD, sym['loadK'])
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
    import sh2dis
    blob, sym = build()
    print({k: hex(v) for k, v in sym.items()}, len(blob))
    g = open(os.path.join(os.path.dirname(HERE), 'work', 'disc', 'SATANIME_en.BIN'), 'rb').read() + blob
    print('\n'.join(sh2dis.dis(sym['loadK'], 40, g)))
