# Gucci × Christmas Edition — 보관·복원 안내

크리스마스 에디션의 **디자인 요소는 전부 이 폴더에** 있고, 스위치 하나로 켜고 끕니다.
시즌이 끝나면 끄고(2027년 2월경), 다음 크리스마스에 다시 켜면 됩니다. 파일은 지우지 않습니다.

## 되돌리기 (클래식으로)

```
python scripts/xmas_toggle.py off
git add -A app/ui && git commit -m "classic look back" && git push
gh workflow run publish-only.yml -R anduli0/gucci-intel-engine
```

다시 켤 때는 `on`. 상태 확인은 `status`. 스크립트가 바꾸는 것은 세 가지뿐입니다 —
`index.html`의 스위치(`window.GI_XMAS.enabled`), 앱 아이콘 3종, SVG 파비콘.

미리보기: 스위치를 건드리지 않고 `?theme=classic` / `?theme=xmas` 를 URL에 붙이면 각 상태를 볼 수 있습니다.
스위치가 켜져 있어도 `until`(기본 2027-01-06 KST)이 지나면 자동으로 꺼집니다.

## 이 폴더의 내용

| 파일 | 내용 |
|---|---|
| `xmas.css` | 에디션 스타일 전부 — 눈 결정 배경, 레드·그린 헤더, 웹 스트라이프 리본, 조명 가랜드, 산타 썰매 페이지 스크롤바, 지팡이 브리프 스크롤바, 크리스마스 탭 표시. 모든 규칙이 `html.xmas`에 묶여 있어 꺼지면 아무 효과가 없음 |
| `xmas.js` | 에디션 동작 — 스위치 판정, `html.xmas` 부여, 헤더 홀스빗·트리·선물·양말 아트, 눈 내림, MRK ♥ 서명, 썰매 스크롤바, 한 몸 지팡이 스크롤바(드래그·터치) |
| `icons/icon-*.png` | 크리스마스 앱 아이콘(G-R-G 트리) 180/192/512 |
| `icons/favicon-xmas.txt`, `icons/favicon-classic.txt` | 탭 파비콘 두 버전(data-URI) |
| `../icons-original/` | 클래식 앱 아이콘(삼색 줄무늬) 원본 |

## 에디션이 아닌 것 (계속 쓰는 것 — 끄더라도 남음)

- 탭 상단 삼색 표시, 리포트 문체 계약(`.claude/style/`), 방법론 개선, 모바일 아코디언 동작, 리포트 사진(figure) 문법, 디렉터 도시에 사진, 데일리 길이 규칙, 금요일 주간 리뷰
- **크리스마스 탭의 내용**(`data/reports/archive/gucci-christmas-history.md`)은 영구 아카이브입니다. 탭 버튼만 에디션이 켜져 있을 때 보이고, 꺼지면 숨겨집니다(파일은 남음).

## 내년에 바꾸고 싶을 때

색은 `xmas.css` 상단 `html.xmas{ --cane / --cream / ... }` 변수, 스크롤바 그림은 `xmas.js`의 `caneSvg()`와 썰매 SVG,
헤더 아트는 같은 파일의 `BIT`(홀스빗)·트리·선물 블록입니다. 아이콘을 다시 만들려면 세션 스크립트 없이도
`icons/`의 PNG를 교체하고 `favicon-xmas.txt`를 바꾸면 됩니다.
