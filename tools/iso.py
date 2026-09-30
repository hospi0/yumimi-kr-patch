# -*- coding: utf-8 -*-
r"""유미미 트랙 1 전체 재배치 (2026-10-01) — 영문 패치 적용본 트랙 1 에서 파일을 바꿔 넣고 다시 이어 붙인다
  적용본 배치(tools/subs·docs/03): 섹터 0‥39 = 시스템 영역·PVD(16)·끝(17)·경로표(18·19)·루트 디렉터리(20‥39, 20섹터),
    데이터 파일 LBA 40 부터 LBA 순으로 빈틈없이, 트랙 1 은 마지막 파일 끝에서 끝남(뒷간격 없음 — 원본도 같음).
    CD-DA «포인터 파일» CDDA1‥3 = 디렉터리 기록이 트랙 2‥4 의 INDEX 01 절대 LBA 를 가리킴 → 트랙 1 길이 차만큼 옮김.
    PVD 볼륨 크기 = 전 트랙 합(적용본 165,443) → 같은 차만큼.
  새 트랙 1: 파일을 같은 LBA 순서·새 크기로 다시 이어 쓰고, 모든 데이터 섹터는 헤더(MSF)+EDC/ECC 새로(cdmode1).
  from iso import rebuild; rebuild(src_bin, n_track1, {'/C006B.DAT': bytes, …}, out_bin)
"""
import os, struct, sys
sys.path.insert(0, r'C:\claude\project\anearth-kr-patch\tools')
import cdmode1

SEC = 2352
SYNC = b'\x00' + b'\xff' * 10 + b'\x00'


def bcd(n):
    return (n // 10) << 4 | n % 10


def header(lba):
    a = lba + 150
    return SYNC + bytes([bcd(a // 4500), bcd(a // 75 % 60), bcd(a % 75), 1])


def mksec(lba, data):
    s = bytearray(SEC)
    s[0:16] = header(lba)
    s[16:16 + len(data)] = data
    return bytes(cdmode1.fix(s))


def dir_records(user, lba0, nsec):
    """디렉터리 영역(유저 데이터 바이트) → [(바이트 위치, 이름, lba, size, 플래그)]"""
    out = []
    for k in range(nsec):
        base = k * 2048; i = 0
        while i < 2048:
            n = user[base + i]
            if n == 0:
                break
            rec = user[base + i:base + i + n]
            nl = rec[32]; name = rec[33:33 + nl].decode('latin1').split(';')[0]
            out.append((base + i, name, struct.unpack_from('<I', rec, 2)[0], struct.unpack_from('<I', rec, 10)[0], rec[25]))
            i += n
    return out


def rebuild(src, n_track1, repl, out, log=print):
    f = open(src, 'rb')
    def raw(lba):
        f.seek(lba * SEC); return f.read(SEC)
    def user(lba, n=1):
        return b''.join(raw(lba + k)[16:2064] for k in range(n))
    pvd = bytearray(user(16))
    root_lba, root_size = struct.unpack_from('<I', pvd, 156 + 2)[0], struct.unpack_from('<I', pvd, 156 + 10)[0]
    rn = (root_size + 2047) // 2048
    assert root_lba == 20 and rn == 20, (root_lba, rn)
    rdir = bytearray(user(root_lba, rn))
    recs = dir_records(rdir, root_lba, rn)
    files = [r for r in recs if r[1] not in ('\x00', '\x01')]
    assert not any(r[4] & 2 for r in files), '하위 디렉터리 있음'
    data = sorted([r for r in files if r[2] < n_track1], key=lambda r: r[2])
    cdda = [r for r in files if r[2] >= n_track1]
    assert data[0][2] == 40
    for a, b in zip(data, data[1:]):
        assert b[2] == a[2] + (a[3] + 2047) // 2048, ('빈틈', a[1], b[1])
    assert data[-1][2] + (data[-1][3] + 2047) // 2048 == n_track1
    names = {'/' + r[1] for r in data}
    for k in repl:
        assert k in names, ('없는 파일', k)
    # 새 배치
    lba = 40; plan = []
    for pos, nm, l, s, fl in data:
        new = repl.get('/' + nm)
        size = len(new) if new is not None else s
        plan.append((pos, nm, l, s, lba, size, new))
        lba += (size + 2047) // 2048
    n_new = lba; delta = n_new - n_track1
    # 디렉터리·PVD 고치기
    def put_lba_size(pos, lba, size):
        struct.pack_into('<I', rdir, pos + 2, lba); struct.pack_into('>I', rdir, pos + 6, lba)
        struct.pack_into('<I', rdir, pos + 10, size); struct.pack_into('>I', rdir, pos + 14, size)
    for pos, nm, l, s, nl, ns, new in plan:
        put_lba_size(pos, nl, ns)
    for pos, nm, l, s, fl in cdda:
        put_lba_size(pos, l + delta, s)
    vol = struct.unpack_from('<I', pvd, 80)[0]
    struct.pack_into('<I', pvd, 80, vol + delta); struct.pack_into('>I', pvd, 84, vol + delta)
    # 쓰기
    o = open(out, 'wb')
    for k in range(40):
        if k == 16:
            o.write(mksec(16, pvd))
        elif 20 <= k < 40:
            o.write(mksec(k, rdir[(k - 20) * 2048:(k - 19) * 2048]))
        else:
            o.write(raw(k))
    moved = 0
    for pos, nm, l, s, nl, ns, new in plan:
        n = (ns + 2047) // 2048
        if new is None and nl == l:
            for k in range(n):
                o.write(raw(l + k))
            continue
        body = new if new is not None else user(l, n)[:s]
        body = body + bytes(n * 2048 - len(body))
        for k in range(n):
            o.write(mksec(nl + k, body[k * 2048:(k + 1) * 2048]))
        moved += 1
    o.close()
    assert os.path.getsize(out) == n_new * SEC
    log('트랙 1: %d → %d 섹터(차 %+d) · 다시 쓴 파일 %d / %d · CDDA 포인터 %d개 이동' % (n_track1, n_new, delta, moved, len(plan), len(cdda)))
    return n_new
