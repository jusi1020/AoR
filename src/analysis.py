"""
포인트 클라우드 분석 → 안식각(Angle of Repose) 360° 측정

알고리즘:
  1. PLY 로드 & 전처리 (다운샘플링 + 통계 이상치 제거)
  2. RANSAC 지면 평면 검출
  3. 지면 위 포인트 분리 → DBSCAN으로 배경 노이즈 제거
  4. 중심축 기준 N개 wedge 분할
  5. 각 wedge: 반경 bin별 최대 높이 추출 → OLS 회귀 → 안식각
  6. 360° 분포 통계 산출
"""
from __future__ import annotations

import numpy as np
import open3d as o3d
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class WedgeResult:
    theta_deg: float    # wedge 중심 방위각 (°)
    angle_deg: float    # 이 방향의 안식각 (°), NaN이면 유효하지 않음
    n_points: int       # 사용된 포인트 수
    valid: bool         # 회귀 신뢰도 충분 여부


@dataclass
class AngleOfReposeResult:
    # 360° wedge별 결과
    wedge_results: List[WedgeResult]

    # 통계 (유효 wedge만 대상)
    mean_angle_deg: float
    std_angle_deg: float
    min_angle_deg: float
    max_angle_deg: float
    n_valid_wedges: int

    # 형상 파라미터
    pile_height: float
    pile_radius: float
    apex: np.ndarray
    base_center: np.ndarray
    ground_plane: np.ndarray

    # 포인트 수
    n_points_total: int
    n_points_pile: int

    @property
    def angle_deg(self) -> float:
        """하위 호환: 평균 안식각 반환"""
        return self.mean_angle_deg


# ── 전처리 ────────────────────────────────────────────────────────────────────

def load_and_preprocess(
    ply_path: str,
    voxel_size: float = 0.005,
) -> o3d.geometry.PointCloud:
    """PLY 로드 → 다운샘플링 → 통계적 이상치 제거"""
    pcd = o3d.io.read_point_cloud(ply_path)
    if len(pcd.points) == 0:
        raise ValueError(f"포인트 클라우드가 비어 있습니다: {ply_path}")

    # 자동 voxel_size: 바운딩박스 대각선의 0.3%
    bbox = pcd.get_axis_aligned_bounding_box()
    diag = np.linalg.norm(bbox.get_extent())
    voxel_size = max(voxel_size, diag * 0.003)

    pcd = pcd.voxel_down_sample(voxel_size=voxel_size)

    # 통계적 이상치 제거 (std_ratio=1.5 → 기존보다 적극적)
    pcd, _ = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=1.5)
    pcd.estimate_normals(
        search_param=o3d.geometry.KDTreeSearchParamHybrid(
            radius=voxel_size * 5, max_nn=30
        )
    )
    return pcd


# ── 지면 검출 ─────────────────────────────────────────────────────────────────

def detect_ground_plane(
    pcd: o3d.geometry.PointCloud,
    distance_threshold: Optional[float] = None,
    ransac_n: int = 3,
    num_iterations: int = 2000,
):
    """RANSAC 지면 평면 검출 → (plane_model, ground_pcd, pile_pcd)"""
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

    # 법선이 위를 향하도록 보정
    a, b, c, d = plane_model
    if c < 0:
        plane_model = [-a, -b, -c, -d]

    return np.array(plane_model, dtype=float), ground_pcd, pile_pcd


# ── 배경 노이즈 제거 ──────────────────────────────────────────────────────────

