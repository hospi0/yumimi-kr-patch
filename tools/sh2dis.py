# -*- coding: utf-8 -*-
"""SATANIME.BIN(영문 패치 적용본) SH-2 역어셈블 — python tools/sh2dis.py 0x06058800 [개수] [jp]
  적재 주소 0x06012000 (영문 패치 asm .open 과 같음). 테라 프로젝트 sh2_disasm 재사용."""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
LOAD = 0x06012000
EXE = os.path.join(ROOT, 'work', 'disc', 'SATANIME_en.BIN')
_src = open(r'C:\claude\project\terra-kr-patch\tools\sh2_disasm.py', encoding='utf-8').read().split("if __name__")[0]
_ns = {}; exec(_src, _ns)


def dis(addr, n=80, g=None):
    g = g or open(EXE, 'rb').read()
    o = addr - LOAD
    return ['%08X  %04X  %s' % (a, w, t) for a, w, t in _ns['disasm_sh2'](g[o:o + n * 2], addr, n)]


def lit(addr, g=None):
    g = g or open(EXE, 'rb').read()
    return struct.unpack_from('>I', g, addr - LOAD)[0]


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    a = int(sys.argv[1], 16); n = int(sys.argv[2]) if len(sys.argv) > 2 else 80
    g = open(EXE.replace('_en', '_jp'), 'rb').read() if 'jp' in sys.argv[3:] else None
    print('\n'.join(dis(a, n, g)))
