"""
Open3D 3D 시각화 + matplotlib 결과 플롯
"""
from __future__ import annotations

import numpy as np
import open3d as o3d
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path

from .analysis import AngleOfReposeResult


def visualize_pointcloud(
    ply_path: str,
    result: AngleOfReposeResult,
    plane_model: np.ndarray,
) -> None:
    """Open3D로 포인트 클라우드 + 지면 + 원뿔 축 시각화"""
    pcd = o3d.io.read_point_cloud(ply_path)

    geometries = [pcd]

    # 지면 평면 (반투명 메시)
    a, b, c, d = result.ground_plane
    normal = np.array([a, b, c]) / np.linalg.norm([a, b, c])
    bbox   = pcd.get_axis_aligned_bounding_box()
    ext    = bbox.get_extent()
    size   = max(ext[0], ext[1]) * 0.6

    # 지면 포인트 생성
    gplane = o3d.geometry.TriangleMesh.create_box(size, size, 0.001)
    gplane.translate(result.base_center - np.array([size / 2, size / 2, 0]))
    gplane.paint_uniform_color([0.8, 0.7, 0.5])  # 모래색
    geometries.append(gplane)

    # 꼭짓점 구
    apex_sphere = o3d.geometry.TriangleMesh.create_sphere(radius=ext[0] * 0.015)
    apex_sphere.translate(result.apex)
    apex_sphere.paint_uniform_color([1.0, 0.2, 0.2])
    geometries.append(apex_sphere)

    # 밑면 중심 구
    base_sphere = o3d.geometry.TriangleMesh.create_sphere(radius=ext[0] * 0.015)
    base_sphere.translate(result.base_center)
    base_sphere.paint_uniform_color([0.2, 0.8, 0.2])
    geometries.append(base_sphere)

    # 높이 선
    height_line = o3d.geometry.LineSet()
    height_line.points  = o3d.utility.Vector3dVector([result.apex, result.base_center])
    height_line.lines   = o3d.utility.Vector2iVector([[0, 1]])
    height_line.colors  = o3d.utility.Vector3dVector([[1.0, 0.5, 0.0]])
    geometries.append(height_line)

    o3d.visualization.draw_geometries(
        geometries,
        window_name=f"안식각 분석 — {result.angle_deg:.1f}°",
        width=1024,
        height=768,
    )


def save_result_plot(
    result: AngleOfReposeResult,
    output_path: str,
) -> str:
    """안식각 단면도 + 결과 요약 이미지 저장"""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.patch.set_facecolor("#1e1e2e")

    for ax in axes:
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="white")
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")
        ax.title.set_color("white")
        for spine in ax.spines.values():
            spine.set_edgecolor("#555577")

    # ── 왼쪽: 원뿔 단면도 ──────────────────────────────────────────────────
    ax1 = axes[0]
    h = result.pile_height
    r = result.pile_radius
    alpha = np.radians(result.angle_deg)

    # 원뿔 단면
    xs = np.array([-r, 0, r])
    ys = np.array([0,  h, 0])
    ax1.fill(xs, ys, color="#c8a882", alpha=0.7, label="토양 더미")
    ax1.plot(xs, ys, color="#e0c090", linewidth=2)

    # 지면선
    ax1.axhline(y=0, color="#888866", linewidth=1.5, linestyle="--", label="지면")

    # 안식각 호
    theta = np.linspace(0, alpha, 50)
    arc_r = r * 0.35
    ax1.plot(arc_r * np.cos(theta) - r, arc_r * np.sin(theta), color="#ff6699", linewidth=2)
    ax1.annotate(
        f"α = {result.angle_deg:.1f}°",
        xy=(-r + arc_r * 0.5, arc_r * 0.6),
        color="#ff6699",
        fontsize=13,
        fontweight="bold",
    )

    # 치수 표시
    ax1.annotate("", xy=(0, h), xytext=(0, 0),
                 arrowprops=dict(arrowstyle="<->", color="#66ffaa", lw=1.5))
    ax1.text(0.05 * r, h / 2, f"h={h:.3f}", color="#66ffaa", fontsize=10)

    ax1.annotate("", xy=(r, -0.05*h), xytext=(0, -0.05*h),
                 arrowprops=dict(arrowstyle="<->", color="#66aaff", lw=1.5))
    ax1.text(r * 0.4, -0.09 * h, f"r={r:.3f}", color="#66aaff", fontsize=10)

    ax1.set_xlim(-r * 1.4, r * 1.4)
    ax1.set_ylim(-0.15 * h, h * 1.2)
    ax1.set_aspect("equal")
    ax1.set_title("안식각 단면도", fontsize=14, fontweight="bold", color="white")
    ax1.set_xlabel("반지름", color="white")
    ax1.set_ylabel("높이", color="white")
    ax1.legend(facecolor="#2a2a3e", edgecolor="#555577",
               labelcolor="white", fontsize=10)

    # ── 오른쪽: 결과 요약 ──────────────────────────────────────────────────
    ax2 = axes[1]
    ax2.axis("off")

    summary = [
        ("안식각 (Angle of Repose)", f"{result.angle_deg:.2f}°", "#ff9966"),
        ("더미 높이",               f"{result.pile_height:.4f}",  "#66ffaa"),
        ("더미 반지름",              f"{result.pile_radius:.4f}",  "#66aaff"),
        ("tan(α) = h/r",           f"{result.pile_height / max(result.pile_radius, 1e-9):.4f}", "#ffcc44"),
        ("분석 포인트 수",           f"{result.n_points_pile:,}개", "#aaaacc"),
        ("전체 포인트 수",           f"{result.n_points_total:,}개", "#aaaacc"),
    ]

    y = 0.88
    ax2.text(0.5, 0.97, "분석 결과", ha="center", va="top",
             color="white", fontsize=15, fontweight="bold",
             transform=ax2.transAxes)
    for label, value, color in summary:
        ax2.text(0.05, y, label, ha="left", va="center",
                 color="#aaaacc", fontsize=11, transform=ax2.transAxes)
        ax2.text(0.95, y, value, ha="right", va="center",
                 color=color, fontsize=13, fontweight="bold",
                 transform=ax2.transAxes)
        y -= 0.13

    plt.tight_layout()
    out = str(Path(output_path) / "result.png")
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    return out
