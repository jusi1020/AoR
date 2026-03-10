"""
Metashape 자동 3D 재구성 파이프라인
사진 폴더 → 포인트 클라우드 + 메시 생성
"""
import os
from pathlib import Path
from typing import Callable, Optional


def run_reconstruction(
    photo_dir: str,
    output_dir: str,
    license_key: str,
    quality: str = "medium",          # lowest / low / medium / high / highest
    progress_callback: Optional[Callable[[str, int], None]] = None,
) -> dict:
    """
    Metashape를 이용해 사진 → 포인트 클라우드 + 메시 생성

    Returns:
        {"ply": <경로>, "obj": <경로>, "success": bool, "error": str|None}
    """
    try:
        import Metashape
    except ImportError:
        raise RuntimeError(
            "Metashape 모듈을 찾을 수 없습니다.\n"
            "pip install <metashape.whl> 로 먼저 설치해주세요."
        )

    def _progress(msg: str, pct: int = 0):
        if progress_callback:
            progress_callback(msg, pct)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    ply_path = str(output_path / "pointcloud.ply")
    obj_path = str(output_path / "mesh.obj")

    # ── 라이선스 활성화 ──────────────────────────────────────────────────────
    _progress("라이선스 확인 중...", 2)
    if not Metashape.License().valid:
        Metashape.License().activate(license_key)
        if not Metashape.License().valid:
            raise RuntimeError("Metashape 라이선스 활성화 실패")

    # ── Metashape 2.x 품질 매핑 (downscale 정수값) ──────────────────────────
    # matchPhotos downscale: 0=highest, 1=high, 2=medium, 4=low, 8=lowest
    # buildDepthMaps downscale: 1=ultra, 2=high, 4=medium, 8=low, 16=lowest
    match_downscale = {
        "highest": 0,
        "high":    1,
        "medium":  2,
        "low":     4,
        "lowest":  8,
    }.get(quality, 2)

    depth_downscale = {
        "highest": 1,
        "high":    2,
        "medium":  4,
        "low":     8,
        "lowest":  16,
    }.get(quality, 4)

    # ── 프로젝트 생성 ────────────────────────────────────────────────────────
    _progress("프로젝트 생성 중...", 5)
    doc   = Metashape.Document()
    chunk = doc.addChunk()

    # ── 사진 추가 ────────────────────────────────────────────────────────────
    _progress("사진 불러오는 중...", 8)
    exts  = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
    photos = [
        str(p) for p in Path(photo_dir).iterdir()
        if p.suffix.lower() in exts
    ]
    if not photos:
        raise ValueError(f"사진을 찾을 수 없습니다: {photo_dir}")

    chunk.addPhotos(photos)
    _progress(f"{len(photos)}장 사진 로드 완료", 12)

    # ── 사진 정렬 (Sparse Point Cloud) ───────────────────────────────────────
    _progress("사진 정렬 중 (1/4)...", 15)
    chunk.matchPhotos(
        downscale=match_downscale,
        generic_preselection=True,
        reference_preselection=False,
    )
    chunk.alignCameras()
    _progress("사진 정렬 완료", 35)

    # ── Depth Maps ───────────────────────────────────────────────────────────
    _progress("깊이 맵 생성 중 (2/4)...", 38)
    chunk.buildDepthMaps(
        downscale=depth_downscale,
    )
    _progress("깊이 맵 완료", 55)

    # ── Dense Point Cloud ────────────────────────────────────────────────────
    _progress("포인트 클라우드 생성 중 (3/4)...", 58)
    chunk.buildPointCloud()
    _progress("포인트 클라우드 완료", 72)

    # ── PLY 내보내기 ─────────────────────────────────────────────────────────
    _progress("포인트 클라우드 저장 중...", 74)
    # format은 .ply 확장자로 자동 감지
    chunk.exportPointCloud(
        path=ply_path,
        save_colors=True,
    )

    # ── Mesh ─────────────────────────────────────────────────────────────────
    _progress("메시 생성 중 (4/4)...", 76)
    chunk.buildModel(
        surface_type=Metashape.SurfaceType.HeightField,
        face_count=Metashape.FaceCount.MediumFaceCount,
    )
    chunk.buildTexture(
        blending_mode=Metashape.BlendingMode.Mosaic,
        texture_size=4096,
    )
    _progress("메시 완료", 92)

    # ── OBJ 내보내기 ─────────────────────────────────────────────────────────
    _progress("메시 저장 중...", 94)
    # format은 .obj 확장자로 자동 감지
    chunk.exportModel(
        path=obj_path,
        save_texture=True,
        save_uv=True,
    )

    _progress("재구성 완료!", 100)

    return {
        "ply":     ply_path,
        "obj":     obj_path,
        "success": True,
        "error":   None,
    }