def extract_pile_cluster(
    pile_pcd: o3d.geometry.PointCloud,
    plane_model: np.ndarray,
) -> o3d.geometry.PointCloud:
    """
    DBSCAN 클러스터링으로 배경(검은 배경판 등) 노이즈를 제거하고
    가장 큰 클러스터(= 토양 더미)만 반환
    """
    pts = np.asarray(pile_pcd.points)
    a, b, c, d = plane_model
    normal    = np.array([a, b, c], dtype=float)
    norm_len  = np.linalg.norm(normal)
    normal   /= norm_len
    heights   = pts @ normal + d / norm_len

    # 지면 바로 위 얇은 레이어(하위 5%) 제외 → 지면 경계 노이즈 제거
    h_thresh = np.percentile(heights, 5)
    above_idx = np.where(heights > h_thresh)[0].tolist()
    pile_above = pile_pcd.select_by_index(above_idx)

    if len(pile_above.points) < 10:
        return pile_pcd

    # DBSCAN
    bbox = pile_above.get_axis_aligned_bounding_box()
    diag = np.linalg.norm(bbox.get_extent())
    eps  = max(diag * 0.04, 0.005)
    labels = np.array(
        pile_above.cluster_dbscan(eps=eps, min_points=10, print_progress=False)
    )

    if labels.max() < 0:
        return pile_above  # 클러스터 없으면 그대로

    # 가장 큰 클러스터 선택
    unique, counts = np.unique(labels[labels >= 0], return_counts=True)
    best_label = unique[np.argmax(counts)]
    indices = np.where(labels == best_label)[0].tolist()
    return pile_above.select_by_index(indices)


# ── 360° wedge 분석 ───────────────────────────────────────────────────────────

def analyze_wedges(
    pile_pcd: o3d.geometry.PointCloud,
    plane_model: np.ndarray,
    n_wedges: int = 36,
    n_bins: int = 20,
    lambda1: float = 0.15,
    lambda2: float = 0.85,
):
    """
    원통 좌표계 wedge 분할 → 방향별 안식각 계산

    각 wedge에서:
      - 반경 r 방향으로 n_bins 개 구간 분할
      - 각 bin에서 최대 높이 z 추출 → 단면 윤곽 {(r_j, z_j)}
      - OLS 회귀: z = a·r + b  →  α = arctan(|a|)
      - 회귀 범위: r ∈ [λ₁·R, λ₂·R]  (정점부/발끝 영역 제외)

    Returns:
        wedge_results, apex, base_center, pile_height, pile_radius
    """
    pts = np.asarray(pile_pcd.points)
    a, b, c, d = plane_model
    normal   = np.array([a, b, c], dtype=float)
    norm_len = np.linalg.norm(normal)
    normal  /= norm_len
    heights  = pts @ normal + d / norm_len

    # 꼭짓점(apex): 높이 상위 1% 평균 (단일 노이즈 포인트 완화)
    apex_thresh = np.percentile(heights, 99)
    apex = pts[heights >= apex_thresh].mean(axis=0)
    pile_height = float(np.max(heights))

    # 밑면 중심 = apex의 지면 투영
    apex_h      = float(apex @ normal + d / norm_len)
    base_center = apex - apex_h * normal

    # 각 포인트의 수평 벡터 (법선 성분 제거)
    vecs       = pts - base_center
    vecs_horiz = vecs - (vecs @ normal)[:, None] * normal
    radii      = np.linalg.norm(vecs_horiz, axis=1)

    # 수평 좌표계 (직교 2축)
    ref = np.array([1.0, 0.0, 0.0])
    if abs(np.dot(ref, normal)) > 0.9:
        ref = np.array([0.0, 1.0, 0.0])
    ax1 = ref - np.dot(ref, normal) * normal
    ax1 /= np.linalg.norm(ax1)
    ax2 = np.cross(normal, ax1)
    ax2 /= np.linalg.norm(ax2)

    thetas = np.arctan2(vecs_horiz @ ax2, vecs_horiz @ ax1)  # [-π, π]

    # 대표 반지름 (95퍼센타일)
    R_max       = float(np.percentile(radii, 95))
    pile_radius = R_max

    wedge_angle_rad   = 2 * np.pi / n_wedges
    wedge_results: List[WedgeResult] = []

    for i in range(n_wedges):
        theta_c = -np.pi + (i + 0.5) * wedge_angle_rad

        # 각도 차이를 [-π, π]로 정규화하여 wedge 내 포인트 선택
        delta = ((thetas - theta_c + np.pi) % (2 * np.pi)) - np.pi
        mask  = np.abs(delta) <= wedge_angle_rad / 2

        w_r = radii[mask]
        w_h = heights[mask]

        if len(w_r) < 5:
            wedge_results.append(WedgeResult(
                theta_deg=float(np.degrees(theta_c)),
                angle_deg=float('nan'),
                n_points=int(mask.sum()),
                valid=False,
            ))
            continue

        # 반경 범위 [λ₁·R, λ₂·R] 에서 bin별 최대 높이 추출
        r_lo      = R_max * lambda1
        r_hi      = R_max * lambda2
        bin_edges = np.linspace(r_lo, r_hi, n_bins + 1)

        profile_r, profile_z = [], []
        for j in range(n_bins):
            b_mask = (w_r >= bin_edges[j]) & (w_r < bin_edges[j + 1])
            if b_mask.sum() > 0:
                profile_r.append((bin_edges[j] + bin_edges[j + 1]) / 2)
                profile_z.append(float(np.max(w_h[b_mask])))

        if len(profile_r) < 3:
            wedge_results.append(WedgeResult(
                theta_deg=float(np.degrees(theta_c)),
                angle_deg=float('nan'),
                n_points=int(mask.sum()),
                valid=False,
            ))
            continue

        pr = np.array(profile_r)
        pz = np.array(profile_z)

        # OLS: z = a·r + b
        A = np.column_stack([pr, np.ones_like(pr)])
        coeffs, *_ = np.linalg.lstsq(A, pz, rcond=None)
        a_slope = float(coeffs[0])

        # α = arctan(|a|)  (기울기 음수 = 내리막 → 절댓값 사용)
        angle_deg = float(np.degrees(np.arctan(abs(a_slope))))

        wedge_results.append(WedgeResult(
            theta_deg=float(np.degrees(theta_c)),
            angle_deg=angle_deg,
            n_points=int(mask.sum()),
            valid=True,
        ))

    return wedge_results, apex, base_center, pile_height, pile_radius


