"""
VRChat OSC Integration
Sends text to VRChat chatbox via OSC protocol
"""

import asyncio
import logging
import re
import time
from typing import Callable, Optional
from dataclasses import dataclass, field
from pythonosc import udp_client
from pythonosc.osc_message_builder import OscMessageBuilder

logger = logging.getLogger('stts.vrchat_osc')


# Emoji → displayable replacement for VRChat OSC.
# Priority: 1) Unicode symbol  2) ASCII emoticon  3) short text label
EMOJI_TO_TEXT = {
    # Smileys → Unicode symbols where possible, ASCII emoticons otherwise
    '😀': '☺', '😃': '☺', '😄': '☺', '😁': '☺', '😆': '☺',
    '😅': '☺', '🤣': '☺', '😂': '☺', '🙂': '☺', '😊': '☺',
    '😇': '☺', '🥰': '♥', '😍': '♥', '🤩': '★', '😘': '♥',
    '😗': ':*', '😚': ':*', '😙': ':*', '🥲': ":')", '😋': ':P',
    '😛': ':P', '😜': ';P', '🤪': ';P', '😝': 'xP', '🤑': '$_$',
    '🤗': '☺', '🤭': ':x', '🤫': '…', '🤔': '?', '🤐': ':#',
    '🤨': 'o_O', '😐': ':|', '😑': '-_-', '😶': '…', '😏': ';)',
    '😒': '-_-', '🙄': '-_-', '😬': ':S', '🤥': ':Z', '😌': '☺',
    '😔': ':(', '😪': '~_~', '🤤': ':P~', '😴': '~_~',
    '😷': ':(', '🤒': ':(', '🤕': ':(', '🤢': ':X', '🤮': ':X',
    '🥴': 'x_x', '😵': 'x_x', '🤯': ':O!', '🥳': '☆', '🥸': 'B)',
    '😎': 'B)', '🤓': 'B)', '🧐': 'o_O', '😕': ':/', '😟': ':(',
    '🙁': ':(', '😮': ':O', '😯': ':O', '😲': ':O', '😳': 'O_O',
    '🥺': ':(', '🥹': ":')", '😦': 'D:', '😧': 'D:', '😨': 'D:',
    '😰': "D':", '😥': ":'(", '😢': ":'(", '😭': "T_T", '😱': ':O!',
    '😖': '>_<', '😣': '>_<', '😞': ':(', '😓': '^_^',
    '😩': 'DX', '😫': 'DX', '🥱': '~_~', '😤': '>:(', '😡': '>:(',
    '😠': '>:(', '🤬': '>:(', '😈': '>:)', '👿': '>:)',
    '💀': '☠', '☠️': '☠', '💩': '~', '🤡': ':o)', '👻': '~',
    '👽': '◎', '👾': '◎', '🤖': '◎', '🎃': '☺',

    # Gestures
    '👋': '~', '🤚': '‖', '✋': '‖', '👌': '○',
    '✌️': '✌', '🤞': '✌', '🤟': '\\m/', '🤘': '\\m/',
    '🤙': '~', '👈': '←', '👉': '→', '👆': '↑', '👇': '↓',
    '☝️': '↑', '👍': '✓', '👎': '✗', '✊': '●',
    '👊': '●', '👏': '‖', '🙌': '\\o/', '🤝': '‖',
    '🙏': '†', '💪': '●',

    # Hearts & love → Unicode heart ♥
    '❤️': '♥', '🩷': '♥', '🧡': '♥', '💛': '♥', '💚': '♥',
    '💙': '♥', '🩵': '♥', '💜': '♥', '🖤': '♥', '🩶': '♥',
    '🤍': '♥', '🤎': '♥', '💔': '♥', '❤️‍🔥': '♥',
    '❤️‍🩹': '♥', '❣️': '♥', '💕': '♥♥', '💞': '♥♥',
    '💓': '♥', '💗': '♥', '💖': '♥', '💘': '♥', '💝': '♥',

    # Common symbols → Unicode equivalents
    '✨': '✧', '🔥': '※', '💯': '100', '⭐': '★',
    '🌟': '★', '💫': '★', '✅': '✓', '❌': '✗', '❗': '!',
    '❓': '?', '❕': '!', '❔': '?', '‼️': '!!', '⁉️': '?!',
    '💤': '~', '♻️': '♻', '☑️': '✓', '✔️': '✓',
    '❎': '✗', '➕': '+', '➖': '-', '➗': '÷', '✖️': '×',
    '♾️': '∞', '💲': '$',

    # Celebrations → short Unicode
    '🎉': '★', '🎊': '★', '🎈': '○',
    '🎁': '◇', '🏆': '★', '🥇': '①', '🥈': '②', '🥉': '③',

    # Animals → single-char where possible
    '🐶': '◎', '🐱': '◎', '🐭': '◎', '🐹': '◎',
    '🐰': '◎', '🦊': '◎', '🐻': '◎', '🐼': '◎',
    '🐨': '◎', '🐯': '◎', '🦁': '◎', '🐮': '◎',
    '🐷': '◎', '🐸': '◎', '🐵': '◎',

    # Music & media → Unicode music notes
    '🎵': '♪', '🎶': '♫', '🎤': '♪', '🎧': '♪',
    '🎮': '◇', '🎬': '◇',

    # Weather → Unicode symbols
    '☀️': '☀', '🌙': '☽', '🌈': '~',

    # Food → short
    '☕': '○', '🍕': '◇', '🍔': '◇',
    '🍺': '○', '🍻': '○', '🥂': '○', '🍷': '○',

    # Cat faces → kaomoji
    '😺': ':3', '😸': ':3', '😹': 'x3', '😻': '♥:3', '😼': ':3',
    '😽': ':3', '🙀': ':3!', '😿': ":'3", '😾': '>:3',
}

