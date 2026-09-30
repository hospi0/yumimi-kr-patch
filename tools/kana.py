# -*- coding: utf-8 -*-
r"""노래 가사 로마자(카라오케 «<…>») → 한글 발음 (2026-10-01)
  ★거센소리 규칙: か행 ㅋ · た행 ㅌ · つ 츠 · ち 치 (어두 무기음 안 씀) [[feedback_jp_name_romanization]]
  촉음(kk·pp·tt·ss·cch·tch) = 앞 음절 ㅅ 받침 · ん = ㄴ 받침 · 장음(aa·uu·ee·oo·ou)은 뺀다(ii 는 «いい» 라 둔다).
  «< > { }» 표시는 자리 그대로 두되, 음절 한가운데(wasurey><ou)면 음절 앞으로 옮기고,
  받침(촉음·ん)이 표시 뒤로 떨어져 있으면 앞 음절 쪽으로 붙인다 — 그러면 뒤 묶음이 비는 경우엔 앞 음절째 뒤 묶음으로 넘긴다.
  python tools/kana.py "<to><ppin shan>"
"""
import re, sys

CHO = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ'
JUNG = ['ㅏ', 'ㅐ', 'ㅑ', 'ㅒ', 'ㅓ', 'ㅔ', 'ㅕ', 'ㅖ', 'ㅗ', 'ㅘ', 'ㅙ', 'ㅚ', 'ㅛ', 'ㅜ', 'ㅝ', 'ㅞ', 'ㅟ', 'ㅠ', 'ㅡ', 'ㅢ', 'ㅣ']
JONG = ['', 'ㄱ', 'ㄲ', 'ㄳ', 'ㄴ', 'ㄵ', 'ㄶ', 'ㄷ', 'ㄹ', 'ㄺ', 'ㄻ', 'ㄼ', 'ㄽ', 'ㄾ', 'ㄿ', 'ㅀ', 'ㅁ', 'ㅂ', 'ㅄ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']

C = {'': 'ㅇ', 'k': 'ㅋ', 'g': 'ㄱ', 's': 'ㅅ', 'sh': 'ㅅ', 'z': 'ㅈ', 'j': 'ㅈ', 't': 'ㅌ', 'ch': 'ㅊ', 'ts': 'ㅊ', 'd': 'ㄷ',
     'n': 'ㄴ', 'h': 'ㅎ', 'f': 'ㅎ', 'b': 'ㅂ', 'p': 'ㅍ', 'm': 'ㅁ', 'y': 'ㅇ', 'r': 'ㄹ', 'w': 'ㅇ'}
V = {'a': 'ㅏ', 'i': 'ㅣ', 'u': 'ㅜ', 'e': 'ㅔ', 'o': 'ㅗ'}
YV = {'a': 'ㅑ', 'u': 'ㅠ', 'o': 'ㅛ', 'e': 'ㅖ'}
SYL = {}
for c in C:
    for v in 'aiueo':
        SYL[c + v] = (C[c], V[v])
for c in ('k', 'g', 'n', 'h', 'b', 'p', 'm', 'r'):
    for v in 'auo':
        SYL[c + 'y' + v] = (C[c], YV[v])
for v in 'auo':
    SYL['y' + v] = ('ㅇ', YV[v])
for c in ('sh', 'j', 'ch'):                 # しゃ=샤 · じゃ=자 · ちゃ=차 (지·치 뒤 ㅑ 는 한국어에서 ㅏ)
    for v in 'auoe':
        SYL[c + v] = (C[c], ('ㅑ' if v == 'a' else 'ㅠ' if v == 'u' else 'ㅛ' if v == 'o' else 'ㅖ') if c == 'sh' else V[v])
SYL['wa'] = ('ㅇ', 'ㅘ'); SYL['wo'] = ('ㅇ', 'ㅗ'); SYL['wi'] = ('ㅇ', 'ㅟ'); SYL['we'] = ('ㅇ', 'ㅞ')
SYL['fu'] = ('ㅎ', 'ㅜ'); SYL['tsu'] = ('ㅊ', 'ㅡ'); SYL['su'] = ('ㅅ', 'ㅡ'); SYL['zu'] = ('ㅈ', 'ㅡ')
SYL['shi'] = ('ㅅ', 'ㅣ'); SYL['chi'] = ('ㅊ', 'ㅣ'); SYL['ji'] = ('ㅈ', 'ㅣ')
SYL['du'] = ('ㅈ', 'ㅡ'); SYL['di'] = ('ㄷ', 'ㅣ')
KEYS = sorted(SYL, key=len, reverse=True)
MARK = '<>{}'


