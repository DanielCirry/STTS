"""
VR OCR Overlay — Adds OCR-specific overlays to SteamVR.

Creates and manages:
- Cyan OCR toggle button (camera/scan icon)
- Capture region rectangle (semi-transparent, shows scan area)
- Camera button (attached to right edge of region, triggers capture)
- Corner handles (4 cyan spheres for resizing, selection mode only)
- Close button (X at top-right, exits selection mode)

Also handles controller button polling for OCR capture/toggle bindings.
"""

import logging
import math
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

logger = logging.getLogger('stts.vr_ocr_overlay')

# OCR overlay colors
CYAN = (0, 229, 255, 230)          # #00E5FF — OCR button + handles
CYAN_HIGHLIGHT = (255, 255, 255, 240)  # White highlight for hover
REGION_FILL = (255, 255, 255, 38)   # ~15% opacity white
REGION_BORDER = (200, 200, 200, 100)  # Light gray border
CAMERA_BG = (60, 60, 60, 220)       # Dark background for camera button
CAMERA_FG = (255, 255, 255, 255)    # White icon
CLOSE_BG = (200, 60, 60, 220)       # Red background for close button
CLOSE_FG = (255, 255, 255, 255)     # White X

# Button map for controller bindings
BUTTON_MAP = {}  # Populated lazily when openvr is available

# Overlay texture sizes
BUTTON_TEX_SIZE = 128
REGION_TEX_SIZE = 512
CAMERA_TEX_SIZE = 64
CORNER_TEX_SIZE = 32
CLOSE_TEX_SIZE = 48


def _init_button_map():
    """Initialize button map from openvr constants."""
    global BUTTON_MAP
    if BUTTON_MAP:
        return
    try:
        import openvr
        BUTTON_MAP.update({
            'grip': openvr.ButtonMaskFromId(openvr.k_EButton_Grip),
            'trigger': openvr.ButtonMaskFromId(openvr.k_EButton_SteamVR_Trigger),
            'a': openvr.ButtonMaskFromId(openvr.k_EButton_A),
            'b': openvr.ButtonMaskFromId(openvr.k_EButton_ApplicationMenu),
            'trackpad': openvr.ButtonMaskFromId(openvr.k_EButton_SteamVR_Touchpad),
        })
    except Exception as e:
        logger.warning(f"[vr_ocr] Failed to init button map: {e}")


