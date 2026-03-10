"""
포인트 클라우드 분석 → 안식각(Angle of Repose) 측정

알고리즘:
  1. 포인트 클라우드 로드 & 전처리
  2. RANSAC으로 지면 평면 검출
  3. 지면 위 토양 더미 포인트 분리
  4. 원뿔(cone) 피팅으로 안식각 계산
"""
from __future__ import annotations

import numpy as np
import open3d as o3d
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class AngleOfReposeResult:
    angle_deg: float           # 안식각 (도)
    angle_rad: float           # 안식각 (라디안)
    pile_height: float         # 더미 높이 (m 또는 포인트 클라우드 단위)
    pile_radius: float         # 더미 반지름
    apex: np.ndarray           # 꼭짓점 좌표 [x, y, z]
    base_center: np.ndarray    # 밑면 중심 좌표
    n_points_total: int        # 전체 포인트 수
    n_points_pile: int         # 더미 포인트 수
    ground_plane: np.ndarray   # 지면 평면 방정식 [a, b, c, d] (ax+by+cz+d=0)


def load_and_preprocess(ply_path: str, voxel_size: float = 0.005) -> o3d.geometry.PointCloud:
    """PLY 로드 → 다운샘플링 → 이상치 제거"""
    pcd = o3d.io.read_point_cloud(ply_path)
    if len(pcd.points) == 0:
        raise ValueError(f"포인트 클라우드가 비어 있습니다: {ply_path}")

    # 자동 voxel_size: 바운딩박스 대각선의 0.3%
    bbox = pcd.get_axis_aligned_bounding_box()
    diag = np.linalg.norm(bbox.get_extent())
    voxel_size = max(voxel_size, diag * 0.003)

    pcd = pcd.voxel_down_sample(voxel_size=voxel_size)

    # 통계적 이상치 제거
    pcd, _ = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
    pcd.estimate_normals(
        search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=voxel_size * 5, max_nn=30)
    )
    return pcd


def detect_ground_plane(
    pcd: o3d.geometry.PointCloud,
    distance_threshold: Optional[float] = None,
    ransac_n: int = 3,
    num_iterations: int = 2000,
) -> Tuple[np.ndarray, o3d.geometry.PointCloud, o3d.geometry.PointCloud]:
    """
    RANSAC으로 지면 평면 검출

    Returns:
        plane_model  : [a, b, c, d]
        ground_pcd   : 지면 포인트들
        pile_pcd     : 더미 포인트들
    """
    pts = np.asarray(pcd.points)
    bbox = pcd.get_axis_aligned_bounding_box()
    diag = np.linalg.norm(bbox.get_extent())
    if distance_threshold is None:
        distance_threshold = diag * 0.01

    plane_model, inliers = pcd.segment_plane(
        distance_threshold=distance_threshold,
        ransac_n=ransac_n,
        num_iterations=num_iterations,
    )

    ground_pcd = pcd.select_by_index(inliers)
    pile_pcd   = pcd.select_by_index(inliers, invert=True)

    # 지면이 아래 있도록 보정 (법선이 위를 향하게)
    a, b, c, d = plane_model
    if c < 0:
        plane_model = np.array([-a, -b, -c, -d])

    return np.array(plane_model), ground_pcd, pile_pcd


def _height_above_plane(points: np.ndarray, plane: np.ndarray) -> np.ndarray:
    """각 포인트의 지면 평면 위 높이 계산"""
    a, b, c, d = plane
    normal = np.array([a, b, c])
    normal /= np.linalg.norm(normal)
    return points @ normal + d / np.linalg.norm(np.array([a, b, c]))


def fit_cone_angle(
    pile_pcd: o3d.geometry.PointCloud,
    plane_model: np.ndarray,
) -> AngleOfReposeResult:
    """
    토양 더미에 원뿔 피팅 → 안식각 계산

    방법: 밑면 중심에서 각 포인트까지의 수평 거리와 높이의 비율로
          선형 회귀(최소제곱)를 통해 원뿔 경사각 계산
    """
    pts = np.asarray(pile_pcd.points)

    # 지면 법선 방향
    a, b, c, d = plane_model
    normal = np.array([a, b, c], dtype=float)
    normal /= np.linalg.norm(normal)

    # 각 포인트의 지면 위 높이
    heights = pts @ normal + d / np.linalg.norm([a, b, c])

    # 높이가 양수인 포인트만 (지면 위)
    above_mask = heights > np.percentile(heights, 5)
    pts_above  = pts[above_mask]
    h_above    = heights[above_mask]

    # 꼭짓점(최고점) 주변 포인트에서 밑면 중심 추정
    apex_idx      = np.argmax(h_above)
    apex          = pts_above[apex_idx]
    pile_height   = h_above[apex_idx]

    # 꼭짓점을 지면에 투영 → 밑면 중심
    base_center = apex - pile_height * normal

    # 각 포인트의 수평 거리 (밑면 중심 기준)
    vecs = pts_above - base_center
    # 수평 성분만 (법선 방향 제거)
    vecs_proj   = vecs - (vecs @ normal)[:, None] * normal
    radii       = np.linalg.norm(vecs_proj, axis=1)

    # 더미 반지름 (하위 10% 높이에서의 평균 반지름)
    low_mask    = h_above < np.percentile(h_above, 15)
    pile_radius = float(np.median(radii[low_mask])) if low_mask.sum() > 5 else float(np.max(radii))

    # 안식각: 높이와 반지름의 비율로 선형 회귀
    # tan(α) = h / r  →  α = arctan(h/r)
    # 회귀: h = tan(α) * r  →  기울기 = tan(α)
    valid = radii > pile_radius * 0.05
    if valid.sum() < 10:
        # 회귀 실패 시 단순 계산
        tan_alpha = pile_height / (pile_radius + 1e-9)
    else:
        # 원점 통과 선형 회귀: h = slope * r
        r_v = radii[valid]
        h_v = h_above[valid]
        # h를 감소 방향으로 (꼭짓점에서 멀수록 낮음)
        h_from_base = pile_height - h_v
        slope, *_ = np.linalg.lstsq(r_v[:, None], h_from_base, rcond=None)
        tan_alpha = float(slope[0])

    angle_rad = float(np.arctan(max(tan_alpha, 0.0)))
    angle_deg = float(np.degrees(angle_rad))

    return AngleOfReposeResult(
        angle_deg    = round(angle_deg, 2),
        angle_rad    = round(angle_rad, 4),
        pile_height  = round(float(pile_height), 4),
        pile_radius  = round(pile_radius, 4),
        apex         = apex,
        base_center  = base_center,
        n_points_total = len(np.asarray(pile_pcd.points)) + 0,
        n_points_pile  = len(pts_above),
        ground_plane = plane_model,
    )


def analyze_angle_of_repose(
    ply_path: str,
    voxel_size: float = 0.005,
) -> AngleOfReposeResult:
    """전체 파이프라인: PLY → 안식각"""
    pcd                           = load_and_preprocess(ply_path, voxel_size)
    plane_model, ground_pcd, pile_pcd = detect_ground_plane(pcd)
    result                        = fit_cone_angle(pile_pcd, plane_model)
    result.n_points_total         = len(np.asarray(pcd.points))
    return result