def compose(cho, jung, jong=''):
    return chr(0xAC00 + (CHO.index(cho) * 21 + JUNG.index(jung)) * 28 + JONG.index(jong))


def tokens(plain):
    """로마자 → [(종류, 값, 시작, 끝)] 종류 = S(음절, 로마자) · Q(촉음) · N(ん) · X(그 밖 글자 그대로)"""
    out = []; i = 0; low = plain.lower()
    while i < len(low):
        if low.startswith('\\n', i):
            out.append(('X', '\\n', i, i + 2)); i += 2; continue
        ch = low[i]
        if ch.isalpha():
            nx = low[i + 1] if i + 1 < len(low) else ''
            if ch == 'n' and (not nx or nx not in 'aiueoy'):
                out.append(('N', 'n', i, i + 1)); i += 1; continue
            if nx and (ch in 'kpts' and nx == ch) or ch == 'c' and nx == 'c' or ch == 't' and nx == 'c':
                out.append(('Q', ch, i, i + 1)); i += 1; continue
            for k in KEYS:
                if low.startswith(k, i):
                    out.append(('S', k, i, i + len(k))); i += len(k); break
            else:
                raise ValueError('로마자 해석 불가 %r @%d «%s»' % (ch, i, plain))
            continue
        if ch == '-':                           # otto-san 의 붙임표 → 뺌
            i += 1; continue
        out.append(('X', plain[i], i, i + 1)); i += 1
    return out


def line(src):
    src = src.replace('AH―', 'a―')
    plain = ''; marks = []                      # (평문 위치, 표시)
    for ch in src:
        if ch in MARK:
            marks.append((len(plain), ch))
        else:
            plain += ch
    tk = tokens(plain)
    # 장음 빼기
    keep = []
    for t in tk:
        if t[0] == 'S' and t[1] in 'aueo' and keep and keep[-1][0] == 'S':
            pv = keep[-1][1][-1]
            if pv == t[1] or (pv == 'o' and t[1] == 'u'):
                keep.append(('D',) + t[1:]); continue
        keep.append(t)
    tk = keep
    # 표시 → 토큰 사이 자리(k = k번째 토큰 앞)
    seq = []
    for p, m in marks:
        k = 0
        while k < len(tk) and tk[k][3] <= p:    # 음절 한가운데(tk[k] 시작 < p)면 자연히 그 음절 앞
            k += 1
        seq.append([k, m])
    # 받침(Q·N)이 표시 바로 뒤면 앞 음절 쪽으로
    for s in seq:
        k = s[0]
        j = k
        while j < len(tk) and tk[j][0] in 'QND':
            j += 1
        if j > k and k > 0 and tk[k - 1][0] in 'SD':
            s[0] = j
    # 뒤 묶음이 비면 앞 음절째 넘김
    for i, s in enumerate(seq):
        if s[1] != '<':
            continue
        k = s[0]
        end = next((q[0] for q in seq[i + 1:] if q[1] == '>'), len(tk))
        if not any(t[0] == 'S' for t in tk[k:end]):
            b = k - 1
            while b >= 0 and tk[b][0] != 'S':
                b -= 1
            if b >= 0:
                for q in seq[:i + 1]:
                    if b < q[0] <= k:
                        q[0] = b
    # 한글로
    out = []; at = {}
    for k, m in seq:
        at.setdefault(k, []).append(m)
    last = None                                 # out 안 마지막 음절 자리
    for k, t in enumerate(tk + [None]):
        for m in at.get(k, []):
            out.append(m)
        if t is None:
            break
        if t[0] == 'S':
            cho, jung = SYL[t[1]]
            out.append([cho, jung, '']); last = len(out) - 1
        elif t[0] in 'QN':
            if last is not None and out[last][2] == '':
                out[last][2] = 'ㅅ' if t[0] == 'Q' else 'ㄴ'
            elif t[0] == 'N':
                out.append('ㄴ')
        elif t[0] == 'X':
            out.append(t[1])
    return ''.join(compose(*x) if isinstance(x, list) else x for x in out)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    for a in sys.argv[1:]:
        print(a, '→', line(a))
