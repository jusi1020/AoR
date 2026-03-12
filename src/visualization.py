"""
결과 시각화: 360° 안식각 극좌표 다이어그램 + 통계 요약
"""
from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import open3d as o3d
from pathlib import Path

from .analysis import AngleOfReposeResult


def save_result_plot(result: AngleOfReposeResult, output_path: str) -> str:
    """
    안식각 분석 결과 이미지 저장

    - 왼쪽: 360° 방향별 안식각 극좌표 다이어그램 (rose plot)
    - 오른쪽: 수치 요약
    """
    fig = plt.figure(figsize=(14, 6))
    fig.patch.set_facecolor("#1e1e2e")

    # ── 왼쪽: 극좌표 rose 다이어그램 ─────────────────────────────────────
    ax1 = fig.add_subplot(121, projection="polar")
    ax1.set_facecolor("#2a2a3e")

    thetas = np.radians([w.theta_deg for w in result.wedge_results])
    angles = np.array(
        [w.angle_deg if w.valid else 0.0 for w in result.wedge_results]
    )
    valid = np.array([w.valid for w in result.wedge_results])

    n = len(thetas)
    bar_width = 2 * np.pi / n * 0.85

    # 색상: 안식각 크기에 따라 그라디언트 (낮으면 초록, 높으면 빨강)
    max_a   = max(result.max_angle_deg, 1.0)
    colors  = cm.RdYlGn_r(angles / max_a)
    colors[~valid] = [0.3, 0.3, 0.3, 0.5]  # 무효 wedge = 회색

    ax1.bar(thetas, angles, width=bar_width,
            color=colors, edgecolor="white", linewidth=0.3, alpha=0.9)

    # 평균 안식각 원 표시
    theta_ring = np.linspace(0, 2 * np.pi, 300)
    ax1.plot(
        theta_ring,
        np.full(300, result.mean_angle_deg),
        "--", color="#ffdd44", linewidth=1.8,
        label=f"평균  {result.mean_angle_deg:.1f}°",
    )

    ax1.set_title("360° 방향별 안식각", color="white",
                  fontsize=13, fontweight="bold", pad=15)
    ax1.set_theta_zero_location("N")   # 북쪽(0°)을 위쪽으로
    ax1.set_theta_direction(-1)        # 시계 방향
    ax1.tick_params(colors="white", labelsize=9)
    ax1.spines["polar"].set_color("#555577")
    for label in ax1.get_yticklabels():
        label.set_color("white")
    for label in ax1.get_xticklabels():
        label.set_color("#aaaacc")

    ax1.legend(
        facecolor="#2a2a3e", edgecolor="#555577",
        labelcolor="white", fontsize=9,
        loc="upper right", bbox_to_anchor=(1.3, 1.1),
    )

    # ── 오른쪽: 수치 요약 ────────────────────────────────────────────────
    ax2 = fig.add_subplot(122)
    ax2.set_facecolor("#2a2a3e")
    ax2.axis("off")

    rows = [
        ("평균 안식각 (ᾱ)",  f"{result.mean_angle_deg:.2f}°",  "#ff9966"),
        ("표준편차 (σ)",      f"{result.std_angle_deg:.2f}°",   "#ffcc44"),
        ("최솟값 / 최댓값",
         f"{result.min_angle_deg:.1f}° / {result.max_angle_deg:.1f}°",
         "#66ffcc"),
        ("유효 wedge 수",
         f"{result.n_valid_wedges} / {len(result.wedge_results)}",
         "#aaaacc"),
        ("─", "", "#444466"),
        ("더미 높이",        f"{result.pile_height:.4f}",       "#66aaff"),
        ("더미 반지름",      f"{result.pile_radius:.4f}",       "#66aaff"),
        ("─", "", "#444466"),
        ("분석 포인트",
         f"{result.n_points_pile:,} / {result.n_points_total:,}",
         "#aaaacc"),
    ]

    ax2.text(0.5, 0.97, "분석 결과", ha="center", va="top",
             color="white", fontsize=15, fontweight="bold",
             transform=ax2.transAxes)

    y = 0.86
    for label, value, color in rows:
        if label == "─":
            ax2.axhline(
                y=y + 0.03, xmin=0.05, xmax=0.95,
                color="#444466", linewidth=0.8,
                transform=ax2.transAxes,
            )
        else:
            ax2.text(0.05, y, label, ha="left", va="center",
                     color="#aaaacc", fontsize=11,
                     transform=ax2.transAxes)
            ax2.text(0.95, y, value, ha="right", va="center",
                     color=color, fontsize=12, fontweight="bold",
                     transform=ax2.transAxes)
        y -= 0.09

    plt.tight_layout(pad=2.0)
    out = str(Path(output_path) / "result.png")
    plt.savefig(out, dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()
    return out


def visualize_pointcloud(
    ply_path: str,
    result: AngleOfReposeResult,
) -> None:
    """Open3D로 포인트 클라우드 + 꼭짓점/밑면 중심 시각화"""
    pcd = o3d.io.read_point_cloud(ply_path)
    geometries = [pcd]

    bbox = pcd.get_axis_aligned_bounding_box()
    ext  = bbox.get_extent()

    # 꼭짓점 구 (빨강)
    apex_sphere = o3d.geometry.TriangleMesh.create_sphere(radius=ext[0] * 0.015)
    apex_sphere.translate(result.apex)
    apex_sphere.paint_uniform_color([1.0, 0.2, 0.2])
    geometries.append(apex_sphere)

    # 밑면 중심 구 (초록)
    base_sphere = o3d.geometry.TriangleMesh.create_sphere(radius=ext[0] * 0.015)
    base_sphere.translate(result.base_center)
    base_sphere.paint_uniform_color([0.2, 0.8, 0.2])
    geometries.append(base_sphere)

    # 높이 축선 (주황)
    line = o3d.geometry.LineSet()
    line.points = o3d.utility.Vector3dVector([result.apex, result.base_center])
    line.lines  = o3d.utility.Vector2iVector([[0, 1]])
    line.colors = o3d.utility.Vector3dVector([[1.0, 0.5, 0.0]])
    geometries.append(line)

    o3d.visualization.draw_geometries(
        geometries,
        window_name=f"안식각 분석 — 평균 {result.mean_angle_deg:.1f}°",
        width=1024, height=768,
    )
