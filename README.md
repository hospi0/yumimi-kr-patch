# 유미미 믹스 리믹스 (세가 새턴 일본판) 한글 패치

**최신 v0.9** — 내려받기는 [Releases](../../releases) 의 `YumimiMixRemix_KR_v0.9.zip`.
일본판 Redump 4트랙 중 **트랙 1** 에 적용합니다(원본md5 `B26C2987…` → 패치md5 `81E815FA…`). 영문 패치를 먼저 적용하지 마세요.

## 만든 방법
- Supper 의 영문 패치([yumimiremixtools](https://github.com/suppertails66/yumimiremixtools), GPLv3)가 새로 만든 **게임 안 자막 기능**을 한글로 바꿨습니다.
  영문 패치 적용본을 직접 고치며, 빌드 도구(armips 등)는 쓰지 않습니다.
- 자막: 영문 패치의 컴파일된 자막 블록(SUBS)에서 문자열만 한국어로 교체. 한국어 음절은 2바이트 코드 → 표시 직전에 기울임꼴 자리 75칸을 캐시로 써서 글리프를 올림(`tools/hookk.py`).
  장면별 글리프는 자막 블록 뒤에 1bpp 로 싣고 적재 때 높은 RAM 으로 복사.
- 그림: 장면 그림 코덱(`tools/scene.py`), 메뉴·로고·선택지(`tools/gfx.py`).
- 디스크: 트랙 1 전체 재배치(`tools/iso.py`).
- 분석 문서: `docs/03_자막엔진.md` (같은 엔진의 다른 판·게임에 옮길 때 참고).

## 빌드
```
python tools/trmerge.py --apply     # 번역(my files/yumimi_ko) → 조각 단위 TSV
python tools/build.py --write       # → work/out/…(Track 1).bin
python tools/make_dist.py           # → dist/
```
