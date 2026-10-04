"""Robot Control Monitor — YOLO damage-panel camera console.

Run with: python3 app.py
"""

from __future__ import annotations

import time
import tkinter as tk
import queue
import threading
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk
import os

# The Tk window is the visible UI. A dummy SDL video driver lets pygame read
# USB joystick events without opening a second macOS window or Cocoa app loop.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
# Prefer SDL's direct HID path for a wired Nintendo Switch Pro Controller on macOS.
os.environ.setdefault("SDL_JOYSTICK_HIDAPI", "1")
os.environ.setdefault("SDL_JOYSTICK_HIDAPI_SWITCH", "1")
os.environ.setdefault("SDL_JOYSTICK_MFI", "0")

import cv2
import numpy as np
from PIL import Image, ImageTk
from ultralytics import YOLO
try:
    import pygame
except ImportError:  # The camera UI remains usable even if a controller is absent.
    pygame = None


# High-contrast palette intended to remain readable at a competition venue.
BG = "#0a1019"
PANEL = "#121c29"
PANEL_ALT = "#172434"
LINE = "#26394d"
TEXT = "#e8f0f7"
MUTED = "#94a8ba"
CYAN = "#22d3ee"
GREEN = "#4ade80"
AMBER = "#fbbf24"
RED = "#fb5267"
PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL_PATH = PROJECT_DIR.parent / "Panel_Yolo" / "best.pt"


@dataclass
class CameraStatus:
    connected: bool = False
    detecting: bool = True
    camera_index: int = 0
    frame_count: int = 0
    faces: int = 0
    last_time: float = 0.0
    fps: float = 0.0


