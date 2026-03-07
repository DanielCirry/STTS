"""
VR Overlay for SteamVR
Displays text overlay in VR using OpenVR — supports dual overlays,
message log, fade effects, per-axis rotation, tracking targets, and CJK fonts.
"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

import numpy as np

# PIL is optional - only needed if VR overlay is actually used
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None
    ImageDraw = None
    ImageFont = None

logger = logging.getLogger('stts.vr_overlay')

# Default overlay settings
DEFAULT_WIDTH = 800
DEFAULT_HEIGHT = 200
DEFAULT_LOG_WIDTH = 800
DEFAULT_LOG_HEIGHT = 600
DEFAULT_FONT_SIZE = 32
DEFAULT_FONT_COLOR = (255, 255, 255, 255)  # White
DEFAULT_BG_COLOR = (0, 0, 0, 180)  # Semi-transparent black
DEFAULT_LOG_MAX = 20
DEFAULT_FADE_IN = 0.3
DEFAULT_FADE_OUT = 0.5


@dataclass
class OverlaySettings:
    """Settings for VR overlay."""
    enabled: bool = False

    # Notification panel
    notification_enabled: bool = True
    notification_tracking: str = 'none'   # 'none', 'left_hand', 'right_hand'
    notification_x: float = 0.0           # horizontal offset (meters)
    notification_y: float = -0.3          # vertical offset (meters)
    notification_width: float = 0.4       # meters
    notification_height: float = 0.15     # meters
    notification_distance: float = 1.5    # depth (meters)
    notification_font_size: int = DEFAULT_FONT_SIZE
    notification_font_color: Tuple[int, int, int, int] = DEFAULT_FONT_COLOR
    notification_bg_color: Tuple[int, int, int, int] = DEFAULT_BG_COLOR
    notification_bg_opacity: float = 0.7
    notification_fade_in: float = DEFAULT_FADE_IN
    notification_fade_out: float = DEFAULT_FADE_OUT
    notification_auto_hide: float = 5.0
    notification_adaptive_height: bool = True

    # Message log panel
    message_log_enabled: bool = False
    message_log_tracking: str = 'none'    # 'none', 'left_hand', 'right_hand'
    message_log_x: float = 0.0
    message_log_y: float = 0.0
    message_log_width: float = 0.5
    message_log_height: float = 0.4
    message_log_distance: float = 1.8
    message_log_font_size: int = 20
    message_log_font_color: Tuple[int, int, int, int] = DEFAULT_FONT_COLOR
    message_log_bg_color: Tuple[int, int, int, int] = DEFAULT_BG_COLOR
    message_log_bg_opacity: float = 0.6
    message_log_max: int = DEFAULT_LOG_MAX


@dataclass
class OverlayMessage:
    """A message to display in the overlay."""
    text: str
    message_type: str  # 'user', 'speaker', 'ai', 'system'
    timestamp: float
    duration: float = 5.0


# Type colors for message log
MESSAGE_TYPE_COLORS = {
    'user': (100, 200, 255, 255),      # Light blue
    'speaker': (200, 255, 100, 255),   # Light green
    'ai': (255, 180, 100, 255),        # Orange
    'system': (180, 180, 180, 255),    # Gray
}

MESSAGE_TYPE_LABELS = {
    'user': 'You',
    'speaker': 'Other',
    'ai': 'AI',
    'system': 'System',
}


class VROverlay:
    """SteamVR overlay for displaying text in VR."""

    def __init__(self):
        self._openvr = None
        self._overlay_handle = None       # Notification overlay
        self._log_overlay_handle = None   # Message log overlay
        self._is_initialized = False
        self._settings = OverlaySettings()

        # Message queue (for notification overlay)
        self._messages: List[OverlayMessage] = []
        self._current_message: Optional[OverlayMessage] = None
        self._message_lock = threading.Lock()

        # Message history (for log overlay)
        self._message_history: List[OverlayMessage] = []
        self._history_lock = threading.Lock()
        self._log_dirty = False

        # Rendering
        self._texture_width = DEFAULT_WIDTH
        self._texture_height = DEFAULT_HEIGHT
        self._log_texture_width = DEFAULT_LOG_WIDTH
        self._log_texture_height = DEFAULT_LOG_HEIGHT
        self._font = None
        self._cjk_font = None  # Separate CJK-capable font
        self._log_font = None
        self._log_cjk_font = None

        # Fade state
        self._fade_alpha = 0.0  # Current alpha for notification
        self._fade_target = 0.0
        self._fade_start_time = 0.0
        self._fade_start_alpha = 0.0
        self._fade_duration = 0.0

        # Update thread
        self._update_thread: Optional[threading.Thread] = None
        self._should_update = False

        # Callbacks
        self.on_error: Optional[Callable[[str], None]] = None

    def initialize(self) -> bool:
        """Initialize OpenVR and create overlay(s)."""
        if self._is_initialized:
            return True

        try:
            import openvr

            if not openvr.isRuntimeInstalled():
                logger.warning("SteamVR runtime not installed")
                return False

            if not openvr.isHmdPresent():
                logger.debug("No VR headset detected")
                return False

            self._openvr = openvr.init(openvr.VRApplication_Overlay)

            if self._openvr is None:
                logger.error("Failed to initialize OpenVR")
                return False

            overlay = openvr.IVROverlay()

            # Create notification overlay
            error, self._overlay_handle = overlay.createOverlay(
                b"stts.notification.overlay",
                b"STTS Notification"
            )
            if error != openvr.VROverlayError_None:
                logger.error(f"Failed to create notification overlay: {error}")
                openvr.shutdown()
                return False

            # Create message log overlay
            error, self._log_overlay_handle = overlay.createOverlay(
                b"stts.log.overlay",
                b"STTS Message Log"
            )
            if error != openvr.VROverlayError_None:
                logger.warning(f"Failed to create log overlay: {error}")
                self._log_overlay_handle = None

            # Configure overlays
            self._load_font()
            self._configure_overlay()

            self._is_initialized = True
            logger.debug("VR overlay initialized (notification + log)")

            self._start_update_thread()
            return True

        except ImportError:
            logger.warning("openvr not installed")
            return False
        except Exception as e:
            logger.error(f"Error initializing VR overlay: {e}")
            return False

    def _configure_overlay(self):
        """Configure overlay properties."""
        if not self._openvr:
            return

        try:
            import openvr
            overlay = openvr.IVROverlay()

            # --- Notification overlay ---
            if self._overlay_handle:
                overlay.setOverlayWidthInMeters(self._overlay_handle, self._settings.notification_width)
                overlay.setOverlayAlpha(self._overlay_handle, 0.0)  # Start hidden (fade in)

                self._update_overlay_position(
                    self._overlay_handle,
                    self._settings.notification_distance,
                    self._settings.notification_y,
                    self._settings.notification_x,
                    self._settings.notification_tracking,
                )

                if self._settings.enabled and self._settings.notification_enabled:
                    overlay.showOverlay(self._overlay_handle)
                else:
                    overlay.hideOverlay(self._overlay_handle)

            # --- Log overlay ---
            if self._log_overlay_handle:
                overlay.setOverlayWidthInMeters(self._log_overlay_handle, self._settings.message_log_width)
                overlay.setOverlayAlpha(self._log_overlay_handle, self._settings.message_log_bg_opacity)

                # If both overlays on the same hand, stack notification above log
                log_y = self._settings.message_log_y
                if (self._settings.notification_enabled and self._settings.message_log_enabled
                        and self._settings.notification_tracking != 'none'
                        and self._settings.notification_tracking == self._settings.message_log_tracking):
                    # Offset log below notification
                    log_y = self._settings.notification_y - self._settings.notification_height - 0.02

                self._update_overlay_position(
                    self._log_overlay_handle,
                    self._settings.message_log_distance,
                    log_y,
                    self._settings.message_log_x,
                    self._settings.message_log_tracking,
                )

                if self._settings.enabled and self._settings.message_log_enabled:
                    overlay.showOverlay(self._log_overlay_handle)
                else:
                    overlay.hideOverlay(self._log_overlay_handle)

        except Exception as e:
            logger.error(f"Error configuring overlay: {e}")

    def _get_tracking_device_index(self, tracking: str = 'none'):
        """Get the OpenVR device index for a tracking target."""
        import openvr

        if tracking == 'left_hand':
            system = openvr.VRSystem()
            return system.getTrackedDeviceIndexForControllerRole(
                openvr.TrackedControllerRole_LeftHand
            )
        elif tracking == 'right_hand':
            system = openvr.VRSystem()
            return system.getTrackedDeviceIndexForControllerRole(
                openvr.TrackedControllerRole_RightHand
            )
        else:
            return openvr.k_unTrackedDeviceIndex_Hmd

    def _update_overlay_position(self, handle, distance: float,
                                  v_offset: float, h_offset: float,
                                  tracking: str = 'none'):
        """Update overlay position relative to HMD or hand controller."""
        if not self._openvr or not handle:
            return

        try:
            import openvr
            overlay = openvr.IVROverlay()

            transform = openvr.HmdMatrix34_t()

            # Identity rotation
            transform.m[0][0] = 1.0
            transform.m[1][1] = 1.0
            transform.m[2][2] = 1.0

            # Position
            transform.m[0][3] = h_offset
            transform.m[1][3] = v_offset
            transform.m[2][3] = -distance  # Negative Z is forward

            device_index = self._get_tracking_device_index(tracking)
            overlay.setOverlayTransformTrackedDeviceRelative(
                handle,
                device_index,
                transform
            )

        except Exception as e:
            logger.error(f"Error updating overlay position: {e}")

    def _load_font(self):
        """Load fonts for text rendering, including CJK-capable fonts."""
        if not PIL_AVAILABLE:
            return

        notif_size = self._settings.notification_font_size
        log_size = self._settings.message_log_font_size

        # Primary font (Latin)
        latin_font_paths = [
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]

        # CJK font (for Japanese, Chinese, Korean characters)
        cjk_font_paths = [
            "C:/Windows/Fonts/YuGothM.ttc",    # Yu Gothic Medium
            "C:/Windows/Fonts/meiryo.ttc",      # Meiryo
            "C:/Windows/Fonts/msgothic.ttc",    # MS Gothic
            "C:/Windows/Fonts/msyh.ttc",        # Microsoft YaHei (Chinese)
            "C:/Windows/Fonts/malgun.ttf",       # Malgun Gothic (Korean)
            "C:/Windows/Fonts/NotoSansCJK-Regular.ttc",  # Noto Sans CJK if installed
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        ]

        def _load(size):
            font = None
            for path in latin_font_paths:
                try:
                    font = ImageFont.truetype(path, size)
                    break
                except:
                    continue
            if font is None:
                font = ImageFont.load_default()

            cjk = None
            for path in cjk_font_paths:
                try:
                    cjk = ImageFont.truetype(path, size)
                    break
                except:
                    continue
            if cjk is None:
                cjk = font
            return font, cjk

        self._font, self._cjk_font = _load(notif_size)
        self._log_font, self._log_cjk_font = _load(log_size)

    def _has_cjk(self, text: str) -> bool:
        """Check if text contains CJK characters."""
        for ch in text:
            cp = ord(ch)
            if (0x4E00 <= cp <= 0x9FFF or    # CJK Unified
                0x3040 <= cp <= 0x309F or     # Hiragana
                0x30A0 <= cp <= 0x30FF or     # Katakana
                0xAC00 <= cp <= 0xD7AF or     # Korean Hangul
                0x3400 <= cp <= 0x4DBF or     # CJK Extension A
                0xFF00 <= cp <= 0xFFEF):      # Fullwidth forms
                return True
        return False

    def _get_font_for_text(self, text: str, for_log: bool = False):
        """Return the appropriate font for the text content."""
        if for_log:
            if self._has_cjk(text):
                return self._log_cjk_font or self._log_font or self._font
            return self._log_font or self._font
        if self._has_cjk(text):
            return self._cjk_font or self._font
        return self._font

    def _render_text(self, text: str, width: int = None, height: int = None,
                     adaptive: bool = False) -> Optional[np.ndarray]:
        """Render text to a texture."""
        if not PIL_AVAILABLE:
            return None

        try:
            w = width or self._texture_width
            h = height or self._texture_height
            font = self._get_font_for_text(text)

            # For adaptive height, measure first
            if adaptive and self._settings.notification_adaptive_height:
                temp_img = Image.new('RGBA', (w, 2000), (0, 0, 0, 0))
                temp_draw = ImageDraw.Draw(temp_img)
                wrapped = self._wrap_text(text, temp_draw, w, font)
                bbox = temp_draw.multiline_textbbox((0, 0), wrapped, font=font)
                text_h = bbox[3] - bbox[1]
                h = max(h, text_h + 30)  # padding

            img = Image.new('RGBA', (w, h), self._settings.notification_bg_color)
            draw = ImageDraw.Draw(img)

            wrapped = self._wrap_text(text, draw, w, font)

            bbox = draw.multiline_textbbox((0, 0), wrapped, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            x = (w - text_width) // 2
            y = (h - text_height) // 2

            draw.multiline_text(
                (x, y), wrapped, font=font,
                fill=self._settings.notification_font_color, align='center'
            )

            return np.array(img)

        except Exception as e:
            logger.error(f"Error rendering text: {e}")
            return None

    def _render_message_log(self) -> Optional[np.ndarray]:
        """Render the message log overlay texture."""
        if not PIL_AVAILABLE:
            return None

        try:
            w = self._log_texture_width
            h = self._log_texture_height

            img = Image.new('RGBA', (w, h), self._settings.message_log_bg_color)
            draw = ImageDraw.Draw(img)

            with self._history_lock:
                messages = list(self._message_history)

            if not messages:
                # Empty log
                font = self._log_font or self._font
                draw.text((10, 10), "No messages yet", font=font,
                          fill=(128, 128, 128, 255))
                return np.array(img)

            padding = 10
            line_spacing = 6
            y_pos = padding
            max_width = w - (padding * 2)

            # Render messages bottom-up (newest at bottom)
            rendered_lines = []
            for msg in messages:
                label = MESSAGE_TYPE_LABELS.get(msg.message_type, '???')
                color = MESSAGE_TYPE_COLORS.get(msg.message_type, (255, 255, 255, 255))
                font = self._get_font_for_text(msg.text, for_log=True)
                prefix = f"[{label}] "
                full_text = prefix + msg.text
                wrapped = self._wrap_text(full_text, draw, max_width, font)
                rendered_lines.append((wrapped, color, font))

            # Calculate total height needed
            total_h = 0
            line_heights = []
            for wrapped, color, font in rendered_lines:
                bbox = draw.multiline_textbbox((0, 0), wrapped, font=font)
                lh = bbox[3] - bbox[1] + line_spacing
                line_heights.append(lh)
                total_h += lh

            # If content exceeds height, start from bottom and skip old messages
            if total_h > h - (padding * 2):
                y_pos = h - padding
                for i in range(len(rendered_lines) - 1, -1, -1):
                    wrapped, color, font = rendered_lines[i]
                    lh = line_heights[i]
                    y_pos -= lh
                    if y_pos < padding:
                        break
                    draw.multiline_text((padding, y_pos), wrapped,
                                        font=font, fill=color)
            else:
                y_pos = padding
                for i, (wrapped, color, font) in enumerate(rendered_lines):
                    draw.multiline_text((padding, y_pos), wrapped,
                                        font=font, fill=color)
                    y_pos += line_heights[i]

            return np.array(img)

        except Exception as e:
            logger.error(f"Error rendering message log: {e}")
            return None

    def _wrap_text(self, text: str, draw, max_width: int = None,
                   font=None) -> str:
        """Wrap text to fit overlay width."""
        if font is None:
            font = self._font
        if max_width is None:
            max_width = self._texture_width - 20

        words = text.split()
        lines = []
        current_line = []

        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)
            width = bbox[2] - bbox[0]

            if width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]

        if current_line:
            lines.append(' '.join(current_line))

        return '\n'.join(lines)

    def _update_texture(self, handle, rgba_array: np.ndarray):
        """Update overlay texture."""
        if not self._openvr or not handle:
            return

        try:
            import openvr
            overlay = openvr.IVROverlay()

            # OpenVR expects BGRA, PIL gives us RGBA
            bgra_array = rgba_array.copy()
            bgra_array[:, :, [0, 2]] = bgra_array[:, :, [2, 0]]

            h, w = bgra_array.shape[:2]
            overlay.setOverlayRaw(
                handle,
                bgra_array.ctypes.data_as(openvr.POINTER(openvr.c_char)),
                w, h, 4
            )

        except Exception as e:
            logger.error(f"Error updating texture: {e}")

    def _start_update_thread(self):
        """Start the overlay update thread."""
        if self._update_thread is not None:
            return

        self._should_update = True
        self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self._update_thread.start()

    def _update_loop(self):
        """Background thread for updating overlay."""
        logger.debug("Overlay update loop started")

        while self._should_update:
            try:
                now = time.time()

                # --- Fade animation ---
                self._update_fade(now)

                # --- Notification overlay: message expiration ---
                with self._message_lock:
                    if self._current_message:
                        elapsed = now - self._current_message.timestamp
                        remaining = self._current_message.duration - elapsed

                        # Start fade-out near end of duration
                        if remaining <= self._settings.notification_fade_out and self._fade_target > 0:
                            self._start_fade(0.0, self._settings.notification_fade_out)

                        if elapsed >= self._current_message.duration:
                            self._current_message = None

                    # Get next message if none active
                    if not self._current_message and self._messages:
                        self._current_message = self._messages.pop(0)
                        self._display_notification(self._current_message)

                # --- Log overlay: re-render if dirty ---
                if self._log_dirty and self._log_overlay_handle:
                    self._log_dirty = False
                    self._render_and_update_log()

                time.sleep(0.05)  # 20Hz

            except Exception as e:
                logger.error(f"Error in update loop: {e}")

        logger.debug("Overlay update loop stopped")

    def _start_fade(self, target_alpha: float, duration: float):
        """Start a fade animation."""
        if duration <= 0:
            self._fade_alpha = target_alpha
            self._fade_target = target_alpha
            self._apply_notification_alpha(target_alpha)
            return

        self._fade_target = target_alpha
        self._fade_start_alpha = self._fade_alpha
        self._fade_start_time = time.time()
        self._fade_duration = duration

    def _update_fade(self, now: float):
        """Update fade animation state."""
        if self._fade_alpha == self._fade_target:
            return

        if self._fade_duration <= 0:
            self._fade_alpha = self._fade_target
        else:
            elapsed = now - self._fade_start_time
            t = min(1.0, elapsed / self._fade_duration)
            # Ease in-out
            t = t * t * (3.0 - 2.0 * t)
            self._fade_alpha = self._fade_start_alpha + (self._fade_target - self._fade_start_alpha) * t

            if t >= 1.0:
                self._fade_alpha = self._fade_target

        self._apply_notification_alpha(self._fade_alpha)

    def _apply_notification_alpha(self, alpha: float):
        """Set the notification overlay alpha."""
        if not self._openvr or not self._overlay_handle:
            return
        try:
            import openvr
            overlay = openvr.IVROverlay()
            overlay.setOverlayAlpha(self._overlay_handle, max(0.0, min(1.0, alpha)))
        except Exception:
            pass

    def _display_notification(self, message: OverlayMessage):
        """Display a message on the notification overlay."""
        if not self._is_initialized or not self._settings.notification_enabled:
            return

        if not self._should_show_type(message.message_type):
            return

        texture = self._render_text(message.text, adaptive=True)
        if texture is not None:
            self._update_texture(self._overlay_handle, texture)
            self._show_overlay(self._overlay_handle)
            # Start fade-in
            self._start_fade(1.0, self._settings.notification_fade_in)

    def _render_and_update_log(self):
        """Render and update the log overlay texture."""
        if not self._settings.message_log_enabled or not self._log_overlay_handle:
            return

        texture = self._render_message_log()
        if texture is not None:
            self._update_texture(self._log_overlay_handle, texture)

    def _should_show_type(self, message_type: str) -> bool:
        """Check if a message type should be shown.

        Note: The engine already filters based on overlay settings toggles
        (showOriginalText, showTranslatedText, showAIResponses, showListenText).
        This is a secondary filter for the overlay's own settings.
        """
        return True  # Engine handles filtering

    def _show_overlay(self, handle):
        """Show an overlay."""
        if not self._openvr or not handle:
            return
        try:
            import openvr
            overlay = openvr.IVROverlay()
            overlay.showOverlay(handle)
        except Exception as e:
            logger.error(f"Error showing overlay: {e}")

    def _hide_overlay(self, handle):
        """Hide an overlay."""
        if not self._openvr or not handle:
            return
        try:
            import openvr
            overlay = openvr.IVROverlay()
            overlay.hideOverlay(handle)
        except Exception as e:
            logger.error(f"Error hiding overlay: {e}")

    def show_text(self, text: str, message_type: str = 'system',
                  duration: Optional[float] = None):
        """Show text on the overlay."""
        if not self._settings.enabled:
            return

        if not self._should_show_type(message_type):
            return

        if duration is None:
            duration = self._settings.notification_auto_hide

        message = OverlayMessage(
            text=text,
            message_type=message_type,
            timestamp=time.time(),
            duration=duration
        )

        # Add to notification queue
        if self._settings.notification_enabled:
            with self._message_lock:
                self._messages.append(message)

        # Add to message history (for log overlay)
        if self._settings.message_log_enabled:
            with self._history_lock:
                self._message_history.append(message)
                # Trim to max
                max_msgs = self._settings.message_log_max
                if len(self._message_history) > max_msgs:
                    self._message_history = self._message_history[-max_msgs:]
            self._log_dirty = True

    def update_settings(self, settings: dict):
        """Update overlay settings."""
        # Map camelCase keys from frontend to snake_case
        key_map = {
            'notificationEnabled': 'notification_enabled',
            'notificationTracking': 'notification_tracking',
            'notificationX': 'notification_x',
            'notificationY': 'notification_y',
            'notificationWidth': 'notification_width',
            'notificationHeight': 'notification_height',
            'notificationDistance': 'notification_distance',
            'notificationFontSize': 'notification_font_size',
            'notificationFontColor': 'notification_font_color',
            'notificationBgColor': 'notification_bg_color',
            'notificationBgOpacity': 'notification_bg_opacity',
            'notificationFadeIn': 'notification_fade_in',
            'notificationFadeOut': 'notification_fade_out',
            'notificationAutoHide': 'notification_auto_hide',
            'notificationAdaptiveHeight': 'notification_adaptive_height',
            'messageLogEnabled': 'message_log_enabled',
            'messageLogTracking': 'message_log_tracking',
            'messageLogX': 'message_log_x',
            'messageLogY': 'message_log_y',
            'messageLogWidth': 'message_log_width',
            'messageLogHeight': 'message_log_height',
            'messageLogDistance': 'message_log_distance',
            'messageLogFontSize': 'message_log_font_size',
            'messageLogFontColor': 'message_log_font_color',
            'messageLogBgColor': 'message_log_bg_color',
            'messageLogBgOpacity': 'message_log_bg_opacity',
            'messageLogMax': 'message_log_max',
        }

        for key, value in settings.items():
            attr_name = key_map.get(key, key)

            # Handle special conversions for color fields
            if attr_name in ('notification_font_color', 'message_log_font_color') and isinstance(value, str):
                value = self._hex_to_rgba(value)
            elif attr_name == 'notification_bg_color' and isinstance(value, str):
                rgb = self._hex_to_rgb(value)
                value = (*rgb, int(self._settings.notification_bg_opacity * 255))
            elif attr_name == 'notification_bg_opacity' and isinstance(value, (int, float)):
                r, g, b, _ = self._settings.notification_bg_color
                self._settings.notification_bg_color = (r, g, b, int(value * 255))
                setattr(self._settings, attr_name, value)
                continue
            elif attr_name == 'message_log_bg_color' and isinstance(value, str):
                rgb = self._hex_to_rgb(value)
                value = (*rgb, int(self._settings.message_log_bg_opacity * 255))
            elif attr_name == 'message_log_bg_opacity' and isinstance(value, (int, float)):
                r, g, b, _ = self._settings.message_log_bg_color
                self._settings.message_log_bg_color = (r, g, b, int(value * 255))
                setattr(self._settings, attr_name, value)
                continue

            if hasattr(self._settings, attr_name):
                setattr(self._settings, attr_name, value)

        # Apply changes
        if 'notificationFontSize' in settings or 'messageLogFontSize' in settings:
            self._load_font()

        if self._is_initialized:
            self._configure_overlay()

        logger.debug(f"Overlay settings updated: {list(settings.keys())}")

    def _hex_to_rgba(self, hex_color: str) -> Tuple[int, int, int, int]:
        """Convert hex color string to RGBA tuple."""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 6:
            r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
            return (r, g, b, 255)
        elif len(hex_color) == 8:
            r, g, b, a = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16), int(hex_color[6:8], 16)
            return (r, g, b, a)
        return DEFAULT_FONT_COLOR

    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color string to RGB tuple."""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) >= 6:
            return (int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))
        return (0, 0, 0)

    @property
    def is_available(self) -> bool:
        if not PIL_AVAILABLE:
            return False
        try:
            import openvr
            return openvr.isRuntimeInstalled() and openvr.isHmdPresent()
        except ImportError:
            return False
        except:
            return False

    @property
    def is_runtime_installed(self) -> bool:
        try:
            import openvr
            return openvr.isRuntimeInstalled()
        except ImportError:
            return False
        except:
            return False

    @property
    def is_hmd_present(self) -> bool:
        try:
            import openvr
            return openvr.isHmdPresent()
        except ImportError:
            return False
        except:
            return False

    @property
    def is_initialized(self) -> bool:
        return self._is_initialized

    @property
    def settings(self) -> OverlaySettings:
        return self._settings

    def clear(self):
        """Clear the overlay and cancel any pending messages."""
        with self._message_lock:
            self._messages.clear()
            self._current_message = None
        self._fade_alpha = 0.0
        self._fade_target = 0.0
        self._apply_notification_alpha(0.0)
        self._hide_overlay(self._overlay_handle)

    def clear_history(self):
        """Clear the message log history."""
        with self._history_lock:
            self._message_history.clear()
        self._log_dirty = True

    def shutdown(self):
        """Shutdown the overlay."""
        self._should_update = False

        if self._update_thread:
            self._update_thread.join(timeout=2)
            self._update_thread = None

        try:
            import openvr
            overlay_api = openvr.IVROverlay()

            if self._overlay_handle:
                overlay_api.destroyOverlay(self._overlay_handle)
                self._overlay_handle = None

            if self._log_overlay_handle:
                overlay_api.destroyOverlay(self._log_overlay_handle)
                self._log_overlay_handle = None
        except:
            pass

        if self._openvr:
            try:
                import openvr
                openvr.shutdown()
            except:
                pass
            self._openvr = None

        self._is_initialized = False
        logger.debug("VR overlay shut down")


# Singleton instance
_vr_overlay: Optional[VROverlay] = None


def get_vr_overlay() -> VROverlay:
    """Get the singleton VR overlay instance."""
    global _vr_overlay
    if _vr_overlay is None:
        _vr_overlay = VROverlay()
    return _vr_overlay
