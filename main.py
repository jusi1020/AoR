"""
AoR — Angle of Repose 자동 측정 시스템
토양 실린더리프팅법 3D 재구성 + 안식각 계산

워크플로:
  STEP 1 — 3D 재구성 → 포인트 클라우드 시각화 확인
  STEP 2 — 확인 후 안식각 분석 실행

실행: python main.py
"""
import threading
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog, messagebox

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

LICENSE_FILE = Path(__file__).parent / ".license_key"

# 단계 색상
COLOR_STEP1  = "#1a4a7a"   # 파랑 계열
COLOR_STEP2  = "#2d5a27"   # 초록 계열
COLOR_ACTIVE = "#0088ff"


class AoRApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AoR — 안식각 측정 시스템")
        self.geometry("700x760")
        self.resizable(False, False)

        self._photo_dir  = ctk.StringVar()
        self._output_dir = ctk.StringVar(value=str(Path.home() / "AoR_output"))
        self._license    = ctk.StringVar(value=self._load_license())
        self._quality    = ctk.StringVar(value="medium")

        # 상태
        self._ply_path: str | None = None   # 재구성 결과 PLY
        self._analysis_result      = None

        self._build_ui()

    # ── UI 구성 ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        pad = {"padx": 20, "pady": 5}

        # 타이틀
        ctk.CTkLabel(
            self, text="🌱 AoR — 안식각 측정 시스템",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(pady=(22, 2))
        ctk.CTkLabel(
            self, text="실린더리프팅법 · 3D 재구성 → 시각화 확인 → 안식각 분석",
            font=ctk.CTkFont(size=12), text_color="gray",
        ).pack(pady=(0, 14))

        # ── 공통 입력 ─────────────────────────────────────────────────────
        # 사진 폴더
        f = ctk.CTkFrame(self); f.pack(fill="x", **pad)
        ctk.CTkLabel(f, text="📷 사진 폴더", width=120, anchor="w").pack(side="left", padx=12)
        ctk.CTkEntry(f, textvariable=self._photo_dir, width=380).pack(side="left", padx=4)
        ctk.CTkButton(f, text="찾기", width=60, command=self._pick_photo_dir).pack(side="left", padx=4)

        # 출력 폴더
        f = ctk.CTkFrame(self); f.pack(fill="x", **pad)
        ctk.CTkLabel(f, text="💾 출력 폴더", width=120, anchor="w").pack(side="left", padx=12)
        ctk.CTkEntry(f, textvariable=self._output_dir, width=380).pack(side="left", padx=4)
        ctk.CTkButton(f, text="찾기", width=60, command=self._pick_output_dir).pack(side="left", padx=4)

        # 품질
        f = ctk.CTkFrame(self); f.pack(fill="x", **pad)
        ctk.CTkLabel(f, text="⚙ 재구성 품질", width=120, anchor="w").pack(side="left", padx=12)
        for q in ["lowest", "low", "medium", "high", "highest"]:
            ctk.CTkRadioButton(f, text=q, variable=self._quality, value=q).pack(side="left", padx=8)

        # 라이선스
        f = ctk.CTkFrame(self); f.pack(fill="x", **pad)
        ctk.CTkLabel(f, text="🔑 라이선스 키", width=120, anchor="w").pack(side="left", padx=12)
        ctk.CTkEntry(f, textvariable=self._license, show="*", width=380).pack(side="left", padx=4)
        ctk.CTkButton(f, text="저장", width=60, command=self._save_license).pack(side="left", padx=4)

        # ── 진행 상황 ─────────────────────────────────────────────────────
        ctk.CTkLabel(self, text="진행 상황", anchor="w").pack(fill="x", padx=20, pady=(12, 2))
        self._progress_bar = ctk.CTkProgressBar(self, width=660)
        self._progress_bar.pack(padx=20)
        self._progress_bar.set(0)
        self._status_label = ctk.CTkLabel(
            self, text="대기 중", text_color="gray",
            font=ctk.CTkFont(size=12),
        )
        self._status_label.pack(pady=(3, 0))

        # ── STEP 1 ────────────────────────────────────────────────────────
        sep1 = ctk.CTkFrame(self, height=2, fg_color="#334466")
        sep1.pack(fill="x", padx=20, pady=(14, 6))

        ctk.CTkLabel(
            self, text="STEP 1 — 3D 재구성",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#66aaff",
            anchor="w",
        ).pack(fill="x", padx=20)

        btn1_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn1_frame.pack(pady=8)

        self._recon_btn = ctk.CTkButton(
            btn1_frame,
            text="▶  3D 재구성 시작",
            width=220, height=44,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLOR_STEP1, hover_color="#2060aa",
            command=self._start_reconstruction,
        )
        self._recon_btn.pack(side="left", padx=8)

        self._view3d_btn = ctk.CTkButton(
            btn1_frame,
            text="🔍 포인트 클라우드 확인",
            width=200, height=44,
            fg_color="#334455", hover_color="#446688",
            command=self._view_pointcloud,
            state="disabled",
        )
        self._view3d_btn.pack(side="left", padx=8)

        # PLY 직접 불러오기 (재구성 없이 분석만 하고 싶을 때)
        ply_frame = ctk.CTkFrame(self, fg_color="transparent")
        ply_frame.pack(pady=(0, 4))
        ctk.CTkLabel(ply_frame, text="또는 PLY 직접 불러오기:", text_color="gray",
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=4)
        self._ply_label = ctk.CTkLabel(ply_frame, text="(없음)", text_color="gray",
                                        font=ctk.CTkFont(size=11), width=300, anchor="w")
        self._ply_label.pack(side="left", padx=4)
        ctk.CTkButton(ply_frame, text="PLY 열기", width=90, height=28,
                      command=self._load_ply_directly).pack(side="left", padx=4)

        # ── STEP 2 ────────────────────────────────────────────────────────
        sep2 = ctk.CTkFrame(self, height=2, fg_color="#334433")
        sep2.pack(fill="x", padx=20, pady=(12, 6))

        ctk.CTkLabel(
            self, text="STEP 2 — 안식각 분석",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#66ff99",
            anchor="w",
        ).pack(fill="x", padx=20)

        self._analyze_btn = ctk.CTkButton(
            self,
            text="📐  안식각 분석 실행",
            width=220, height=44,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLOR_STEP2, hover_color="#3a7a35",
            command=self._start_analysis,
            state="disabled",
        )
        self._analyze_btn.pack(pady=8)

        # 결과 박스
        self._result_box = ctk.CTkTextbox(
            self, height=130, width=660,
            font=ctk.CTkFont(family="Courier", size=13),
        )
        self._result_box.pack(padx=20, pady=(4, 16))
        self._result_box.insert("end", "3D 재구성 후 포인트 클라우드를 확인하세요.\n"
                                       "이상 없으면 STEP 2에서 안식각을 분석합니다.\n")
        self._result_box.configure(state="disabled")

    # ── 이벤트 ───────────────────────────────────────────────────────────────

    def _pick_photo_dir(self):
        d = filedialog.askdirectory(title="사진 폴더 선택")
        if d: self._photo_dir.set(d)

    def _pick_output_dir(self):
        d = filedialog.askdirectory(title="출력 폴더 선택")
        if d: self._output_dir.set(d)

    def _save_license(self):
        key = self._license.get().strip()
        if key:
            LICENSE_FILE.write_text(key)
            messagebox.showinfo("저장됨", "라이선스 키가 저장됐습니다.")

    def _load_license(self) -> str:
        return LICENSE_FILE.read_text().strip() if LICENSE_FILE.exists() else ""

    def _load_ply_directly(self):
        f = filedialog.askopenfilename(title="PLY 파일 선택", filetypes=[("PLY", "*.ply")])
        if f:
            self._ply_path = f
            self._ply_label.configure(text=Path(f).name, text_color="#66aaff")
            self._view3d_btn.configure(state="normal")
            self._analyze_btn.configure(state="normal")
            self._log(f"PLY 불러옴: {f}\n포인트 클라우드를 확인하고 분석을 시작하세요.\n")

    # ── STEP 1: 재구성 ───────────────────────────────────────────────────────

    def _start_reconstruction(self):
        if not self._photo_dir.get():
            messagebox.showwarning("입력 오류", "사진 폴더를 선택해주세요.")
            return
        self._recon_btn.configure(state="disabled")
        self._view3d_btn.configure(state="disabled")
        self._analyze_btn.configure(state="disabled")
        self._progress_bar.set(0)
        threading.Thread(target=self._run_reconstruction, daemon=True).start()

    def _run_reconstruction(self):
        try:
            from src.reconstruction import run_reconstruction

            output_dir = self._output_dir.get()
            Path(output_dir).mkdir(parents=True, exist_ok=True)

            self._update_status("재구성 시작...", 0)
            recon = run_reconstruction(
                photo_dir         = self._photo_dir.get(),
                output_dir        = output_dir,
                license_key       = self._license.get().strip(),
                quality           = self._quality.get(),
                progress_callback = self._update_status,
            )
            self._ply_path = recon["ply"]

            self._update_status("재구성 완료! 포인트 클라우드를 확인하세요.", 100)
            self._log(
                f"재구성 완료!\n"
                f"  PLY  : {recon['ply']}\n"
                f"  OBJ  : {recon['obj']}\n\n"
                f"[3D 확인] 버튼으로 포인트 클라우드를 확인하세요.\n"
                f"이상 없으면 [안식각 분석 실행]을 누르세요.\n"
            )

            def _enable():
                self._view3d_btn.configure(state="normal")
                self._analyze_btn.configure(state="normal")
                self._ply_label.configure(text=Path(self._ply_path).name, text_color="#66aaff")
            self.after(0, _enable)

        except Exception as e:
            msg = str(e)
            self._update_status(f"오류: {msg}", 0)
            self.after(0, lambda m=msg: messagebox.showerror("재구성 오류", m))
        finally:
            self.after(0, lambda: self._recon_btn.configure(state="normal"))

    def _view_pointcloud(self):
        if not self._ply_path:
            return
        threading.Thread(
            target=self._open_o3d_viewer, daemon=True
        ).start()

    def _open_o3d_viewer(self):
        try:
            import open3d as o3d
            pcd = o3d.io.read_point_cloud(self._ply_path)
            o3d.visualization.draw_geometries(
                [pcd],
                window_name="포인트 클라우드 확인",
                width=1024, height=768,
            )
        except Exception as e:
            msg = str(e)
            self.after(0, lambda m=msg: messagebox.showerror("시각화 오류", m))

    # ── STEP 2: 분석 ─────────────────────────────────────────────────────────

    def _start_analysis(self):
        if not self._ply_path:
            messagebox.showwarning("입력 오류", "먼저 3D 재구성을 하거나 PLY 파일을 불러오세요.")
            return
        self._analyze_btn.configure(state="disabled")
        self._progress_bar.set(0)
        threading.Thread(target=self._run_analysis, daemon=True).start()

    def _run_analysis(self):
        try:
            from src.analysis      import analyze_angle_of_repose
            from src.visualization import save_result_plot

            self._update_status("포인트 클라우드 분석 중...", 20)
            result = analyze_angle_of_repose(
                self._ply_path,
                output_dir=output_dir,
            )

            self._update_status("결과 이미지 저장 중...", 85)
            output_dir = self._output_dir.get()
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            img_path = save_result_plot(result, output_dir)

            self._analysis_result = result

            # 배경 제거된 PLY가 저장됐으면 뷰어를 그걸로 교체
            if result.cleaned_ply_path:
                def _update_ply(p=result.cleaned_ply_path):
                    self._ply_path = p
                    self._ply_label.configure(
                        text="pile_cleaned.ply  ✓ 배경 제거됨",
                        text_color="#66ff99",
                    )
                self.after(0, _update_ply)

            self._update_status("분석 완료!", 100)

            text = (
                f"{'='*46}\n"
                f"  평균 안식각 (ᾱ)  : {result.mean_angle_deg:.2f}°\n"
                f"  표준편차 (σ)     :  {result.std_angle_deg:.2f}°\n"
                f"  범위             : {result.min_angle_deg:.1f}° ~ {result.max_angle_deg:.1f}°\n"
                f"  유효 wedge       : {result.n_valid_wedges} / {len(result.wedge_results)}\n"
                f"{'='*46}\n"
                f"  더미 높이        : {result.pile_height:.4f}\n"
                f"  더미 반지름      : {result.pile_radius:.4f}\n"
                f"  분석 포인트      : {result.n_points_pile:,} / {result.n_points_total:,}\n"
                f"{'='*46}\n"
                f"  결과 이미지      : {img_path}\n"
            )
            self._log(text)

        except Exception as e:
            msg = str(e)
            self._update_status(f"오류: {msg}", 0)
            self.after(0, lambda m=msg: messagebox.showerror("분석 오류", m))
        finally:
            self.after(0, lambda: self._analyze_btn.configure(state="normal"))

    # ── 유틸 ─────────────────────────────────────────────────────────────────

    def _log(self, text: str):
        def _update():
            self._result_box.configure(state="normal")
            self._result_box.delete("1.0", "end")
            self._result_box.insert("end", text)
            self._result_box.configure(state="disabled")
        self.after(0, _update)

    def _update_status(self, msg: str, pct: int):
        def _update():
            self._status_label.configure(text=msg)
            self._progress_bar.set(pct / 100)
        self.after(0, _update)


# ── 진입점 ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = AoRApp()
    app.mainloop()