class VROCROverlay:
    """Manages OCR-specific VR overlays and controller polling."""

    def __init__(self):
        self._openvr = None
        self._is_initialized = False

        # Overlay handles
        self._button_handle = None       # Cyan OCR toggle button
        self._region_handle = None       # Capture region rectangle
        self._camera_handle = None       # Camera button (on region right edge)
        self._corner_handles = [None, None, None, None]  # 4 corner resize handles
        self._close_handle = None        # X close button (selection mode)
        self._translation_handle = None  # Translation overlay (rendered OCR results)

        # State
        self._enabled = False            # OCR feature enabled
        self._region_visible = False     # Capture region shown
        self._selection_mode = False     # Corner handles visible for resize
        self._first_selection = True     # Show tooltip on first selection

        # Positions (VR meters)
        self._button_pos = {'x': 0.25, 'y': -0.3, 'width': 0.06, 'distance': 1.5, 'tracking': 'none'}
        self._region_pos = {'x': 0.0, 'y': -0.1, 'width': 0.5, 'height': 0.15, 'distance': 1.5}

        # Controller polling
        self._controller_enabled = False
        self._capture_binding: List[str] = ['right_grip']
        self._toggle_binding: List[str] = ['left_grip', 'left_a']
        self._poll_thread: Optional[threading.Thread] = None
        self._should_poll = False
        self._capture_combo_held = False  # For rising-edge detection
        self._toggle_combo_held = False

        # Callbacks
        self.on_capture_triggered: Optional[Callable] = None
        self.on_toggle_region: Optional[Callable] = None
        self.on_region_changed: Optional[Callable[[Dict], None]] = None

    def initialize(self, openvr_instance) -> bool:
        """Initialize OCR overlays using an existing OpenVR session."""
        if self._is_initialized:
            return True

        if not openvr_instance:
            return False

        self._openvr = openvr_instance

        try:
            import openvr
            overlay = openvr.IVROverlay()
            _init_button_map()

            # Create cyan OCR toggle button
            err, self._button_handle = overlay.createOverlay(
                b"stts.ocr.button", b"OCR Toggle Button"
            )
            if err != openvr.VROverlayError_None:
                logger.error(f"[vr_ocr] Failed to create button overlay: {err}")
                return False
            logger.debug("[vr_ocr] Created OCR button overlay")

            # Create capture region rectangle
            err, self._region_handle = overlay.createOverlay(
                b"stts.ocr.region", b"OCR Capture Region"
            )
            if err != openvr.VROverlayError_None:
                logger.warning(f"[vr_ocr] Failed to create region overlay: {err}")
                self._region_handle = None

            # Create camera button
            err, self._camera_handle = overlay.createOverlay(
                b"stts.ocr.camera", b"OCR Camera Button"
            )
            if err != openvr.VROverlayError_None:
                logger.warning(f"[vr_ocr] Failed to create camera overlay: {err}")
                self._camera_handle = None

            # Create translation result overlay (sits on top of region)
            err, self._translation_handle = overlay.createOverlay(
                b"stts.ocr.translation", b"OCR Translation"
            )
            if err != openvr.VROverlayError_None:
                logger.warning(f"[vr_ocr] Failed to create translation overlay: {err}")
                self._translation_handle = None

            # Create corner handles (selection mode)
            for i in range(4):
                err, handle = overlay.createOverlay(
                    f"stts.ocr.corner.{i}".encode(), f"OCR Corner {i}".encode()
                )
                if err == openvr.VROverlayError_None:
                    self._corner_handles[i] = handle
                else:
                    logger.warning(f"[vr_ocr] Failed to create corner {i}: {err}")

            # Create close button
            err, self._close_handle = overlay.createOverlay(
                b"stts.ocr.close", b"OCR Close Button"
            )
            if err != openvr.VROverlayError_None:
                logger.warning(f"[vr_ocr] Failed to create close overlay: {err}")
                self._close_handle = None

            # Render initial textures
            self._render_button_texture()
            self._render_region_texture()
            self._render_camera_texture()
            self._render_corner_textures()
            self._render_close_texture()

            # Configure initial positions (all hidden)
            self._configure_overlays()

            # Enable overlay input for clickable overlays
            self._enable_overlay_input()

            self._is_initialized = True
            logger.info("[vr_ocr] OCR overlays initialized")
            return True

        except ImportError:
            logger.warning("[vr_ocr] openvr not installed")
            return False
        except Exception as e:
            logger.error(f"[vr_ocr] Failed to initialize: {e}")
            return False

    def _enable_overlay_input(self):
        """Enable mouse/laser input events on interactive overlays."""
        if not self._openvr:
            return
        try:
            import openvr
            overlay = openvr.IVROverlay()

            # Button overlay: mouse events for click
            for handle in [self._button_handle, self._camera_handle, self._close_handle]:
                if handle:
                    overlay.setOverlayInputMethod(handle, openvr.VROverlayInputMethod_Mouse)

            # Corner handles: mouse events for drag
            for handle in self._corner_handles:
                if handle:
                    overlay.setOverlayInputMethod(handle, openvr.VROverlayInputMethod_Mouse)

        except Exception as e:
            logger.error(f"[vr_ocr] Failed to enable input: {e}")

    def _configure_overlays(self):
        """Configure overlay positions, sizes, and visibility."""
        if not self._openvr:
            return

        try:
            import openvr
            overlay = openvr.IVROverlay()

            # --- Cyan OCR button ---
            if self._button_handle:
                overlay.setOverlayWidthInMeters(self._button_handle, self._button_pos['width'])
                overlay.setOverlayAlpha(self._button_handle, 0.9)
                self._update_position(self._button_handle,
                                      self._button_pos['distance'],
                                      self._button_pos['y'],
                                      self._button_pos['x'],
                                      self._button_pos.get('tracking', 'none'))
                if self._enabled:
                    overlay.showOverlay(self._button_handle)
                else:
                    overlay.hideOverlay(self._button_handle)

            # --- Capture region ---
            if self._region_handle:
                overlay.setOverlayWidthInMeters(self._region_handle, self._region_pos['width'])
                overlay.setOverlayAlpha(self._region_handle, 0.5)
                self._update_position(self._region_handle,
                                      self._region_pos['distance'],
                                      self._region_pos['y'],
                                      self._region_pos['x'],
                                      'none')
                if self._enabled and self._region_visible:
                    overlay.showOverlay(self._region_handle)
                else:
                    overlay.hideOverlay(self._region_handle)

            # --- Camera button (right edge of region) ---
            if self._camera_handle:
                cam_width = 0.04  # Small camera icon
                overlay.setOverlayWidthInMeters(self._camera_handle, cam_width)
                overlay.setOverlayAlpha(self._camera_handle, 0.9)
                cam_x = self._region_pos['x'] + self._region_pos['width'] / 2 + cam_width / 2 + 0.01
                self._update_position(self._camera_handle,
                                      self._region_pos['distance'],
                                      self._region_pos['y'],
                                      cam_x,
                                      'none')
                if self._enabled and self._region_visible:
                    overlay.showOverlay(self._camera_handle)
                else:
                    overlay.hideOverlay(self._camera_handle)

            # --- Translation overlay (same position as region) ---
            if self._translation_handle:
                overlay.setOverlayWidthInMeters(self._translation_handle, self._region_pos['width'])
                overlay.setOverlayAlpha(self._translation_handle, 1.0)
                # Slightly in front of region so it covers original text
                self._update_position(self._translation_handle,
                                      self._region_pos['distance'] - 0.001,
                                      self._region_pos['y'],
                                      self._region_pos['x'],
                                      'none')
                if self._enabled and self._region_visible:
                    overlay.showOverlay(self._translation_handle)
                else:
                    overlay.hideOverlay(self._translation_handle)

            # --- Corner handles (selection mode only) ---
            self._update_corner_positions()

            # --- Close button (selection mode only) ---
            if self._close_handle:
                close_width = 0.03
                overlay.setOverlayWidthInMeters(self._close_handle, close_width)
                overlay.setOverlayAlpha(self._close_handle, 0.9)
                close_x = self._region_pos['x'] + self._region_pos['width'] / 2 + 0.02
                close_y = self._region_pos['y'] + self._region_pos['height'] / 2 + 0.02
                self._update_position(self._close_handle,
                                      self._region_pos['distance'] - 0.002,
                                      close_y, close_x, 'none')
                if self._selection_mode:
                    overlay.showOverlay(self._close_handle)
                else:
                    overlay.hideOverlay(self._close_handle)

        except Exception as e:
            logger.error(f"[vr_ocr] Failed to configure overlays: {e}")

    def _update_corner_positions(self):
        """Update corner handle positions based on current region."""
        if not self._openvr:
            return

        try:
            import openvr
            overlay = openvr.IVROverlay()

            corner_width = 0.02  # Small sphere
            hw = self._region_pos['width'] / 2
            hh = self._region_pos.get('height', 0.15) / 2
            cx = self._region_pos['x']
            cy = self._region_pos['y']
            dist = self._region_pos['distance'] - 0.002

            corners = [
                (cx - hw, cy + hh),  # top-left
                (cx + hw, cy + hh),  # top-right
                (cx - hw, cy - hh),  # bottom-left
                (cx + hw, cy - hh),  # bottom-right
            ]

            for i, handle in enumerate(self._corner_handles):
                if not handle:
                    continue
                overlay.setOverlayWidthInMeters(handle, corner_width)
                overlay.setOverlayAlpha(handle, 0.8)
                self._update_position(handle, dist, corners[i][1], corners[i][0], 'none')
                if self._selection_mode:
                    overlay.showOverlay(handle)
                else:
                    overlay.hideOverlay(handle)

        except Exception as e:
            logger.error(f"[vr_ocr] Failed to update corner positions: {e}")

    def _update_position(self, handle, distance: float, v_offset: float,
                         h_offset: float, tracking: str = 'none'):
        """Set overlay transform relative to tracked device."""
        if not self._openvr or not handle:
            return

        try:
            import openvr
            overlay_api = openvr.IVROverlay()

            transform = openvr.HmdMatrix34_t()
            transform.m[0][0] = 1.0
            transform.m[1][1] = 1.0
            transform.m[2][2] = 1.0
            transform.m[0][3] = h_offset
            transform.m[1][3] = v_offset
            transform.m[2][3] = -distance

            device_index = self._get_device_index(tracking)
            overlay_api.setOverlayTransformTrackedDeviceRelative(
                handle, device_index, transform
            )
        except Exception as e:
            logger.error(f"[vr_ocr] Failed to update position: {e}")

    def _get_device_index(self, tracking: str):
        """Get OpenVR tracked device index."""
        import openvr
        if tracking == 'left_hand':
            return openvr.VRSystem().getTrackedDeviceIndexForControllerRole(
                openvr.TrackedControllerRole_LeftHand)
        elif tracking == 'right_hand':
            return openvr.VRSystem().getTrackedDeviceIndexForControllerRole(
                openvr.TrackedControllerRole_RightHand)
        return openvr.k_unTrackedDeviceIndex_Hmd

    # ── Texture Rendering ─────────────────────────────────────────────

    def _update_texture(self, handle, rgba_array: np.ndarray):
        """Push RGBA texture to an overlay."""
        if not self._openvr or not handle:
            return
        try:
            import openvr
            overlay = openvr.IVROverlay()
            bgra = rgba_array.copy()
            bgra[:, :, [0, 2]] = bgra[:, :, [2, 0]]
            h, w = bgra.shape[:2]
            overlay.setOverlayRaw(
                handle,
                bgra.ctypes.data_as(openvr.POINTER(openvr.c_char)),
                w, h, 4
            )
        except Exception as e:
            logger.error(f"[vr_ocr] Failed to update texture: {e}")

    def _render_button_texture(self):
        """Render the cyan OCR toggle button (camera icon)."""
        if not PIL_AVAILABLE or not self._button_handle:
            return

        s = BUTTON_TEX_SIZE
        img = Image.new('RGBA', (s, s), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Cyan circle background
        padding = 8
        draw.ellipse([padding, padding, s - padding, s - padding], fill=CYAN)

        # Camera icon (simplified)
        cx, cy = s // 2, s // 2
        # Camera body
        bw, bh = 36, 26
        draw.rounded_rectangle(
            [cx - bw//2, cy - bh//2 + 2, cx + bw//2, cy + bh//2 + 2],
            radius=4, fill=CAMERA_BG
        )
        # Lens circle
        draw.ellipse([cx - 10, cy - 8, cx + 10, cy + 12], fill=CAMERA_FG)
        draw.ellipse([cx - 6, cy - 4, cx + 6, cy + 8], fill=CAMERA_BG)
        # Flash bump
        draw.rectangle([cx - 16, cy - bh//2 - 2, cx - 8, cy - bh//2 + 4], fill=CAMERA_BG)

        self._update_texture(self._button_handle, np.array(img))
        logger.debug("[vr_ocr] Button texture rendered")

    def _render_region_texture(self):
        """Render the capture region rectangle (semi-transparent)."""
        if not PIL_AVAILABLE or not self._region_handle:
            return

        s = REGION_TEX_SIZE
        img = Image.new('RGBA', (s, s), REGION_FILL)
        draw = ImageDraw.Draw(img)

        # Border
        border = 3
        draw.rectangle([0, 0, s-1, s-1], outline=REGION_BORDER, width=border)

        # "OCR" label in top-left
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 24)
        except Exception:
            font = ImageFont.load_default()
        draw.text((10, 6), "OCR", font=font, fill=(200, 200, 200, 150))

        self._update_texture(self._region_handle, np.array(img))
        logger.debug("[vr_ocr] Region texture rendered")

    def _render_camera_texture(self):
        """Render the camera capture button."""
        if not PIL_AVAILABLE or not self._camera_handle:
            return

        s = CAMERA_TEX_SIZE
        img = Image.new('RGBA', (s, s), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Dark circle
        draw.ellipse([2, 2, s-2, s-2], fill=CAMERA_BG)
        # Camera icon (simplified lens)
        cx, cy = s // 2, s // 2
        draw.ellipse([cx-12, cy-12, cx+12, cy+12], outline=CAMERA_FG, width=2)
        draw.ellipse([cx-6, cy-6, cx+6, cy+6], fill=CAMERA_FG)

        self._update_texture(self._camera_handle, np.array(img))

    def _render_corner_textures(self):
        """Render cyan sphere textures for corner handles."""
        if not PIL_AVAILABLE:
            return

        s = CORNER_TEX_SIZE
        img = Image.new('RGBA', (s, s), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([2, 2, s-2, s-2], fill=CYAN)

        texture = np.array(img)
        for handle in self._corner_handles:
            if handle:
                self._update_texture(handle, texture)

    def _render_close_texture(self):
        """Render the X close button."""
        if not PIL_AVAILABLE or not self._close_handle:
            return

        s = CLOSE_TEX_SIZE
        img = Image.new('RGBA', (s, s), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Red circle
        draw.ellipse([2, 2, s-2, s-2], fill=CLOSE_BG)
        # White X
        p = 14
        draw.line([(p, p), (s-p, s-p)], fill=CLOSE_FG, width=3)
        draw.line([(s-p, p), (p, s-p)], fill=CLOSE_FG, width=3)

        self._update_texture(self._close_handle, np.array(img))

    # ── Public API ────────────────────────────────────────────────────

    def set_enabled(self, enabled: bool):
        """Show/hide OCR overlays based on feature toggle."""
        self._enabled = enabled
        logger.info(f"[vr_ocr] OCR overlays {'enabled' if enabled else 'disabled'}")

        if not self._is_initialized:
            return

        try:
            import openvr
            overlay = openvr.IVROverlay()

            if enabled:
                if self._button_handle:
                    overlay.showOverlay(self._button_handle)
            else:
                # Hide everything
                for handle in [self._button_handle, self._region_handle,
                                self._camera_handle, self._translation_handle,
                                self._close_handle] + self._corner_handles:
                    if handle:
                        overlay.hideOverlay(handle)
                self._region_visible = False
                self._selection_mode = False

        except Exception as e:
            logger.error(f"[vr_ocr] Failed to set enabled: {e}")

    def toggle_region(self):
        """Toggle capture region visibility (cyan button click)."""
        self._region_visible = not self._region_visible
        logger.info(f"[vr_ocr] Region {'shown' if self._region_visible else 'hidden'}")

        if not self._is_initialized:
            return

        try:
            import openvr
            overlay = openvr.IVROverlay()

            if self._region_visible:
                if self._region_handle:
                    overlay.showOverlay(self._region_handle)
                if self._camera_handle:
                    overlay.showOverlay(self._camera_handle)
                if self._translation_handle:
                    overlay.showOverlay(self._translation_handle)
            else:
                for handle in [self._region_handle, self._camera_handle,
                                self._translation_handle, self._close_handle] + self._corner_handles:
                    if handle:
                        overlay.hideOverlay(handle)
                self._selection_mode = False

        except Exception as e:
            logger.error(f"[vr_ocr] Failed to toggle region: {e}")

        if self.on_toggle_region:
            self.on_toggle_region(self._region_visible)

    def toggle_selection_mode(self):
        """Toggle selection mode (corner handles for resizing)."""
        self._selection_mode = not self._selection_mode
        logger.info(f"[vr_ocr] Selection mode {'on' if self._selection_mode else 'off'}")

        if not self._is_initialized:
            return

        try:
            import openvr
            overlay = openvr.IVROverlay()

            if self._selection_mode:
                self._update_corner_positions()
                if self._close_handle:
                    overlay.showOverlay(self._close_handle)
                # Pulse animation: brief alpha changes
                self._pulse_region_border()
            else:
                for handle in self._corner_handles:
                    if handle:
                        overlay.hideOverlay(handle)
                if self._close_handle:
                    overlay.hideOverlay(self._close_handle)

        except Exception as e:
            logger.error(f"[vr_ocr] Failed to toggle selection: {e}")

    def _pulse_region_border(self):
        """Brief visual pulse on the region border (3 flashes over 1.5s)."""
        if not self._region_handle:
            return

        def _do_pulse():
            try:
                import openvr
                overlay = openvr.IVROverlay()
                for _ in range(3):
                    overlay.setOverlayAlpha(self._region_handle, 0.9)
                    time.sleep(0.15)
                    overlay.setOverlayAlpha(self._region_handle, 0.3)
                    time.sleep(0.35)
                overlay.setOverlayAlpha(self._region_handle, 0.5)
            except Exception:
                pass

        threading.Thread(target=_do_pulse, daemon=True).start()

    def update_translation_texture(self, rgba_array: np.ndarray):
        """Apply OCR translation results as overlay texture.

        Args:
            rgba_array: RGBA numpy array from render_translation_texture()
        """
        if self._translation_handle:
            self._update_texture(self._translation_handle, rgba_array)
            logger.debug(f"[vr_ocr] Translation texture updated: {rgba_array.shape}")

    def update_settings(self, settings: dict):
        """Update OCR overlay settings from frontend."""
        logger.debug(f"[vr_ocr] update_settings: {list(settings.keys())}")

        if 'ocrButton' in settings:
            btn = settings['ocrButton']
            self._button_pos.update(btn)

        if 'captureRegion' in settings:
            reg = settings['captureRegion']
            self._region_pos.update(reg)

        if 'controllerBindingEnabled' in settings:
            self._controller_enabled = settings['controllerBindingEnabled']

        if 'captureBinding' in settings:
            self._capture_binding = settings['captureBinding']

        if 'toggleBinding' in settings:
            self._toggle_binding = settings['toggleBinding']

        if self._is_initialized:
            self._configure_overlays()

    def update_button_position(self, pos: dict):
        """Update just the OCR button position."""
        self._button_pos.update(pos)
        if self._is_initialized and self._button_handle:
            self._update_position(
                self._button_handle,
                self._button_pos['distance'],
                self._button_pos['y'],
                self._button_pos['x'],
                self._button_pos.get('tracking', 'none')
            )

    def update_region_position(self, pos: dict):
        """Update capture region position and re-configure camera/corners."""
        self._region_pos.update(pos)
        if self._is_initialized:
            self._configure_overlays()
            if self.on_region_changed:
                self.on_region_changed(self._region_pos)

    # ── Overlay Event Polling ─────────────────────────────────────────

    def start_event_polling(self):
        """Start polling for VR overlay events (button clicks) and controller bindings."""
        if self._poll_thread is not None:
            return

        self._should_poll = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()
        logger.debug("[vr_ocr] Event polling started")

    def stop_event_polling(self):
        """Stop the event polling thread."""
        self._should_poll = False
        if self._poll_thread:
            self._poll_thread.join(timeout=2)
            self._poll_thread = None
        logger.debug("[vr_ocr] Event polling stopped")

    def _poll_loop(self):
        """Background thread: poll overlay events + controller bindings at 30Hz."""
        while self._should_poll:
            try:
                if self._is_initialized and self._enabled:
                    self._poll_overlay_events()
                    if self._controller_enabled:
                        self._poll_controller_bindings()
                time.sleep(1.0 / 30)  # 30Hz
            except Exception as e:
                logger.error(f"[vr_ocr] Poll loop error: {e}")
                time.sleep(0.5)

    def _poll_overlay_events(self):
        """Check for VR overlay mouse/click events."""
        if not self._openvr:
            return

        try:
            import openvr
            overlay = openvr.IVROverlay()

            # Poll events for each interactive overlay
            event = openvr.VREvent_t()
            event_size = openvr.sizeof(openvr.VREvent_t)

            # Cyan button: toggle region
            if self._button_handle:
                while overlay.pollNextOverlayEvent(self._button_handle, event, event_size):
                    if event.eventType == openvr.VREvent_MouseButtonUp:
                        logger.info("[vr_ocr] Cyan button clicked → toggle region")
                        self.toggle_region()

            # Camera button: trigger capture
            if self._camera_handle and self._region_visible:
                while overlay.pollNextOverlayEvent(self._camera_handle, event, event_size):
                    if event.eventType == openvr.VREvent_MouseButtonUp:
                        logger.info("[vr_ocr] Camera button clicked → trigger capture")
                        if self.on_capture_triggered:
                            self.on_capture_triggered()

            # Close button: exit selection mode
            if self._close_handle and self._selection_mode:
                while overlay.pollNextOverlayEvent(self._close_handle, event, event_size):
                    if event.eventType == openvr.VREvent_MouseButtonUp:
                        logger.info("[vr_ocr] Close button clicked → exit selection")
                        self.toggle_selection_mode()

        except Exception as e:
            logger.error(f"[vr_ocr] Event poll error: {e}")

    def _poll_controller_bindings(self):
        """Check controller button combos for capture/toggle bindings."""
        if not self._openvr or not BUTTON_MAP:
            return

        try:
            import openvr
            system = openvr.VRSystem()

            # Check capture binding (rising-edge: fire on release)
            capture_pressed = self._check_combo(system, self._capture_binding)
            if self._capture_combo_held and not capture_pressed:
                # Released → trigger capture
                logger.info("[vr_ocr] Capture binding released → trigger capture")
                if self.on_capture_triggered:
                    self.on_capture_triggered()
            self._capture_combo_held = capture_pressed

            # Check toggle binding (rising-edge: fire on release)
            toggle_pressed = self._check_combo(system, self._toggle_binding)
            if self._toggle_combo_held and not toggle_pressed:
                logger.info("[vr_ocr] Toggle binding released → toggle region")
                self.toggle_region()
            self._toggle_combo_held = toggle_pressed

        except Exception as e:
            logger.error(f"[vr_ocr] Controller poll error: {e}")

    def _check_combo(self, system, binding: List[str]) -> bool:
        """Check if ALL buttons in a binding are currently pressed."""
        if not binding:
            return False

        for btn_str in binding:
            # Parse "left_grip" → hand='left', button='grip'
            parts = btn_str.split('_', 1)
            if len(parts) != 2:
                return False
            hand, button = parts

            if button not in BUTTON_MAP:
                return False

            try:
                import openvr
                if hand == 'left':
                    role = openvr.TrackedControllerRole_LeftHand
                elif hand == 'right':
                    role = openvr.TrackedControllerRole_RightHand
                else:
                    return False

                device_idx = system.getTrackedDeviceIndexForControllerRole(role)
                if device_idx == openvr.k_unTrackedDeviceIndexInvalid:
                    return False

                result, state = system.getControllerState(device_idx)
                if not result:
                    return False

                if not (state.ulButtonPressed & BUTTON_MAP[button]):
                    return False

            except Exception:
                return False

        return True

    # ── VR Position → Screen Pixel Mapping ────────────────────────────

    def get_crop_region_pixels(self) -> Optional[Dict[str, float]]:
        """Convert VR region position to screen pixel fractions (0-1).

        Uses FOV projection math to map VR meters to screen percentages.
        """
        if not self._openvr:
            return None

        try:
            import openvr
            system = openvr.VRSystem()

            # Get HMD FOV (left eye is representative)
            left, right, top, bottom = system.getProjectionRaw(openvr.Eye_Left)

            fov_h = abs(right - left)
            fov_v = abs(top - bottom)

            r = self._region_pos
            dist = r.get('distance', 1.5)
            if dist <= 0:
                dist = 1.5

            # Convert VR position to angular position
            h_angle = math.atan2(r.get('x', 0), dist)
            v_angle = math.atan2(r.get('y', 0), dist)
            w_angle = math.atan2(r.get('width', 0.5), dist)
            h_angle_h = math.atan2(r.get('height', 0.15), dist)

            # Map to screen percentages
            cx = 0.5 + (h_angle / fov_h)
            cy = 0.5 - (v_angle / fov_v)
            cw = w_angle / fov_h
            ch = h_angle_h / fov_v

            # Convert center+size to top-left+size
            x = cx - cw / 2
            y = cy - ch / 2

            return {'x': max(0, min(1, x)), 'y': max(0, min(1, y)),
                    'w': max(0.01, min(1, cw)), 'h': max(0.01, min(1, ch))}

        except Exception as e:
            logger.warning(f"[vr_ocr] FOV projection failed: {e}")
            return None

    # ── Properties ────────────────────────────────────────────────────

    @property
    def is_initialized(self) -> bool:
        return self._is_initialized

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def region_visible(self) -> bool:
        return self._region_visible

    @property
    def region_position(self) -> dict:
        return dict(self._region_pos)

    @property
    def button_position(self) -> dict:
        return dict(self._button_pos)

    # ── Shutdown ──────────────────────────────────────────────────────

    def shutdown(self):
        """Destroy all OCR overlays and stop polling."""
        logger.info("[vr_ocr] Shutting down OCR overlays")
        self.stop_event_polling()

        try:
            import openvr
            overlay = openvr.IVROverlay()

            all_handles = [self._button_handle, self._region_handle,
                           self._camera_handle, self._translation_handle,
                           self._close_handle] + self._corner_handles

            for handle in all_handles:
                if handle:
                    try:
                        overlay.destroyOverlay(handle)
                    except Exception:
                        pass

        except Exception:
            pass

        self._button_handle = None
        self._region_handle = None
        self._camera_handle = None
        self._translation_handle = None
        self._corner_handles = [None, None, None, None]
        self._close_handle = None
        self._is_initialized = False


# Singleton
_vr_ocr_overlay: Optional[VROCROverlay] = None


def get_vr_ocr_overlay() -> VROCROverlay:
    """Get the singleton VR OCR overlay instance."""
    global _vr_ocr_overlay
    if _vr_ocr_overlay is None:
        _vr_ocr_overlay = VROCROverlay()
    return _vr_ocr_overlay
