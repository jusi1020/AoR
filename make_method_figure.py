"""
안식각 산정 알고리즘 설명 그림 생성
실행: python make_method_figure.py
출력: method_figure.png (현재 폴더)
"""
import platform
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch
from matplotlib.gridspec import GridSpec

# 한글 폰트
if platform.system() == "Windows":
    matplotlib.rc("font", family="Malgun Gothic")
elif platform.system() == "Darwin":
    matplotlib.rc("font", family="AppleGothic")
matplotlib.rcParams["axes.unicode_minus"] = False

BG   = "#1e1e2e"
CARD = "#2a2a3e"
LINE = "#555577"

fig = plt.figure(figsize=(16, 5.5), facecolor=BG)
gs  = GridSpec(1, 3, figure=fig, wspace=0.38,
               left=0.05, right=0.97, top=0.88, bottom=0.12)

# ── 공통 스타일 ──────────────────────────────────────────────────────────────
def style_ax(ax, title):
    ax.set_facecolor(CARD)
    ax.tick_params(colors="white", labelsize=9)
    ax.xaxis.label.set_color("white")
    ax.yaxis.label.set_color("white")
    for sp in ax.spines.values():
        sp.set_edgecolor(LINE)
    ax.set_title(title, color="white", fontsize=12, fontweight="bold", pad=10)

# ════════════════════════════════════════════════════════════════════════════
# STEP 1 — Wedge 분할 (부채꼴, top-down)
# ════════════════════════════════════════════════════════════════════════════
ax1 = fig.add_subplot(gs[0], projection="polar")
ax1.set_facecolor(CARD)
ax1.set_title("① Wedge 분할 (부감)", color="white",
              fontsize=12, fontweight="bold", pad=10)

N = 36
R = 1.0
theta_all = np.linspace(0, 2*np.pi, 300)

# 더미 외곽 원
ax1.plot(theta_all, np.full(300, R), color="#c8a882", linewidth=1.5, alpha=0.5)

# wedge 경계선
wedge_deg = 360 / N
rng = np.random.default_rng(42)
for i in range(N):
    t = np.radians(i * wedge_deg)
    ax1.plot([t, t], [0, R], color=LINE, linewidth=0.5, alpha=0.6)

# 하이라이트 wedge (예시 1개)
hi_i   = 4
t_lo   = np.radians(hi_i * wedge_deg)
t_hi   = np.radians((hi_i + 1) * wedge_deg)
t_fill = np.linspace(t_lo, t_hi, 30)
ax1.fill_between(t_fill, 0, R, color="#ff9966", alpha=0.55, label="분석 wedge")

# λ₁R, λ₂R 원
for lam, col, lab in [(0.15, "#66aaff", "λ₁R"), (0.85, "#66ff99", "λ₂R")]:
    ax1.plot(theta_all, np.full(300, lam * R), "--", color=col,
             linewidth=1.2, alpha=0.8)
    ax1.text(np.radians(200), lam * R + 0.07, lab,
             color=col, fontsize=8, ha="center")

ax1.set_theta_zero_location("N")
ax1.set_theta_direction(-1)
ax1.tick_params(colors="white", labelsize=8)
for lbl in ax1.get_yticklabels(): lbl.set_color("white")
for lbl in ax1.get_xticklabels(): lbl.set_color("#aaaacc")
ax1.spines["polar"].set_color(LINE)
ax1.legend(facecolor=CARD, edgecolor=LINE, labelcolor="white",
           fontsize=8, loc="upper right", bbox_to_anchor=(1.35, 1.1))

# ════════════════════════════════════════════════════════════════════════════
# STEP 2 — 단면 윤곽 추출 (r–z 공간)
# ════════════════════════════════════════════════════════════════════════════
ax2 = fig.add_subplot(gs[1])
style_ax(ax2, "② 단면 윤곽 추출 (r–z)")

rng2    = np.random.default_rng(7)
alpha_t = np.radians(29)            # 예시 안식각
R_max   = 1.0
r_raw   = rng2.uniform(0, R_max, 180)
z_true  = np.maximum(0, (R_max - r_raw) * np.tan(alpha_t))
z_raw   = z_true + rng2.normal(0, 0.025, len(r_raw))

# 전체 포인트 (회색)
ax2.scatter(r_raw, z_raw, s=6, color="#666688", alpha=0.5, zorder=2, label="전체 포인트")

