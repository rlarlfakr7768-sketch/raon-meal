# 라온고 급식 → 인스타 자동 게시 (클라우드 / PC 꺼도 됨)

공식 Instagram API로, **GitHub Actions가 매일 07:30(KST) 자동 게시**합니다.
형 PC가 꺼져 있어도 GitHub 서버가 돌립니다. **비용 0 · 차단 위험 0.**

## 구조
```
GitHub Actions(cron 07:30) → cloud_run.py
   → 급식 파싱(get_menu) → 카드 렌더(render_card, 한글폰트)
   → 이미지 공개 URL 업로드(catbox) → 공식 IG API 게시(publish_ig, 피드+스토리)
   → 토큰 갱신 → 갱신 토큰을 Secret에 다시 저장
```

## 처음 1회 설정 (형이 GitHub 웹에서)

### 1) 새 레포 만들기
- github.com → New repository → 이름 예 `raon-meal` → **Private** 권장 → Create

### 2) 이 폴더를 푸시
로컬에서 (이미 git init·commit 해둠):
```powershell
cd C:\Users\wldnj\raon-meal-cloud
git remote add origin https://github.com/<내아이디>/raon-meal.git
git branch -M main
git push -u origin main
```

### 3) Secret 2개 등록
레포 → **Settings → Secrets and variables → Actions → New repository secret**

1. **`IG_SECRETS_JSON`**
   - 값 = `C:\Users\wldnj\raon-meal-insta\secrets.json` 파일 **내용 전체**를 복사해 붙여넣기
   - (앱ID·앱시크릿·계정 토큰·user_id 가 들어있음)

2. **`GH_PAT`** (갱신된 토큰을 다시 저장하는 데 필요)
   - github.com → Settings(프로필) → Developer settings → **Fine-grained tokens** → Generate new token
   - Repository access: **Only select repositories → 이 레포**
   - Permissions → Repository permissions → **Secrets: Read and write**
   - 생성된 토큰 문자열을 `GH_PAT` 값으로 붙여넣기

### 4) 테스트 실행
- 레포 → **Actions** 탭 → "라온고 급식 자동 게시" → **Run workflow** (수동)
- 주말이면 "급식 없음 — 건너뜀"으로 정상 종료(게시 X). 평일이면 실제 게시.

## 운영
- 매일 07:30(KST) 자동. (GitHub cron은 몇 분 늦을 수 있음 — 정상)
- 올릴 계정 바꾸기: `cloud_run.py` 의 `TARGETS` 수정 (예: `["ha_miltonian","phyedu_net"]`)
- 스토리 끄기: `cloud_run.py` 의 `POST_STORY = False`
- 토큰은 매 실행 자동 갱신 → 사실상 안 만료. (60일 넘게 한 번도 안 돌면 재발급 필요)

## 주의
- 이미지 호스팅(catbox)이 데이터센터에서 막히면 → 게시 로그에 호스팅 실패가 뜸.
  그때는 GitHub Pages/jsDelivr 방식으로 교체(요청 시 작업).
- `secrets.json` 은 절대 커밋하지 않음(.gitignore 처리됨).
