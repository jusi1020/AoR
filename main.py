"""
AoR — Angle of Repose 자동 측정 시스템
토양 실린더리프팅법 3D 재구성 + 안식각 계산

실행: python main.py
"""
import os
import sys
import threading
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog, messagebox

# ── 앱 설정 ──────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

LICENSE_FILE = Path(__file__).parent / ".license_key"


class AoRApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AoR — 안식각 측정 시스템")
        self.geometry("680x720")
        self.resizable(False, False)

        self._photo_dir  = ctk.StringVar()
        self._output_dir = ctk.StringVar(value=str(Path.home() / "AoR_output"))
        self._license    = ctk.StringVar(value=self._load_license())
        self._quality    = ctk.StringVar(value="medium")
        self._mode       = ctk.StringVar(value="full")   # full | analysis_only

        self._result_image_path: str | None = None
        self._build_ui()

    # ── UI 구성 ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        pad = {"padx": 20, "pady": 6}

        # 타이틀
        ctk.CTkLabel(
            self, text="🌱 AoR — 안식각 측정 시스템",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(pady=(24, 4))
        ctk.CTkLabel(
            self, text="실린더리프팅법 · 3D 재구성 + 안식각 자동 계산",
            font=ctk.CTkFont(size=13), text_color="gray",
        ).pack(pady=(0, 16))

        # ── 모드 선택 ─────────────────────────────────────────────────────
        mode_frame = ctk.CTkFrame(self)
        mode_frame.pack(fill="x", **pad)
        ctk.CTkLabel(mode_frame, text="실행 모드", width=120,
                     anchor="w").pack(side="left", padx=12)
        ctk.CTkRadioButton(mode_frame, text="전체 (재구성 + 분석)",
                           variable=self._mode, value="full",
                           command=self._on_mode_change).pack(side="left", padx=10)
        ctk.CTkRadioButton(mode_frame, text="분석만 (PLY 파일 직접 입력)",
                           variable=self._mode, value="analysis_only",
                           command=self._on_mode_change).pack(side="left", padx=10)

        # ── 사진 폴더 ─────────────────────────────────────────────────────
        self._photo_frame = ctk.CTkFrame(self)
        self._photo_frame.pack(fill="x", **pad)
        ctk.CTkLabel(self._photo_frame, text="📷 사진 폴더",
                     width=120, anchor="w").pack(side="left", padx=12)
        ctk.CTkEntry(self._photo_frame, textvariable=self._photo_dir,
                     width=360).pack(side="left", padx=4)
        ctk.CTkButton(self._photo_frame, text="찾기", width=60,
                      command=self._pick_photo_dir).pack(side="left", padx=4)

        # ── PLY 파일 (분석만 모드) ────────────────────────────────────────
        self._ply_var   = ctk.StringVar()
        self._ply_frame = ctk.CTkFrame(self)
        ctk.CTkLabel(self._ply_frame, text="📦 PLY 파일",
                     width=120, anchor="w").pack(side="left", padx=12)
        ctk.CTkEntry(self._ply_frame, textvariable=self._ply_var,
                     width=360).pack(side="left", padx=4)
        ctk.CTkButton(self._ply_frame, text="찾기", width=60,
                      command=self._pick_ply).pack(side="left", padx=4)

        # ── 출력 폴더 ─────────────────────────────────────────────────────
        out_frame = ctk.CTkFrame(self)
        out_frame.pack(fill="x", **pad)
        ctk.CTkLabel(out_frame, text="💾 출력 폴더",
                     width=120, anchor="w").pack(side="left", padx=12)
        ctk.CTkEntry(out_frame, textvariable=self._output_dir,
                     width=360).pack(side="left", padx=4)
        ctk.CTkButton(out_frame, text="찾기", width=60,
                      command=self._pick_output_dir).pack(side="left", padx=4)

        # ── 품질 ──────────────────────────────────────────────────────────
        self._quality_frame = ctk.CTkFrame(self)
        self._quality_frame.pack(fill="x", **pad)
        ctk.CTkLabel(self._quality_frame, text="⚙ 재구성 품질",
                     width=120, anchor="w").pack(side="left", padx=12)
        for q in ["lowest", "low", "medium", "high", "highest"]:
            ctk.CTkRadioButton(
                self._quality_frame, text=q,
                variable=self._quality, value=q,
            ).pack(side="left", padx=8)

        # ── 라이선스 ──────────────────────────────────────────────────────
        self._lic_frame = ctk.CTkFrame(self)
        self._lic_frame.pack(fill="x", **pad)
        ctk.CTkLabel(self._lic_frame, text="🔑 라이선스 키",
                     width=120, anchor="w").pack(side="left", padx=12)
        ctk.CTkEntry(self._lic_frame, textvariable=self._license,
                     show="*", width=360).pack(side="left", padx=4)
        ctk.CTkButton(self._lic_frame, text="저장", width=60,
                      command=self._save_license).pack(side="left", padx=4)

        # ── 진행 상황 ─────────────────────────────────────────────────────
        ctk.CTkLabel(self, text="진행 상황",
                     anchor="w").pack(fill="x", padx=20, pady=(12, 2))
        self._progress_bar = ctk.CTkProgressBar(self, width=640)
        self._progress_bar.pack(padx=20)
        self._progress_bar.set(0)

        self._status_label = ctk.CTkLabel(
            self, text="대기 중", text_color="gray",
            font=ctk.CTkFont(size=12),
        )
        self._status_label.pack(pady=(4, 0))

        # ── 결과 표시 ─────────────────────────────────────────────────────
        self._result_box = ctk.CTkTextbox(self, height=160, width=640,
                                          font=ctk.CTkFont(family="Courier", size=13))
        self._result_box.pack(padx=20, pady=10)
        self._result_box.insert("end", "결과가 여기에 표시됩니다.\n")
        self._result_box.configure(state="disabled")

        # ── 버튼 ──────────────────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=12)

        self._run_btn = ctk.CTkButton(
            btn_frame, text="▶  분석 시작", width=200, height=44,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._start,
        )
        self._run_btn.pack(side="left", padx=8)

        self._view_btn = ctk.CTkButton(
            btn_frame, text="🔍 3D 시각화", width=160, height=44,
            fg_color="#2d5a27", hover_color="#3a7a35",
            command=self._open_viewer,
            state="disabled",
        )
        self._view_btn.pack(side="left", padx=8)

        self._on_mode_change()

    # ── 이벤트 ───────────────────────────────────────────────────────────────

    def _on_mode_change(self):
        if self._mode.get() == "full":
            self._photo_frame.pack(fill="x", padx=20, pady=6, after=None)
            self._ply_frame.pack_forget()
            self._quality_frame.pack(fill="x", padx=20, pady=6)
            self._lic_frame.pack(fill="x", padx=20, pady=6)
        else:
            self._photo_frame.pack_forget()
            self._quality_frame.pack_forget()
            self._lic_frame.pack_forget()
            self._ply_frame.pack(fill="x", padx=20, pady=6)

    def _pick_photo_dir(self):
        d = filedialog.askdirectory(title="사진 폴더 선택")
        if d:
            self._photo_dir.set(d)

    def _pick_ply(self):
        f = filedialog.askopenfilename(
            title="PLY 파일 선택", filetypes=[("PLY files", "*.ply")]
        )
        if f:
            self._ply_var.set(f)

    def _pick_output_dir(self):
        d = filedialog.askdirectory(title="출력 폴더 선택")
        if d:
            self._output_dir.set(d)

    def _save_license(self):
        key = self._license.get().strip()
        if key:
            LICENSE_FILE.write_text(key)
            messagebox.showinfo("저장됨", "라이선스 키가 저장됐습니다.")

    def _load_license(self) -> str:
        if LICENSE_FILE.exists():
            return LICENSE_FILE.read_text().strip()
        return ""

    # ── 실행 ─────────────────────────────────────────────────────────────────

    def _start(self):
        self._run_btn.configure(state="disabled")
        self._view_btn.configure(state="disabled")
        self._progress_bar.set(0)
        self._result_image_path = None
        threading.Thread(target=self._run_pipeline, daemon=True).start()

    def _run_pipeline(self):
        try:
            from src.analysis      import analyze_angle_of_repose
            from src.visualization import save_result_plot

            output_dir = self._output_dir.get()
            Path(output_dir).mkdir(parents=True, exist_ok=True)

            if self._mode.get() == "full":
                from src.reconstruction import run_reconstruction
                self._update_status("재구성 시작...", 0)
                recon = run_reconstruction(
                    photo_dir       = self._photo_dir.get(),
                    output_dir      = output_dir,
                    license_key     = self._license.get().strip(),
                    quality         = self._quality.get(),
                    progress_callback = self._update_status,
                )
                ply_path = recon["ply"]
            else:
                ply_path = self._ply_var.get()

            # ── 분석 ────────────────────────────────────────────────────
            self._update_status("포인트 클라우드 분석 중...", 50)
            result = analyze_angle_of_repose(ply_path)

            self._update_status("결과 이미지 저장 중...", 90)
            img_path = save_result_plot(result, output_dir)
            self._result_image_path = img_path

            self._update_status("완료!", 100)
            self._show_result(result, ply_path)

        except Exception as e:
            self._update_status(f"오류: {e}", 0)
            self.after(0, lambda: messagebox.showerror("오류", str(e)))
        finally:
            self.after(0, lambda: self._run_btn.configure(state="normal"))

    def _show_result(self, result, ply_path: str):
        text = (
            f"{'='*46}\n"
            f"  안식각 (Angle of Repose) : {result.angle_deg:.2f}°\n"
            f"{'='*46}\n"
            f"  더미 높이    : {result.pile_height:.4f}\n"
            f"  더미 반지름  : {result.pile_radius:.4f}\n"
            f"  tan(α) = h/r : {result.pile_height / max(result.pile_radius, 1e-9):.4f}\n"
            f"  분석 포인트  : {result.n_points_pile:,} / {result.n_points_total:,}\n"
            f"{'='*46}\n"
            f"  결과 이미지  : {self._result_image_path}\n"
        )

        def _update():
            self._result_box.configure(state="normal")
            self._result_box.delete("1.0", "end")
            self._result_box.insert("end", text)
            self._result_box.configure(state="disabled")
            self._view_btn.configure(state="normal")
            self._ply_path_for_viewer = ply_path
            self._result_for_viewer   = result

        self.after(0, _update)

    def _open_viewer(self):
        try:
            from src.visualization import visualize_pointcloud
            visualize_pointcloud(
                self._ply_path_for_viewer,
                self._result_for_viewer,
                self._result_for_viewer.ground_plane,
            )
        except Exception as e:
            messagebox.showerror("시각화 오류", str(e))

    def _update_status(self, msg: str, pct: int):
        def _update():
            self._status_label.configure(text=msg)
            self._progress_bar.set(pct / 100)
        self.after(0, _update)


# ── 진입점 ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = AoRApp()
    app.mainloop()