# Build a normalized lookup dict: include both with and without variation selector
# so matching works regardless of whether the text has FE0F or not
_EMOJI_LOOKUP = {}
for _emoji, _repl in EMOJI_TO_TEXT.items():
    _EMOJI_LOOKUP[_emoji] = _repl
    _stripped = _emoji.replace('\uFE0F', '')
    if _stripped != _emoji:
        _EMOJI_LOOKUP[_stripped] = _repl


def _is_emoji_char(ch: str) -> bool:
    """Check if a single character is an emoji pictograph that should be stripped.

    Only strips actual emoji pictographs (colored image glyphs). Keeps all text
    symbols, dingbats, and decorative characters like ✿❁❃★♪ that VRChat can display.
    """
    cp = ord(ch)
    # Variation selectors (invisible modifiers, always strip)
    if 0xFE00 <= cp <= 0xFE0F:
        return True
    # Zero-width joiner (invisible, strip)
    if cp == 0x200D:
        return True
    # Combining enclosing keycap
    if cp == 0x20E3:
        return True
    # Emoji pictograph ranges (the colored image-based ones)
    if 0x1F600 <= cp <= 0x1F64F:  # Emoticons (😀-🙏)
        return True
    if 0x1F300 <= cp <= 0x1F5FF:  # Misc symbols & pictographs (🌀-🗿)
        return True
    if 0x1F680 <= cp <= 0x1F6FF:  # Transport & map (🚀-🛿)
        return True
    if 0x1F900 <= cp <= 0x1F9FF:  # Supplemental symbols (🤀-🧿)
        return True
    if 0x1FA00 <= cp <= 0x1FA6F:  # Chess symbols
        return True
    if 0x1FA70 <= cp <= 0x1FAFF:  # Symbols extended-A (🩰-🫿)
        return True
    if 0x1F1E0 <= cp <= 0x1F1FF:  # Regional indicator flags
        return True
    # Tag characters (used in flag sequences like 🏴󠁧󠁢)
    if 0xE0020 <= cp <= 0xE007F:
        return True
    return False


