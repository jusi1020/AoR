# AoR — Angle of Repose 자동 측정 시스템

토양 **실린더리프팅법** 사진 → 3D 재구성 → 안식각(α) 자동 계산

## 파이프라인

```
📷 360° 사진들 (물체 주변)
    ↓
🔧 Metashape API (사진 정렬 → 포인트 클라우드 → 메시)
    ↓
🔍 Open3D 분석
    ├── RANSAC 지면 평면 검출
    ├── 토양 더미 분리
    └── 원뿔 피팅 → 안식각 계산
    ↓
📊 결과 (각도 + 단면도 + 3D 시각화)
```

## 설치

```bash
# 1. Metashape Python API 설치
pip install "C:\Users\sjisu\Downloads\metashape-2.3.0-cp39.cp310.cp311.cp312.cp313-none-win_amd64.whl"

# 2. 나머지 패키지
pip install -r requirements.txt
```

## 실행

```bash
python main.py
```

## 실행 모드

| 모드 | 설명 |
|------|------|
| **전체** | 사진 폴더 → Metashape 재구성 → 안식각 분석 |
| **분석만** | 기존 PLY 파일 → 안식각 분석만 수행 |

## 출력

| 파일 | 설명 |
|------|------|
| `pointcloud.ply` | 밀집 포인트 클라우드 |
| `mesh.obj` | 텍스처 메시 |
| `result.png` | 안식각 단면도 + 수치 요약 |