# ── 메인 파이프라인 ───────────────────────────────────────────────────────────

def analyze_angle_of_repose(
    ply_path: str,
    voxel_size: float = 0.005,
    n_wedges: int = 36,
    n_bins: int = 20,
    lambda1: float = 0.15,
    lambda2: float = 0.85,
) -> AngleOfReposeResult:
    """전체 파이프라인: PLY → 360° 안식각 분석"""
    pcd     = load_and_preprocess(ply_path, voxel_size)
    n_total = len(pcd.points)

    plane_model, ground_pcd, pile_raw = detect_ground_plane(pcd)
    pile_pcd = extract_pile_cluster(pile_raw, plane_model)
    n_pile   = len(pile_pcd.points)

    wedge_results, apex, base_center, pile_height, pile_radius = analyze_wedges(
        pile_pcd, plane_model,
        n_wedges=n_wedges,
        n_bins=n_bins,
        lambda1=lambda1,
        lambda2=lambda2,
    )

    valid_angles = np.array([w.angle_deg for w in wedge_results if w.valid])
    if len(valid_angles) == 0:
        raise ValueError("유효한 wedge가 없습니다. 포인트 클라우드를 확인해주세요.")

    return AngleOfReposeResult(
        wedge_results  = wedge_results,
        mean_angle_deg = float(np.mean(valid_angles)),
        std_angle_deg  = float(np.std(valid_angles)),
        min_angle_deg  = float(np.min(valid_angles)),
        max_angle_deg  = float(np.max(valid_angles)),
        n_valid_wedges = int(len(valid_angles)),
        pile_height    = round(float(pile_height), 4),
        pile_radius    = round(float(pile_radius), 4),
        apex           = apex,
        base_center    = base_center,
        ground_plane   = plane_model,
        n_points_total = n_total,
        n_points_pile  = n_pile,
    )