def convert_emojis_for_osc(text: str) -> str:
    """Convert Unicode emojis to ASCII text equivalents for VRChat OSC.

    VRChat's OSC chatbox can only display text characters, not emoji images.
    This function replaces known emojis with ASCII equivalents (e.g., 😊 -> :))
    and strips any remaining unmapped emoji characters.

    Args:
        text: Input text possibly containing Unicode emojis

    Returns:
        Text with emojis replaced by ASCII equivalents
    """
    if not text:
        return text

    result = text

    # First pass: replace known emojis with their text equivalents
    # Sort by length descending so multi-char emojis (ZWJ sequences) match first
    for emoji, replacement in sorted(_EMOJI_LOOKUP.items(), key=lambda x: len(x[0]), reverse=True):
        if emoji in result:
            result = result.replace(emoji, replacement)

    # Second pass: strip any remaining emoji characters that weren't mapped
    # Process character by character to avoid regex issues with Unicode ranges
    cleaned = []
    for ch in result:
        if not _is_emoji_char(ch):
            cleaned.append(ch)
    result = ''.join(cleaned)

    # Clean up extra spaces from removal
    result = re.sub(r'  +', ' ', result).strip()

    return result

# VRChat OSC addresses
CHATBOX_INPUT = "/chatbox/input"
CHATBOX_TYPING = "/chatbox/typing"

# VRChat chatbox limits
MAX_CHATBOX_LENGTH = 144
CHUNK_DELAY = 1.5  # Delay between message chunks (seconds)


@dataclass
class VRChatMessage:
    """A message to be sent to VRChat chatbox."""
    text: str
    send_immediately: bool = True
    play_sound: bool = True
    priority: int = 0
    timestamp: float = field(default_factory=time.time)


