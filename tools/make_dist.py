# -*- coding: utf-8 -*-
r"""유미미 믹스 리믹스 배포 묶음 — dist/YumimiMixRemix_KR_<VER>/ : 트랙 1 xdelta + xdelta.exe + readme.txt(CP949) + 한글패치_적용.bat
  원본 = 일본판 Redump 트랙 1 (영문 패치를 거치지 않은 원본) → 한글판 트랙 1 (영문 패치의 자막 엔진 포함)
  검증: 원본 트랙 1 → xdelta 적용 → md5 = 빌드 결과(work/out) md5.
  python tools/make_dist.py   (먼저 python tools/build.py --write)
"""
import hashlib, os, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)

VER = 'v0.9'
XDELTA = r'C:\claude\utils\xdelta.exe'
ROMNAME = 'Yumimi Mix Remix (Japan)'
SRC = os.path.join(r'C:\claude\roms\ss\완료', ROMNAME, ROMNAME + ' (Track 1).bin')   # 사용자가 완료 폴더로 옮김
OUT = os.path.join(ROOT, 'work', 'out', ROMNAME + ' (Track 1).bin')
NAME = 'YumimiMixRemix_KR_' + VER
TITLE = '유미미 믹스 리믹스 (세가 새턴 일본판) 한글 패치 ' + VER
TRACKS = 4


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest().upper()


HEAD = """{tracks}개의 트랙으로 이루어진 {rom} 의
트랙 1번에 패치하시면 됩니다.

원본md5 : {o}
패치md5 : {d}

입니다.
"""

BODY = """

[ 적용 방법 ]

  1) 원본 트랙 1 파일을 이 폴더에 복사
       "{bin}"
  2) 한글패치_적용.bat 실행 → 이름 끝에 [KR] 이 붙은 파일이 만들어집니다
  3) 만든 파일 이름을 원본 트랙 1 이름으로 바꿔 넣고, 나머지 트랙(2~4)과 cue 는 그대로 쓰세요
     (트랙 1 크기가 조금 커지지만 cue 는 트랙마다 파일을 따로 가리키므로 고칠 필요 없습니다)

  직접 적용:
    xdelta.exe -d -s "원본 트랙 1" "{patch}" "결과 파일"
  (Delta Patcher 같은 xdelta3 GUI 도구로 적용해도 됩니다. 원본이 다르면 xdelta 가 적용을 거부합니다.)
  ※ 영문 패치를 먼저 적용하지 마세요. 일본판 원본(Redump)에 바로 적용합니다.


[ 바뀌는 것 ]

  - 음성 자막 전부(영문 패치가 새로 만든 자막 기능을 한글로) - 노래는 위에 한글 발음 카라오케, 아래에 뜻풀이
  - 선택지
  - 제목 로고, 메인 메뉴, 백업 RAM 안내, 저장/불러오기 줄, 일시정지 메뉴, 광고 화면
  - 유미미 퍼즐 로고, 끝 화면, 예고 화면
  - 일시정지 메뉴의 경칭 옵션은 뺐고, 엔딩 크레디트는 영문 패치 그대로입니다.


[ 만든 사람 ]

  - 자막 기능·영문 패치: Supper (yumimiremixtools, GPLv3) - 이 한글 패치는 그 위에 한글 표시를 더한 것입니다.
  - 한글 번역·패치: hospi


[ 알려진 점 ]

  - 아직 끝까지 실기로 통독하지 못했습니다. 이상한 곳이 있으면 알려 주세요.
"""

BAT = r"""@echo off
chcp 949 >nul
set "XD=%~dp0xdelta.exe"
if not exist "%~dp0{bin}" (
  echo   [오류] 원본 트랙 1 파일을 이 폴더에 넣어 주세요(readme 참고).
  pause & exit /b 1
)
"%XD%" -d -f -s "%~dp0{bin}" "%~dp0{patch}" "%~dp0{kbin}"
if errorlevel 1 (
  echo   [오류] 패치 실패 - 원본이 다를 수 있습니다(readme 의 원본md5 확인).
  pause & exit /b 1
)
echo   완료: "{kbin}"
pause
"""


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    d = os.path.join(ROOT, 'dist', NAME)
    os.makedirs(d, exist_ok=True)
    b = os.path.basename(SRC)
    patch = NAME + '.xdelta'; pp = os.path.join(d, patch)
    subprocess.run([XDELTA, '-e', '-9', '-f', '-B', '536870912', '-s', SRC, OUT, pp], check=True)
    chk = os.path.join(d, '_check.bin')
    subprocess.run([XDELTA, '-d', '-f', '-B', '536870912', '-s', SRC, pp, chk], check=True)
    o, want, got = md5(SRC), md5(OUT), md5(chk)
    os.remove(chk)
    assert got == want, ('패치 적용 결과가 빌드와 다름', got, want)
    kbin = ROMNAME + ' (Track 1) [KR].bin'
    shutil.copy2(XDELTA, os.path.join(d, 'xdelta.exe'))
    readme = (TITLE + '\n' + '=' * 60 + '\n\n' + HEAD.format(tracks=TRACKS, rom=ROMNAME, o=o, d=want)
              + BODY.format(bin=b, patch=patch))
    open(os.path.join(d, 'readme.txt'), 'wb').write(readme.replace('\n', '\r\n').encode('cp949'))
    open(os.path.join(d, '한글패치_적용.bat'), 'wb').write(
        BAT.format(bin=b, patch=patch, kbin=kbin).replace('\n', '\r\n').encode('cp949'))
    print('원본md5 %s → 패치md5 %s · %s %d B' % (o, want, patch, os.path.getsize(pp)))
    print('✅', d)
    for f in sorted(os.listdir(d)):
        print('  %-40s %12d' % (f, os.path.getsize(os.path.join(d, f))))


if __name__ == '__main__':
    main()