# bin별 최대 z (윤곽 포인트)
n_bins   = 20
lam1, lam2 = 0.15, 0.85
bins     = np.linspace(lam1 * R_max, lam2 * R_max, n_bins + 1)
prof_r, prof_z = [], []
for j in range(n_bins):
    mask = (r_raw >= bins[j]) & (r_raw < bins[j+1])
    if mask.sum() > 0:
        prof_r.append((bins[j]+bins[j+1])/2)
        prof_z.append(float(np.max(z_raw[mask])))

prof_r = np.array(prof_r)
prof_z = np.array(prof_z)
ax2.scatter(prof_r, prof_z, s=28, color="#ff9966", zorder=4, label="bin 최대 높이")

# λ₁R, λ₂R 범위 음영
ax2.axvspan(lam1*R_max, lam2*R_max, alpha=0.08, color="#66ff99")
ax2.axvline(lam1*R_max, color="#66aaff", linewidth=1.2, linestyle="--", alpha=0.8)
ax2.axvline(lam2*R_max, color="#66ff99", linewidth=1.2, linestyle="--", alpha=0.8)
ax2.text(lam1*R_max, -0.06, "λ₁R", color="#66aaff", fontsize=8, ha="center")
ax2.text(lam2*R_max, -0.06, "λ₂R", color="#66ff99", fontsize=8, ha="center")

ax2.set_xlabel("반경  r", color="white")
ax2.set_ylabel("높이  z", color="white")
ax2.legend(facecolor=CARD, edgecolor=LINE, labelcolor="white", fontsize=8)
ax2.set_xlim(-0.05, 1.1)
ax2.set_ylim(-0.1, 1.2 * R_max * np.tan(alpha_t))

# ════════════════════════════════════════════════════════════════════════════
# STEP 3 — OLS 회귀 → 안식각
# ════════════════════════════════════════════════════════════════════════════
ax3 = fig.add_subplot(gs[2])
style_ax(ax3, "③ OLS 회귀 → 안식각 α")

# 동일 데이터
ax3.scatter(prof_r, prof_z, s=28, color="#ff9966", zorder=4, label="단면 윤곽")

# OLS
A      = np.column_stack([prof_r, np.ones_like(prof_r)])
coeffs, *_ = np.linalg.lstsq(A, prof_z, rcond=None)
a_sl, b_sl = coeffs
r_fit  = np.linspace(lam1*R_max, lam2*R_max, 100)
z_fit  = a_sl * r_fit + b_sl

ax3.plot(r_fit, z_fit, color="#ffdd44", linewidth=2.2, zorder=5,
         label=f"회귀선  z = {a_sl:.2f}r + {b_sl:.2f}")

# 안식각 호 표시
ang_deg = float(np.degrees(np.arctan(abs(a_sl))))
r_arc   = 0.18
thetas  = np.linspace(np.pi - np.arctan(abs(a_sl)), np.pi, 40)
# 회귀선과 수평선이 만나는 x 좌표
x0 = -b_sl / a_sl  # z=0 교점 (=추정 밑면 반지름)
ax3.axhline(0, color="#888866", linewidth=1.0, linestyle="--", alpha=0.7)

# 회귀선 연장 (z=0까지)
r_ext = np.linspace(0, max(r_fit[-1], x0) * 1.05, 200)
ax3.plot(r_ext, a_sl * r_ext + b_sl, color="#ffdd44", linewidth=1.0,
         linestyle=":", alpha=0.5)

# 각도 호
arc_x = x0 + r_arc * np.cos(np.linspace(np.pi, np.pi - np.arctan(abs(a_sl)), 40))
arc_y =      r_arc * np.sin(np.linspace(np.pi, np.pi - np.arctan(abs(a_sl)), 40))
ax3.plot(arc_x, arc_y, color="#ff6699", linewidth=2)
ax3.text(x0 - r_arc * 1.7, r_arc * 0.55,
         f"α = arctan(|a|)\n  = {ang_deg:.1f}°",
         color="#ff6699", fontsize=9.5, fontweight="bold")

ax3.set_xlabel("반경  r", color="white")
ax3.set_ylabel("높이  z", color="white")
ax3.legend(facecolor=CARD, edgecolor=LINE, labelcolor="white", fontsize=8)
ax3.set_xlim(-0.05, 1.1)
ax3.set_ylim(-0.15, 1.2 * R_max * np.tan(alpha_t))

# ── 제목 ─────────────────────────────────────────────────────────────────────
fig.text(0.5, 0.97,
         "3D 포인트 클라우드 기반 안식각 산정 알고리즘",
         ha="center", va="top",
         color="white", fontsize=14, fontweight="bold")

out = "method_figure.png"
plt.savefig(out, dpi=180, bbox_inches="tight", facecolor=BG)
plt.close()
print(f"저장 완료: {out}")