class VRChatOSC:
    """VRChat OSC client for chatbox integration."""

    def __init__(self):
        self._client: Optional[udp_client.SimpleUDPClient] = None
        self._ip: str = "127.0.0.1"
        self._port: int = 9000
        self._connected: bool = False
        self._typing_indicator_enabled: bool = True

        # Message queue for handling long texts
        self._message_queue: asyncio.Queue[VRChatMessage] = asyncio.Queue()
        self._queue_task: Optional[asyncio.Task] = None
        self._is_processing: bool = False

        # Callback for status updates
        self._status_callback: Optional[Callable[[str, dict], None]] = None

    def connect(self, ip: str = "127.0.0.1", port: int = 9000) -> bool:
        """Connect to VRChat OSC server.

        Args:
            ip: VRChat OSC IP address (default localhost)
            port: VRChat OSC port (default 9000)

        Returns:
            True if connection created successfully
        """
        try:
            self._ip = ip
            self._port = port
            self._client = udp_client.SimpleUDPClient(ip, port)
            self._connected = True
            logger.debug(f"VRChat OSC client connected to {ip}:{port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to VRChat OSC: {e}")
            self._connected = False
            return False

    def disconnect(self):
        """Disconnect from VRChat OSC server."""
        self._connected = False
        self._client = None
        if self._queue_task:
            self._queue_task.cancel()
        logger.debug("VRChat OSC client disconnected")

    def set_status_callback(self, callback: Callable[[str, dict], None]):
        """Set callback for status updates.

        Args:
            callback: Function to call with (event_type, data)
        """
        self._status_callback = callback

    def set_typing_indicator(self, enabled: bool):
        """Enable or disable typing indicator.

        Args:
            enabled: Whether to show typing indicator
        """
        self._typing_indicator_enabled = enabled

    def _send_typing(self, is_typing: bool):
        """Send typing indicator to VRChat.

        Args:
            is_typing: Whether user is typing
        """
        if not self._client or not self._connected:
            return

        if not self._typing_indicator_enabled:
            return

        try:
            self._client.send_message(CHATBOX_TYPING, is_typing)
        except Exception as e:
            logger.warning(f"Failed to send typing indicator: {e}")

    def _send_chatbox(self, text: str, send_immediately: bool = True, play_sound: bool = True):
        """Send text to VRChat chatbox.

        Args:
            text: Text to display (max 144 chars)
            send_immediately: If True, display immediately; if False, wait for Enter
            play_sound: Whether to play notification sound
        """
        if not self._client or not self._connected:
            logger.warning("VRChat OSC not connected")
            return

        try:
            # Convert emojis to ASCII equivalents for VRChat OSC
            osc_text = convert_emojis_for_osc(text)

            # Build OSC message with all parameters
            # VRChat chatbox input format: (string text, bool immediate, bool sound)
            builder = OscMessageBuilder(address=CHATBOX_INPUT)
            builder.add_arg(osc_text[:MAX_CHATBOX_LENGTH])  # Truncate to max length
            builder.add_arg(send_immediately)
            builder.add_arg(play_sound)
            msg = builder.build()

            self._client.send(msg)
            logger.debug(f"Sent to VRChat chatbox: {text[:50]}...")

        except Exception as e:
            logger.error(f"Failed to send chatbox message: {e}")

    @staticmethod
    def chunk_text(text: str, max_length: int = MAX_CHATBOX_LENGTH) -> list[str]:
        """Split text into chunks that fit VRChat chatbox limit.

        Tries to split at word boundaries when possible.

        Args:
            text: Text to split
            max_length: Maximum chunk length (default 144)

        Returns:
            List of text chunks
        """
        if len(text) <= max_length:
            return [text]

        chunks = []
        remaining = text

        while remaining:
            if len(remaining) <= max_length:
                chunks.append(remaining)
                break

            # Find last space within limit
            split_pos = remaining[:max_length].rfind(' ')

            if split_pos <= 0:
                # No space found, hard split
                split_pos = max_length

            chunk = remaining[:split_pos].strip()
            if chunk:
                chunks.append(chunk)
            remaining = remaining[split_pos:].strip()

        return chunks

    async def send_text(self, text: str, send_immediately: bool = True,
                       play_sound: bool = True, priority: int = 0):
        """Queue text to be sent to VRChat chatbox.

        Long texts will be automatically chunked and sent with delays.

        Args:
            text: Text to send
            send_immediately: Display immediately without Enter key
            play_sound: Play notification sound
            priority: Message priority (higher = more important)
        """
        message = VRChatMessage(
            text=text,
            send_immediately=send_immediately,
            play_sound=play_sound,
            priority=priority
        )
        await self._message_queue.put(message)

        # Start queue processor if not running
        if self._queue_task is None or self._queue_task.done():
            self._queue_task = asyncio.create_task(self._process_queue())

    async def _process_queue(self):
        """Process message queue, sending chunks with appropriate delays."""
        self._is_processing = True

        try:
            while not self._message_queue.empty():
                message = await self._message_queue.get()
                chunks = self.chunk_text(message.text)

                for i, chunk in enumerate(chunks):
                    # Show typing indicator before sending
                    self._send_typing(True)

                    # Small delay to show typing indicator
                    await asyncio.sleep(0.1)

                    # Send the chunk
                    # Only play sound on first chunk
                    play_sound = message.play_sound and i == 0
                    self._send_chatbox(
                        chunk,
                        message.send_immediately,
                        play_sound
                    )

                    # Turn off typing indicator
                    self._send_typing(False)

                    # Notify callback
                    if self._status_callback:
                        self._status_callback('chatbox_sent', {
                            'chunk': i + 1,
                            'total_chunks': len(chunks),
                            'text': chunk
                        })

                    # Delay between chunks
                    if i < len(chunks) - 1:
                        await asyncio.sleep(CHUNK_DELAY)

                self._message_queue.task_done()

        except asyncio.CancelledError:
            logger.debug("Message queue processing cancelled")
        except Exception as e:
            logger.error(f"Error processing message queue: {e}")
        finally:
            self._is_processing = False
            self._send_typing(False)

    def send_text_sync(self, text: str, send_immediately: bool = True,
                       play_sound: bool = True):
        """Synchronously send a single message (no chunking or queue).

        Use this for simple, immediate messages that don't need queuing.

        Args:
            text: Text to send (will be truncated to 144 chars)
            send_immediately: Display immediately
            play_sound: Play notification sound
        """
        self._send_chatbox(text, send_immediately, play_sound)

    def clear_chatbox(self):
        """Clear the VRChat chatbox by sending empty string."""
        self._send_chatbox("", True, False)

    @property
    def is_connected(self) -> bool:
        """Check if connected to VRChat OSC."""
        return self._connected

    @property
    def is_processing(self) -> bool:
        """Check if currently processing message queue."""
        return self._is_processing

    @property
    def queue_size(self) -> int:
        """Get number of messages in queue."""
        return self._message_queue.qsize()


# Singleton instance
_vrchat_osc: Optional[VRChatOSC] = None


def get_vrchat_osc() -> VRChatOSC:
    """Get the singleton VRChat OSC instance."""
    global _vrchat_osc
    if _vrchat_osc is None:
        _vrchat_osc = VRChatOSC()
    return _vrchat_osc