class RobotControlMonitor(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("ROBOCON // VISION CONTROL")
        self.geometry("1440x900")
        self.minsize(960, 620)
        self.configure(bg=BG)
        self.status = CameraStatus()
        self.capture: cv2.VideoCapture | None = None
        self.photo: ImageTk.PhotoImage | None = None
        self.stream_id = 0  # Invalidates scheduled reads when reconnecting cameras.
        # State for lightweight digital image stabilization (no AI model required).
        self.stabilization_enabled = True
        self.previous_gray: np.ndarray | None = None
        self.trajectory = np.zeros(3, dtype=np.float32)
        self.smoothed_trajectory = np.zeros(3, dtype=np.float32)
        self.current_faces: list[tuple[int, int, int, int]] = []
        self.target_classes: list[tuple[str, float]] = []
        self.selected_target = 0
        self.hit_target: int | None = None
        self.hit_until = 0.0
        self.joystick: object | None = None
        self.controller_state = {"left": False, "right": False, "hit": False}
        self.controller_scan_at = 0.0
        # Long-range mode renders larger YOLO inputs; lower confidence helps tiny panels.
        self.confidence = tk.DoubleVar(value=0.35)
        # "BOTH" accepts all classes; the two other choices aid field diagnosis.
        self.allowed_class = tk.StringVar(value="BOTH")
        self.max_aspect_ratio = tk.DoubleVar(value=1.8)
        self.long_range_enabled = True
        self.inference_size = 960
        # Distance is calibrated from a known placement of the 145 mm square face.
        self.panel_size_mm = tk.StringVar(value="145")
        self.calibration_distance_mm = tk.StringVar(value="1000")
        self.focal_length_px: float | None = None
        # YOLO inference runs away from Tk's event loop so menus and buttons stay responsive.
        self.yolo_requests: queue.Queue[tuple[np.ndarray, float, int]] = queue.Queue(maxsize=1)
        self.yolo_results: queue.Queue[list[tuple[int, int, int, int, str, float]]] = queue.Queue(maxsize=1)
        self.latest_yolo_detections: list[tuple[int, int, int, int, str, float]] = []
        self.yolo_stop = threading.Event()
        self.yolo_error: str | None = None
        model_path = Path(os.environ.get("ROBOT_PANEL_MODEL", DEFAULT_MODEL_PATH))
        if not model_path.is_file():
            raise RuntimeError(
                f"YOLO model was not found: {model_path}\n"
                "Set ROBOT_PANEL_MODEL to the path of best.pt if it has been moved."
            )
        self.panel_model = YOLO(str(model_path))
        self.yolo_thread = threading.Thread(target=self._yolo_worker, name="yolo-inference", daemon=True)
        self.yolo_thread.start()

        self._configure_style()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<space>", lambda _event: self.toggle_detection())
        self.bind("<Escape>", lambda _event: self.emergency_stop())
        self.bind("<Left>", lambda _event: self.select_target(-1))
        self.bind("<Right>", lambda _event: self.select_target(1))
        self.bind("<Return>", lambda _event: self.hit_selected_target())
        self._setup_controller()
        self.after(50, self._poll_controller)
        self.after(300, self.connect_camera)

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground=PANEL_ALT, background=PANEL_ALT,
                        foreground=TEXT, arrowcolor=CYAN, bordercolor=LINE, padding=7)
        style.map("TCombobox", fieldbackground=[("readonly", PANEL_ALT)],
                  selectbackground=[("readonly", PANEL_ALT)], selectforeground=[("readonly", TEXT)])

    def _label(self, parent: tk.Widget, text: str, *, color: str = TEXT,
               size: int = 11, weight: str = "normal", **kwargs: object) -> tk.Label:
        return tk.Label(parent, text=text, fg=color, bg=parent.cget("bg"),
                        font=("Helvetica", size, weight), **kwargs)

    def _panel(self, parent: tk.Widget, **kwargs: object) -> tk.Frame:
        return tk.Frame(parent, bg=PANEL, highlightbackground=LINE, highlightthickness=1, **kwargs)

    def _button(self, parent: tk.Widget, text: str, command: object,
                *, accent: str = CYAN, **kwargs: object) -> tk.Button:
        foreground = kwargs.pop("fg", "#06111a")
        active_foreground = kwargs.pop("activeforeground", "#06111a")
        active_background = kwargs.pop("activebackground", "#a5f3fc" if accent == CYAN else accent)
        padx = kwargs.pop("padx", 16)
        pady = kwargs.pop("pady", 10)
        return tk.Button(parent, text=text, command=command, bg=accent, fg=foreground,
                         activebackground=active_background, activeforeground=active_foreground,
                         relief="flat", bd=0,
                         padx=padx, pady=pady, cursor="hand2",
                         font=("Helvetica", 10, "bold"), **kwargs)

    def _build_ui(self) -> None:
        # The camera is the stage; controls are deliberately kept at its edges.
        self.stage = tk.Frame(self, bg="#05080d")
        self.stage.pack(fill="both", expand=True)
        self.video = tk.Label(self.stage, bg="#05080d", fg=MUTED,
                              text="CAMERA INITIALIZING…", font=("Helvetica", 15, "bold"))
        self.video.pack(fill="both", expand=True)

        header = tk.Frame(self.stage, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        header.place(x=18, y=18, width=340, height=76)
        self._label(header, "ROBOCON / PANEL CONTROL", color=CYAN, size=11, weight="bold").pack(anchor="w", padx=14, pady=(11, 2))
        self.connection_label = self._label(header, "●  CONNECTING", color=AMBER, size=10, weight="bold")
        self.connection_label.pack(anchor="w", padx=14)
        self.system_label = self._label(header, "CAMERA OFFLINE", color=RED, size=9)
        self.system_label.pack(anchor="w", padx=14)
        self._tick_clock()

        controller = self._panel(self.stage)
        controller.place(relx=1, x=-18, y=18, anchor="ne", width=305, height=126)
        self._label(controller, "USB PRO CONTROLLER", color=MUTED, size=9, weight="bold").pack(anchor="w", padx=13, pady=(11, 3))
        self.controller_label = self._label(controller, "SEARCHING…", color=AMBER, size=10, weight="bold")
        self.controller_label.pack(anchor="w", padx=13)
        self._label(controller, "L2 / R2  SELECT     A  HIT!", color=TEXT, size=9, weight="bold").pack(anchor="w", padx=13, pady=(7, 0))
        self._label(controller, "Keyboard:  ← / → / Enter", color=MUTED, size=8).pack(anchor="w", padx=13, pady=(2, 0))

        footer = self._panel(self.stage)
        footer.place(x=18, rely=1, y=-18, anchor="sw", width=430, height=170)
        self.fps_label = self._label(footer, "FPS  --", color=MUTED, size=10, weight="bold")
        self.fps_label.place(x=14, y=13)
        self.face_label = self._label(footer, "TARGETS  0", color=GREEN, size=10, weight="bold")
        self.face_label.place(x=128, y=13)
        self.target_label = self._label(footer, "SELECT  --", color=AMBER, size=10, weight="bold")
        self.target_label.place(x=14, y=43)
        self.distance_label = self._label(footer, "DISTANCE  CALIBRATE TARGET", color=MUTED, size=10, weight="bold")
        self.distance_label.place(x=14, y=68)
        self._label(footer, "PANEL SIZE (mm)", color=MUTED, size=8, weight="bold").place(x=14, y=101)
        self._label(footer, "KNOWN RANGE (mm)", color=MUTED, size=8, weight="bold").place(x=142, y=101)
        entry_style = {"bg": PANEL_ALT, "fg": TEXT, "insertbackground": TEXT, "relief": "flat", "bd": 0,
                       "font": ("Helvetica", 10, "bold"), "justify": "center"}
        tk.Entry(footer, textvariable=self.panel_size_mm, width=10, **entry_style).place(x=14, y=121, height=25)
        tk.Entry(footer, textvariable=self.calibration_distance_mm, width=12, **entry_style).place(x=142, y=121, height=25)
        self._button(footer, "CALIBRATE SELECTED", self.calibrate_selected_target, accent=AMBER,
                     pady=5).place(x=260, y=116, width=154, height=34)

        controls = self._panel(self.stage)
        controls.place(relx=1, rely=1, x=-18, y=-18, anchor="se", width=250, height=250)
        controls.place_configure(height=430)
        self._label(controls, "PANEL YOLO SETTINGS", color=MUTED, size=9, weight="bold").pack(anchor="w", padx=14, pady=(12, 5))
        row = tk.Frame(controls, bg=PANEL)
        row.pack(fill="x", padx=14)
        self._label(row, "CAMERA", color=MUTED, size=9, weight="bold").pack(side="left")
        self.camera_choice = ttk.Combobox(row, values=("0", "1", "2", "3"), width=4, state="readonly")
        self.camera_choice.set("0")
        self.camera_choice.pack(side="right")
        self.camera_choice.bind("<<ComboboxSelected>>", lambda _event: self.change_camera())
        self.detection_btn = self._button(controls, "PANEL DETECTION: ON", self.toggle_detection, accent=GREEN)
        self.detection_btn.pack(fill="x", padx=14, pady=(9, 6))
        self.stabilization_btn = self._button(controls, "STABILIZATION: ON", self.toggle_stabilization, accent=CYAN)
        self.stabilization_btn.pack(fill="x", padx=14, pady=(0, 6))
        confidence_row = tk.Frame(controls, bg=PANEL)
        confidence_row.pack(fill="x", padx=14, pady=(0, 4))
        self.confidence_label = self._label(confidence_row, "CONFIDENCE  35%", color=AMBER, size=9, weight="bold")
        self.confidence_label.pack(anchor="w")
        tk.Scale(confidence_row, from_=0.10, to=0.95, resolution=0.05,
                 orient="horizontal", variable=self.confidence, command=self._update_confidence,
                 bg=PANEL, fg=TEXT, troughcolor=LINE, activebackground=CYAN,
                 highlightthickness=0, bd=0, length=205, showvalue=False).pack(anchor="w", pady=(0, 2))
        class_row = tk.Frame(controls, bg=PANEL)
        class_row.pack(fill="x", padx=14, pady=(0, 5))
        self._label(class_row, "ALLOW CLASS", color=MUTED, size=9, weight="bold").pack(anchor="w")
        class_buttons = tk.Frame(class_row, bg=PANEL)
        class_buttons.pack(fill="x", pady=(3, 0))
        self.class_buttons: dict[str, tk.Button] = {}
        for value, label in (("BOTH", "BOTH"), ("1", "1 ONLY"), ("Damage-Panel3", "PANEL 3")):
            button = self._button(class_buttons, label, lambda item=value: self.set_allowed_class(item),
                                  accent=CYAN, padx=5, pady=5)
            button.pack(side="left", fill="x", expand=True, padx=(0, 4))
            self.class_buttons[value] = button
        self._refresh_class_buttons()
        aspect_row = tk.Frame(controls, bg=PANEL)
        aspect_row.pack(fill="x", padx=14, pady=(0, 4))
        self.aspect_label = self._label(aspect_row, "MAX ASPECT  1.8 : 1", color=AMBER, size=9, weight="bold")
        self.aspect_label.pack(anchor="w")
        tk.Scale(aspect_row, from_=1.1, to=3.0, resolution=0.1,
                 orient="horizontal", variable=self.max_aspect_ratio, command=self._update_aspect_ratio,
                 bg=PANEL, fg=TEXT, troughcolor=LINE, activebackground=CYAN,
                 highlightthickness=0, bd=0, length=205, showvalue=False).pack(anchor="w", pady=(0, 2))
        self.long_range_btn = self._button(controls, "LONG RANGE: ON  /  960px", self.toggle_long_range, accent=AMBER)
        self.long_range_btn.pack(fill="x", padx=14, pady=(0, 6))
        self._button(controls, "EMERGENCY STOP", self.emergency_stop, accent=RED,
                     fg="white", activebackground="#ff8896", activeforeground="white").pack(fill="x", padx=14, pady=(0, 13))

    def _build_system_panel(self, parent: tk.Widget) -> None:
        panel = self._panel(parent)
        panel.pack(fill="x", pady=(0, 12))
        self._label(panel, "SYSTEM STATUS", color=MUTED, size=9, weight="bold").pack(anchor="w", padx=16, pady=(15, 9))
        self.system_label = self._label(panel, "CAMERA OFFLINE", color=RED, size=13, weight="bold")
        self.system_label.pack(anchor="w", padx=16)
        self._label(panel, "Vision pipeline / Haar Cascade", color=MUTED, size=9).pack(anchor="w", padx=16, pady=(4, 15))

    def _build_detection_panel(self, parent: tk.Widget) -> None:
        panel = self._panel(parent)
        panel.pack(fill="x", pady=(0, 12))
        self._label(panel, "VISION SETTINGS", color=MUTED, size=9, weight="bold").pack(anchor="w", padx=16, pady=(15, 10))
        row = tk.Frame(panel, bg=PANEL)
        row.pack(fill="x", padx=16)
        self._label(row, "CAMERA", color=MUTED, size=9, weight="bold").pack(side="left")
        self.camera_choice = ttk.Combobox(row, values=("0", "1", "2", "3"), width=5, state="readonly")
        self.camera_choice.set("0")
        self.camera_choice.pack(side="right")
        self.camera_choice.bind("<<ComboboxSelected>>", lambda _event: self.change_camera())

        self.detection_btn = self._button(panel, "FACE DETECTION: ON", self.toggle_detection, accent=GREEN)
        self.detection_btn.pack(fill="x", padx=16, pady=(13, 9))
        self.stabilization_btn = self._button(panel, "STABILIZATION: ON", self.toggle_stabilization, accent=CYAN)
        self.stabilization_btn.pack(fill="x", padx=16, pady=(0, 16))

    def _build_action_panel(self, parent: tk.Widget) -> None:
        panel = self._panel(parent)
        panel.pack(fill="x", pady=(0, 12))
        self._label(panel, "CAMERA CONTROL", color=MUTED, size=9, weight="bold").pack(anchor="w", padx=16, pady=(15, 10))
        self._button(panel, "RECONNECT CAMERA", self.connect_camera).pack(fill="x", padx=16, pady=(0, 9))
        self._button(panel, "EMERGENCY STOP", self.emergency_stop, accent=RED,
                     fg="white", activebackground="#ff8896", activeforeground="white").pack(fill="x", padx=16, pady=(0, 16))

    def _build_shortcuts(self, parent: tk.Widget) -> None:
        panel = tk.Frame(parent, bg=BG)
        panel.pack(fill="x", padx=2, pady=4)
        self._label(panel, "KEYBOARD", color=MUTED, size=9, weight="bold").pack(anchor="w", pady=(8, 5))
        self._label(panel, "SPACE   toggle face detection\nESC       emergency stop", color=MUTED, size=9,
                    justify="left", anchor="w").pack(anchor="w")

    def _tick_clock(self) -> None:
        self.title(f"ROBOCON // VISION CONTROL   {time.strftime('%H:%M:%S')}")
        self.after(1000, self._tick_clock)

    def connect_camera(self) -> None:
        self._release_camera()
        self.status.connected = False
        self.connection_label.configure(text="●  CONNECTING", fg=AMBER)
        self.system_label.configure(text="CAMERA CONNECTING", fg=AMBER)
        try:
            index = int(self.camera_choice.get())
            self.capture = cv2.VideoCapture(index)
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if not self.capture.isOpened():
                raise RuntimeError("camera could not be opened")
            self.status = CameraStatus(connected=True, detecting=self.status.detecting, camera_index=index,
                                       last_time=time.perf_counter())
            self._reset_stabilizer()
            self.stream_id += 1
            self.connection_label.configure(text="●  LIVE", fg=GREEN)
            self.system_label.configure(text="SYSTEM READY", fg=GREEN)
            self._read_frame(self.stream_id)
        except Exception:
            self._release_camera()
            self.connection_label.configure(text="●  OFFLINE", fg=RED)
            self.system_label.configure(text="CAMERA OFFLINE", fg=RED)
            self.video.configure(image="", text="CAMERA NOT FOUND\nCheck connection, then reconnect.")

    def _read_frame(self, stream_id: int) -> None:
        if stream_id != self.stream_id or not self.status.connected or self.capture is None:
            return
        ok, frame = self.capture.read()
        if not ok:
            self.status.connected = False
            self.connection_label.configure(text="●  SIGNAL LOST", fg=RED)
            self.system_label.configure(text="CAMERA SIGNAL LOST", fg=RED)
            self.video.configure(image="", text="CAMERA SIGNAL LOST")
            return
        if self.stabilization_enabled:
            frame = self._stabilize_frame(frame)
        if self.status.detecting:
            self._queue_yolo_frame(frame)
            self._draw_panels(frame)
        self._show_frame(frame)
        # Keeping drawing at ~30fps reserves Tk time for physical control buttons.
        self.after(33, lambda: self._read_frame(stream_id))

    def _reset_stabilizer(self) -> None:
        """Clear motion history after a reconnect or a setting change."""
        self.previous_gray = None
        self.trajectory.fill(0)
        self.smoothed_trajectory.fill(0)

    def _stabilize_frame(self, frame: np.ndarray) -> np.ndarray:
        """Counter small camera translation/rotation using sparse optical flow.

        This is intentionally lightweight: Shi-Tomasi feature points and Lucas-Kanade
        optical flow run efficiently on a robot's CPU and need no model download.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if self.previous_gray is None:
            self.previous_gray = gray
            return frame

        points = cv2.goodFeaturesToTrack(
            self.previous_gray, maxCorners=120, qualityLevel=0.015,
            minDistance=24, blockSize=5,
        )
        if points is None or len(points) < 8:
            self.previous_gray = gray
            return frame

        next_points, valid, _ = cv2.calcOpticalFlowPyrLK(
            self.previous_gray, gray, points, None,
            winSize=(21, 21), maxLevel=3,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.03),
        )
        self.previous_gray = gray
        if next_points is None or valid is None:
            return frame
        valid = valid.ravel().astype(bool)
        if valid.sum() < 8:
            return frame

        transform, _ = cv2.estimateAffinePartial2D(
            points[valid], next_points[valid], method=cv2.RANSAC,
        )
        if transform is None:
            return frame
        dx, dy = transform[0, 2], transform[1, 2]
        angle = np.arctan2(transform[1, 0], transform[0, 0])

        # Ignore implausibly large estimates caused by a tracking failure.
        if abs(dx) > 45 or abs(dy) > 45 or abs(angle) > np.deg2rad(8):
            return frame

        self.trajectory += (dx, dy, angle)
        # Higher value means steadier output but slightly more delayed camera motion.
        smoothing = 0.84
        self.smoothed_trajectory = (
            smoothing * self.smoothed_trajectory + (1 - smoothing) * self.trajectory
        )
        correction = self.smoothed_trajectory - self.trajectory
        stabilized_dx, stabilized_dy, stabilized_angle = (dx, dy, angle) + correction
        cos_a, sin_a = np.cos(stabilized_angle), np.sin(stabilized_angle)
        matrix = np.array(
            [[cos_a, -sin_a, stabilized_dx], [sin_a, cos_a, stabilized_dy]], dtype=np.float32
        )
        height, width = frame.shape[:2]
        stabilized = cv2.warpAffine(
            frame, matrix, (width, height), flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )
        # A small crop removes the replicated-edge border created during correction.
        crop = 0.025
        x, y = int(width * crop), int(height * crop)
        inner = stabilized[y:height - y, x:width - x]
        return cv2.resize(inner, (width, height), interpolation=cv2.INTER_LINEAR)

    def _setup_controller(self) -> None:
        """Start pygame's joystick subsystem; reconnects are handled by polling."""
        if pygame is None:
            self.controller_label.configure(text="PYGAME NOT INSTALLED", fg=RED)
            return
        try:
            # pygame's event pump (needed for USB hot-plug and button states)
            # requires its event/video subsystem in addition to joystick support.
            # No pygame window is created; Tk remains the only visible UI.
            pygame.init()
            pygame.joystick.init()
        except pygame.error:
            self.controller_label.configure(text="CONTROLLER UNAVAILABLE", fg=RED)

    def _poll_controller(self) -> None:
        if pygame is None:
            return
        try:
            pygame.event.pump()
            now = time.monotonic()
            if self.joystick is None or not self.joystick.get_init():
                if now >= self.controller_scan_at:
                    self.controller_scan_at = now + 1.0
                    if pygame.joystick.get_count():
                        self.joystick = pygame.joystick.Joystick(0)
                        self.joystick.init()
                        name = self.joystick.get_name()
                        self.controller_label.configure(text=f"● CONNECTED", fg=GREEN)
                        self.title(f"ROBOCON // {name[:24]} CONNECTED")
                    else:
                        self.controller_label.configure(text="SEARCHING…", fg=AMBER)
            if self.joystick is not None and self.joystick.get_init():
                # Nintendo Pro Controller / SDL mapping: A=1, ZL/L2=6, ZR/R2=7.
                # Some drivers expose the two triggers as axes 4 and 5 instead.
                left = self._controller_button(6) or self._controller_trigger_axis(4)
                right = self._controller_button(7) or self._controller_trigger_axis(5)
                hit = self._controller_button(1)
                self._controller_edge("left", left, lambda: self.select_target(-1))
                self._controller_edge("right", right, lambda: self.select_target(1))
                self._controller_edge("hit", hit, self.hit_selected_target)
        except pygame.error:
            self.joystick = None
            self.controller_label.configure(text="RECONNECT CONTROLLER", fg=AMBER)
        self.after(50, self._poll_controller)

    def _controller_button(self, index: int) -> bool:
        return bool(self.joystick is not None and self.joystick.get_numbuttons() > index
                    and self.joystick.get_button(index))

    def _controller_trigger_axis(self, index: int) -> bool:
        if self.joystick is None or self.joystick.get_numaxes() <= index:
            return False
        return self.joystick.get_axis(index) > 0.55

    def _controller_edge(self, name: str, pressed: bool, action: object) -> None:
        was_pressed = self.controller_state[name]
        self.controller_state[name] = pressed
        if pressed and not was_pressed:
            action()

    def select_target(self, direction: int) -> None:
        if not self.current_faces:
            return
        self.selected_target = (self.selected_target + direction) % len(self.current_faces)

    def hit_selected_target(self) -> None:
        if not self.current_faces:
            self.target_label.configure(text="SELECT  --  NO TARGET", fg=RED)
            return
        self.hit_target = self.selected_target
        self.hit_until = time.monotonic() + 1.4

    def _queue_yolo_frame(self, frame: np.ndarray) -> None:
        """Submit only the newest camera frame; never let inference build a backlog."""
        try:
            self.yolo_requests.put_nowait((frame.copy(), float(self.confidence.get()), self.inference_size))
        except queue.Full:
            pass

    def _yolo_worker(self) -> None:
        while not self.yolo_stop.is_set():
            try:
                frame, confidence_threshold, image_size = self.yolo_requests.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                result = self.panel_model.predict(
                    frame, conf=confidence_threshold, imgsz=image_size, verbose=False,
                )[0]
                detections: list[tuple[int, int, int, int, str, float]] = []
                if result.boxes is not None:
                    for box in result.boxes:
                        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                        class_id = int(box.cls[0].item())
                        detections.append((x1, y1, x2 - x1, y2 - y1,
                                           str(result.names[class_id]), float(box.conf[0].item())))
                # Keep only the newest result, matching it to the live display as closely as possible.
                while True:
                    try:
                        self.yolo_results.get_nowait()
                    except queue.Empty:
                        break
                self.yolo_results.put_nowait(detections)
            except Exception as error:
                self.yolo_error = str(error)

    def _draw_panels(self, frame: np.ndarray) -> None:
        """Draw the latest worker result; this must stay fast for interactive controls."""
        try:
            while True:
                self.latest_yolo_detections = self.yolo_results.get_nowait()
        except queue.Empty:
            pass
        selected_class = self.allowed_class.get()
        max_ratio = float(self.max_aspect_ratio.get())
        detections = [detection for detection in self.latest_yolo_detections
                      if (selected_class == "BOTH" or detection[4] == selected_class)
                      and self._is_panel_shaped(detection[2], detection[3], max_ratio)]
        # IDs are reassigned every frame in screen-left to screen-right order.
        detections.sort(key=lambda detection: detection[0])
        self.current_faces = [detection[:4] for detection in detections]
        self.target_classes = [(detection[4], detection[5]) for detection in detections]
        self.status.faces = len(self.current_faces)
        if self.current_faces:
            self.selected_target = min(self.selected_target, len(self.current_faces) - 1)
        else:
            self.selected_target = 0
            self.hit_target = None
        now = time.monotonic()
        for index, (x, y, w, h) in enumerate(self.current_faces):
            class_name, confidence = self.target_classes[index]
            selected = index == self.selected_target
            hit = index == self.hit_target and now < self.hit_until
            color = (34, 211, 238)
            thickness = 3
            if selected:
                color, thickness = (36, 190, 251), 5
            if hit:
                color = (70, 255, 255) if int(now * 12) % 2 else (120, 30, 255)
                thickness = 9
                cv2.putText(frame, "[ HIT! ]", (x, max(48, y - 42)), cv2.FONT_HERSHEY_DUPLEX,
                            1.15, color, 3, cv2.LINE_AA)
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, thickness)
            range_text = self._format_distance(self._estimate_distance_mm(w, h))
            tag = f"{class_name.upper()}  ID {index + 1:02d}  {confidence:.0%}  {range_text}" + ("  SELECT" if selected else "")
            tag_width = min(max(130, 12 * len(tag)), max(130, frame.shape[1] - x))
            cv2.rectangle(frame, (x, max(0, y - 27)), (x + tag_width, y), color, -1)
            cv2.putText(frame, tag, (x + 6, y - 8), cv2.FONT_HERSHEY_SIMPLEX, .48,
                        (5, 16, 25), 1, cv2.LINE_AA)
        if self.hit_target is not None and now >= self.hit_until:
            self.hit_target = None

    def _show_frame(self, frame: object) -> None:
        now = time.perf_counter()
        self.status.frame_count += 1
        elapsed = now - self.status.last_time
        if elapsed >= .5:
            self.status.fps = self.status.frame_count / elapsed
            self.status.frame_count = 0
            self.status.last_time = now
        self.fps_label.configure(text=f"FPS  {self.status.fps:4.1f}")
        self.face_label.configure(text=f"TARGETS  {self.status.faces}")
        target = f"SELECT  ID {self.selected_target + 1:02d}" if self.current_faces else "SELECT  --"
        self.target_label.configure(text=target, fg=AMBER)
        if self.current_faces:
            x, y, w, h = self.current_faces[self.selected_target]
            distance = self._estimate_distance_mm(w, h)
            self.distance_label.configure(text=f"DISTANCE  {self._format_distance(distance)}", fg=GREEN if distance else MUTED)
        else:
            self.distance_label.configure(text="DISTANCE  CALIBRATE TARGET", fg=MUTED)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        # Crop to fill the full stage rather than showing letterbox borders.
        max_w, max_h = max(self.stage.winfo_width(), 960), max(self.stage.winfo_height(), 620)
        scale = max(max_w / image.width, max_h / image.height)
        resized = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
        left = (resized.width - max_w) // 2
        top = (resized.height - max_h) // 2
        image = resized.crop((left, top, left + max_w, top + max_h))
        self.photo = ImageTk.PhotoImage(image=image)
        self.video.configure(image=self.photo, text="")

    def toggle_detection(self) -> None:
        self.status.detecting = not self.status.detecting
        enabled = self.status.detecting
        self.detection_btn.configure(text=f"PANEL DETECTION: {'ON' if enabled else 'OFF'}",
                                     bg=GREEN if enabled else PANEL_ALT,
                                     fg="#06111a" if enabled else TEXT)
        if not enabled:
            self.status.faces = 0
            self.current_faces = []
            self.hit_target = None

    def _update_confidence(self, _value: str) -> None:
        self.confidence_label.configure(text=f"CONFIDENCE  {self.confidence.get():.0%}")

    def _update_aspect_ratio(self, _value: str) -> None:
        self.aspect_label.configure(text=f"MAX ASPECT  {self.max_aspect_ratio.get():.1f} : 1")

    @staticmethod
    def _is_panel_shaped(width: int, height: int, max_ratio: float) -> bool:
        """Keep square-like targets and reject very wide or tall false positives."""
        if width <= 0 or height <= 0:
            return False
        return max(width / height, height / width) <= max_ratio

    def set_allowed_class(self, class_name: str) -> None:
        self.allowed_class.set(class_name)
        self._refresh_class_buttons()

    def _refresh_class_buttons(self) -> None:
        for class_name, button in self.class_buttons.items():
            selected = class_name == self.allowed_class.get()
            button.configure(bg=GREEN if selected else PANEL_ALT,
                             fg="#06111a" if selected else TEXT,
                             activebackground=GREEN if selected else PANEL_ALT)

    def toggle_long_range(self) -> None:
        self.long_range_enabled = not self.long_range_enabled
        self.inference_size = 960 if self.long_range_enabled else 640
        self.long_range_btn.configure(
            text=f"LONG RANGE: {'ON' if self.long_range_enabled else 'OFF'}  /  {self.inference_size}px",
            bg=AMBER if self.long_range_enabled else PANEL_ALT,
            fg="#06111a" if self.long_range_enabled else TEXT,
        )

    def _measurement_mm(self, value: tk.StringVar, name: str) -> float | None:
        try:
            result = float(value.get())
            return result if result > 0 else None
        except ValueError:
            return None

    def calibrate_selected_target(self) -> None:
        """Calculate focal length in pixels from a front-facing, known-distance panel."""
        if not self.current_faces:
            self.distance_label.configure(text="DISTANCE  NO TARGET TO CALIBRATE", fg=RED)
            return
        panel_size = self._measurement_mm(self.panel_size_mm, "panel size")
        known_range = self._measurement_mm(self.calibration_distance_mm, "known range")
        if panel_size is None or known_range is None:
            self.distance_label.configure(text="DISTANCE  ENTER VALID mm VALUES", fg=RED)
            return
        _, _, width, height = self.current_faces[self.selected_target]
        pixel_side = float(np.sqrt(width * height))
        if pixel_side < 2:
            self.distance_label.configure(text="DISTANCE  TARGET TOO SMALL", fg=RED)
            return
        self.focal_length_px = pixel_side * known_range / panel_size
        self.distance_label.configure(text=f"DISTANCE  CALIBRATED  {self._format_distance(known_range)}", fg=GREEN)

    def _estimate_distance_mm(self, width: int, height: int) -> float | None:
        panel_size = self._measurement_mm(self.panel_size_mm, "panel size")
        if self.focal_length_px is None or panel_size is None or width <= 0 or height <= 0:
            return None
        # Geometric mean handles modest perspective skew better than either edge alone.
        pixel_side = float(np.sqrt(width * height))
        return self.focal_length_px * panel_size / pixel_side

    @staticmethod
    def _format_distance(distance_mm: float | None) -> str:
        if distance_mm is None:
            return "--"
        return f"{distance_mm / 1000:.2f} m" if distance_mm >= 1000 else f"{distance_mm:.0f} mm"

    def toggle_stabilization(self) -> None:
        self.stabilization_enabled = not self.stabilization_enabled
        self._reset_stabilizer()
        enabled = self.stabilization_enabled
        self.stabilization_btn.configure(
            text=f"STABILIZATION: {'ON' if enabled else 'OFF'}",
            bg=CYAN if enabled else PANEL_ALT,
            fg="#06111a" if enabled else TEXT,
        )

    def change_camera(self) -> None:
        self.connect_camera()

    def emergency_stop(self) -> None:
        self._release_camera()
        self.status.connected = False
        self.connection_label.configure(text="●  STOPPED", fg=RED)
        self.system_label.configure(text="EMERGENCY STOP ACTIVE", fg=RED)
        self.video.configure(image="", text="EMERGENCY STOP\nCamera feed paused")
        self.fps_label.configure(text="FPS  --")
        self.face_label.configure(text="FACES  --")

    def _release_camera(self) -> None:
        self.stream_id += 1
        if self.capture is not None:
            self.capture.release()
            self.capture = None

    def _close(self) -> None:
        self._release_camera()
        self.yolo_stop.set()
        self.yolo_thread.join(timeout=0.25)
        self.destroy()


if __name__ == "__main__":
    RobotControlMonitor().mainloop()
