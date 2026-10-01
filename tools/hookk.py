# -*- coding: utf-8 -*-
r"""유미미 한글 자막 SH-2 코드 (2026-10-01, 2판) — 영문 패치 적용본 SATANIME.BIN 에 덧붙인다
  ① copyWrap  — 적재 함수(0x0605DACC)의 memcpy 호출 리터럴 0x0605DB58 을 이것으로.
       r4=dst(subtitleBlockData) r5=src(0x20200000) r6=블록 전체 크기.
       블록 끝 8 B 가 [u32 복사 크기]['HANG'] 이면: 글리프(복사 크기 ‥ 끝−8)를 GLY 로 복사, GB=GLY, 문자열 부분만 subtitleBlockData 로.
       ★1판은 글리프를 Low RAM(0x200000 영역)에서 바로 읽었는데, 큰 장면은 음성을 0x200000 에 다시 읽어 들여 글리프가 덮임
         (2026-10-01 실기: C102 에서 글자 깨짐) → 높은 RAM 으로 복사.
  ② remap     — assignRenderBufString 의 wordWrapString 호출 리터럴 0x06068AA4 를 이것으로.
       준비 버퍼를 제자리에서 2바이트 음절(A0+i/200, 1+i%200) → 1바이트 캐시 코드로. 새 칸마다 글리프(2bpp 56 B)를
       표 조회로 4bpp 로 펼쳐(2bpp: 0 투명·1 테두리·2 그림자·3→F) VDP1 글꼴 칸과 RAM 글꼴 원본 둘 다에 쓴다.
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
PCM_EXTRA = 6                       # 블록 최대 = 6섹터(장면마다 실제로 더 읽는 수는 pcmExtra 가 ceil(크기/0x800))
LIT_RET = 0x0605DB8C                # 영문 적재 함수의 «0x0601256C 로 복귀» 리터럴
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
    a.defl('GB', GB); a.defl('SCR', SCR); a.defl('GLY', GLY); a.defl('BUFA', BUF_A); a.defl('EXP', EXPD['EXP'])
    a.defl('VRAM', FONT_VRAM); a.defl('FONT', FONT_RAM); a.defw('K200', 200)

    # ---- ⓪ pcmExtra — 영문 적재 함수 끝의 «0x0601256C 로 복귀» 리터럴(0x0605DB8C)을 이것으로.
    #   r11 = 0x00200004 + SUBS 크기(영문 코드가 방금 맞춰 둔 값) → 음성 분할 읽기 섹터 수 «ADD #imm,R5»(0x0601AD6A)의
    #   imm 을 1 + ceil(SUBS 크기/0x800) 로 고쳐 쓴다(자기 수정 코드 — SH-2 캐시는 명령·데이터 공용이라 같은 CPU 에서 일관).
    #   ★2026-10-01 실기: 모든 장면에 +6 을 고정했더니 C104 에서 소리 대기(0x0601B1A4)로 멈춤 → 장면마다 꼭 필요한 만큼만.
    a.defl('B200004', 0x00200004); a.defl('ADDIMM', PCM_CNT + 1); a.defl('RET256C', 0x0601256C); a.defl('K7FF', 0x7FF)
    a.label('pcmExtra')
    a.mov('r11', 'r1'); a.movl_pc('B200004', 'r2'); a.sub('r2', 'r1')      # r1 = SUBS 크기(없으면 0)
    a.movl_pc('K7FF', 'r0'); a.add('r1', 'r0')
    a.shlr8('r0'); a.shlr2('r0'); a.shlr('r0')                             # ceil(크기/0x800)
    a.addi(1, 'r0')
    a.movl_pc('ADDIMM', 'r1'); a.movb_store('r0', 'r1')
    a.movl_pc('RET256C', 'r0'); a.jmp('r0'); a.nop()

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
    # 글리프: src = GB + r2×56(2bpp) · off = (r12+r1)×0x70 — 표(512 B)로 바이트마다 4bpp 2바이트
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
        EXPD['SCR'] = SCR; EXPD['GB'] = SCR + 128; EXPD['GLY'] = SCR + 132
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
    blob += bytes(128 + 4)
    sym = {'pcmExtra': a.labels['pcmExtra'], 'copyWrap': a.labels['copyWrap'], 'remap': a.labels['remap'],
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
    assert u32(LIT_RET) == 0x0601256C
    struct.pack_into('>I', exe, LIT_RET - LOAD, sym['pcmExtra'])    # 섹터 수는 장면마다 pcmExtra 가 실행 중에 고침
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
