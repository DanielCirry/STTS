"""
RMVPE (Robust Model for Vocal Pitch Estimation) pitch extraction.

Ported from RVC infer/lib/rmvpe.py

RMVPE is a neural network-based F0 (fundamental frequency) estimator
that provides more accurate pitch tracking than signal-processing methods
(Harvest, DIO) especially on speech audio. It is the recommended pitch
method for RVC voice conversion.

Input: 16kHz mono audio
Output: F0 contour in Hz (one value per 10ms frame)
"""

import logging
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

logger = logging.getLogger('stts.rvc.rmvpe')


class BiGRU(nn.Module):
    """Bidirectional GRU layer."""

    def __init__(self, input_features, hidden_features, num_layers):
        super().__init__()
        self.gru = nn.GRU(
            input_features,
            hidden_features,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,
        )

    def forward(self, x):
        return self.gru(x)[0]


class ConvBlockRes(nn.Module):
    """Convolutional block with residual connection."""

    def __init__(self, in_channels, out_channels, momentum=0.01):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(
                in_channels=in_channels,
                out_channels=out_channels,
                kernel_size=(3, 3),
                stride=(1, 1),
                padding=(1, 1),
                bias=False,
            ),
            nn.BatchNorm2d(out_channels, momentum=momentum),
            nn.ReLU(),
            nn.Conv2d(
                in_channels=out_channels,
                out_channels=out_channels,
                kernel_size=(3, 3),
                stride=(1, 1),
                padding=(1, 1),
                bias=False,
            ),
            nn.BatchNorm2d(out_channels, momentum=momentum),
            nn.ReLU(),
        )
        if in_channels != out_channels:
            self.shortcut = nn.Conv2d(in_channels, out_channels, (1, 1))
        else:
            self.shortcut = nn.Identity()

    def forward(self, x):
        return self.conv(x) + self.shortcut(x)


class ResEncoderBlock(nn.Module):
    """Residual encoder block with average pooling."""

    def __init__(self, in_channels, out_channels, kernel_size, n_blocks=1, momentum=0.01):
        super().__init__()
        self.n_blocks = n_blocks
        self.conv = nn.ModuleList()
        self.conv.append(ConvBlockRes(in_channels, out_channels, momentum))
        for _ in range(n_blocks - 1):
            self.conv.append(ConvBlockRes(out_channels, out_channels, momentum))
        self.kernel_size = kernel_size
        if self.kernel_size is not None:
            self.pool = nn.AvgPool2d(kernel_size=kernel_size)

    def forward(self, x):
        for i in range(self.n_blocks):
            x = self.conv[i](x)
        if self.kernel_size is not None:
            return x, self.pool(x)
        else:
            return x


class ResDecoderBlock(nn.Module):
    """Residual decoder block with upsampling."""

    def __init__(self, in_channels, out_channels, stride, n_blocks=1, momentum=0.01):
        super().__init__()
        out_padding = (0, 1) if stride == (1, 2) else (1, 1)
        self.n_blocks = n_blocks
        self.conv1 = nn.Sequential(
            nn.ConvTranspose2d(
                in_channels=in_channels,
                out_channels=out_channels,
                kernel_size=(3, 3),
                stride=stride,
                padding=(1, 1),
                output_padding=out_padding,
                bias=False,
            ),
            nn.BatchNorm2d(out_channels, momentum=momentum),
            nn.ReLU(),
        )
        self.conv2 = nn.ModuleList()
        self.conv2.append(ConvBlockRes(out_channels * 2, out_channels, momentum))
        for _ in range(n_blocks - 1):
            self.conv2.append(ConvBlockRes(out_channels, out_channels, momentum))

    def forward(self, x, concat_tensor):
        x = self.conv1(x)
        # Pooling/upsampling rounding can cause off-by-one between decoder
        # output and encoder skip connection — trim both to the minimum
        min_h = min(x.shape[2], concat_tensor.shape[2])
        min_w = min(x.shape[3], concat_tensor.shape[3])
        x = x[:, :, :min_h, :min_w]
        concat_tensor = concat_tensor[:, :, :min_h, :min_w]
        x = torch.cat((x, concat_tensor), dim=1)
        for i in range(self.n_blocks):
            x = self.conv2[i](x)
        return x


class _Encoder(nn.Module):
    """Encoder wrapper with batch norm and layer list to match checkpoint keys."""

    def __init__(self, in_channels, en_out_channels, kernel_size, n_blocks, en_de_layers):
        super().__init__()
        self.bn = nn.BatchNorm2d(in_channels)
        self.layers = nn.ModuleList()
        self.layers.append(
            ResEncoderBlock(in_channels, en_out_channels, kernel_size, n_blocks)
        )
        for i in range(en_de_layers - 1):
            self.layers.append(
                ResEncoderBlock(
                    en_out_channels * (2 ** i),
                    en_out_channels * (2 ** (i + 1)),
                    kernel_size,
                    n_blocks,
                )
            )


class _Intermediate(nn.Module):
    """Intermediate wrapper to match checkpoint keys."""

    def __init__(self, in_channels, n_blocks, inter_layers):
        super().__init__()
        out_channels = in_channels * 2
        self.layers = nn.ModuleList()
        self.layers.append(ResEncoderBlock(in_channels, out_channels, None, n_blocks))
        for _ in range(inter_layers - 1):
            self.layers.append(ResEncoderBlock(out_channels, out_channels, None, n_blocks))


class _Decoder(nn.Module):
    """Decoder wrapper to match checkpoint keys."""

    def __init__(self, en_out_channels, kernel_size, n_blocks, en_de_layers):
        super().__init__()
        self.layers = nn.ModuleList()
        for i in range(en_de_layers):
            self.layers.append(
                ResDecoderBlock(
                    en_out_channels * (2 ** (en_de_layers - i)),
                    en_out_channels * (2 ** (en_de_layers - 1 - i)),
                    kernel_size,
                    n_blocks,
                )
            )


class DeepUnet(nn.Module):
    """Deep U-Net architecture for RMVPE."""

    def __init__(
        self,
        kernel_size,
        n_blocks,
        en_de_layers=5,
        inter_layers=4,
        in_channels=1,
        en_out_channels=16,
    ):
        super().__init__()
        self.encoder = _Encoder(in_channels, en_out_channels, kernel_size, n_blocks, en_de_layers)
        self.intermediate = _Intermediate(
            en_out_channels * (2 ** (en_de_layers - 1)), n_blocks, inter_layers
        )
        self.decoder = _Decoder(en_out_channels, kernel_size, n_blocks, en_de_layers)

    def forward(self, x):
        x = self.encoder.bn(x)
        concat_tensors = []
        for encoder_layer in self.encoder.layers:
            x, pool = encoder_layer(x)
            concat_tensors.append(x)
            x = pool

        for inter_layer in self.intermediate.layers:
            x = inter_layer(x)

        concat_tensors = concat_tensors[::-1]
        for i, decoder_layer in enumerate(self.decoder.layers):
            x = decoder_layer(x, concat_tensors[i])

        return x


class E2E(nn.Module):
    """End-to-end RMVPE model: mel spectrogram -> F0 probability."""

    def __init__(
        self,
        n_blocks,
        n_gru,
        kernel_size,
        en_de_layers=5,
        inter_layers=4,
        in_channels=1,
        en_out_channels=16,
    ):
        super().__init__()
        self.unet = DeepUnet(
            kernel_size,
            n_blocks,
            en_de_layers,
            inter_layers,
            in_channels,
            en_out_channels,
        )
        self.cnn = nn.Conv2d(en_out_channels, 3, (3, 3), padding=(1, 1))
        if n_gru:
            self.fc = nn.Sequential(
                BiGRU(3 * 128, 256, n_gru),
                nn.Linear(512, 360),
                nn.Dropout(0.25),
                nn.Sigmoid(),
            )
        else:
            self.fc = nn.Sequential(
                nn.Linear(3 * nn.N_MELS, nn.N_CLASS),
                nn.Dropout(0.25),
                nn.Sigmoid(),
            )

    def forward(self, mel):
        mel = mel.transpose(-1, -2).unsqueeze(1)
        x = self.cnn(self.unet(mel)).transpose(1, 2).flatten(-2)
        x = self.fc(x)
        return x


class MelSpectrogram(nn.Module):
    """Mel spectrogram extractor for RMVPE input."""

    def __init__(
        self,
        is_half,
        n_mel_channels=128,
        sampling_rate=16000,
        win_length=1024,
        hop_length=160,
        n_fft=1024,
        mel_fmin=30,
        mel_fmax=8000,
    ):
        super().__init__()
        self.is_half = is_half
        self.sampling_rate = sampling_rate
        self.n_fft = n_fft
        self.win_length = win_length
        self.hop_length = hop_length

        # Build mel filterbank
        self.mel_basis = self._build_mel_basis(
            n_fft, n_mel_channels, sampling_rate, mel_fmin, mel_fmax
        )

        self.hann_window = {}

    def _build_mel_basis(self, n_fft, n_mels, sr, fmin, fmax):
        """Build mel filterbank matrix."""
        try:
            import librosa
            mel_basis = librosa.filters.mel(sr=sr, n_fft=n_fft, n_mels=n_mels, fmin=fmin, fmax=fmax)
        except ImportError:
            # Manual mel filterbank computation
            mel_basis = self._mel_filterbank(sr, n_fft, n_mels, fmin, fmax)
        return mel_basis

    @staticmethod
    def _mel_filterbank(sr, n_fft, n_mels, fmin, fmax):
        """Manual mel filterbank computation."""
        def hz_to_mel(hz):
            return 2595.0 * np.log10(1.0 + hz / 700.0)

        def mel_to_hz(mel):
            return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)

        mel_min = hz_to_mel(fmin)
        mel_max = hz_to_mel(fmax)
        mels = np.linspace(mel_min, mel_max, n_mels + 2)
        freqs = mel_to_hz(mels)
        fft_freqs = np.linspace(0, sr / 2, n_fft // 2 + 1)

        weights = np.zeros((n_mels, n_fft // 2 + 1))
        for i in range(n_mels):
            lower = freqs[i]
            center = freqs[i + 1]
            upper = freqs[i + 2]
            for j, f in enumerate(fft_freqs):
                if lower <= f <= center:
                    weights[i, j] = (f - lower) / (center - lower) if center != lower else 0
                elif center < f <= upper:
                    weights[i, j] = (upper - f) / (upper - center) if upper != center else 0
        return weights

    def forward(self, audio, center=True):
        """Extract mel spectrogram from audio.

        Args:
            audio: Input audio tensor [B, T] at 16kHz.
            center: Whether to center-pad the STFT.

        Returns:
            Mel spectrogram tensor [B, n_mels, T].
        """
        device = audio.device
        dtype = audio.dtype

        if str(device) not in self.hann_window:
            self.hann_window[str(device)] = torch.hann_window(
                self.win_length
            ).to(device)

        # Pad audio
        padding = int((self.n_fft - self.hop_length) / 2)
        audio = F.pad(audio, (padding, padding), mode="reflect")

        # STFT
        fft = torch.stft(
            audio,
            self.n_fft,
            hop_length=self.hop_length,
            win_length=self.win_length,
            window=self.hann_window[str(device)],
            center=center,
            return_complex=True,
        )

        magnitude = torch.abs(fft)

        # Apply mel filterbank
        mel_basis_tensor = torch.from_numpy(self.mel_basis).to(
            dtype=dtype, device=device
        )
        mel_output = torch.matmul(mel_basis_tensor, magnitude)

        # Log mel
        log_mel = torch.log(torch.clamp(mel_output, min=1e-5))

        return log_mel


class RMVPE:
    """RMVPE pitch extraction model.

    Usage:
        rmvpe = RMVPE('rmvpe.pt', device)
        f0 = rmvpe.infer_from_audio(audio_16k, thred=0.03)
    """

    def __init__(self, model_path: str, device: torch.device):
        """Initialize RMVPE model.

        Args:
            model_path: Path to rmvpe.pt weights file.
            device: Torch device (CPU or DirectML).
        """
        self.device = device

        # Build model
        self.model = E2E(4, 1, (2, 2))
        ckpt = torch.load(model_path, map_location="cpu", weights_only=False)
        self.model.load_state_dict(ckpt)
        self.model = self.model.eval().to(device)

        # Mel spectrogram extractor
        self.mel_extractor = MelSpectrogram(
            is_half=False,
            n_mel_channels=128,
            sampling_rate=16000,
            win_length=1024,
            hop_length=160,
            n_fft=1024,
            mel_fmin=30,
            mel_fmax=8000,
        )

        # Frequency bins for pitch decoding (360 bins, 20-1200 Hz log scale)
        cents_mapping = 20 * np.arange(1, 361) + 1997.3794084376191
        self.cents_mapping = np.pad(cents_mapping, (4, 4))

        logger.debug(f"RMVPE model loaded on {device}")

    @torch.no_grad()
    def infer_from_audio(self, audio: np.ndarray, thred: float = 0.03) -> np.ndarray:
        """Extract F0 from audio.

        Args:
            audio: Float32 numpy array at 16kHz mono.
            thred: Voicing threshold (higher = more voiced frames filtered out).

        Returns:
            F0 array in Hz (one value per 10ms frame). Unvoiced frames = 0.
        """
        audio_tensor = torch.from_numpy(audio).float().unsqueeze(0).to(self.device)

        # Extract mel spectrogram
        mel = self.mel_extractor(audio_tensor, center=True)

        # Run model
        hidden = self.model(mel)

        # Decode pitch from hidden representation
        return self._decode(hidden, thred)

    def _decode(self, hidden: torch.Tensor, thred: float) -> np.ndarray:
        """Decode F0 from model output probabilities.

        Args:
            hidden: Model output [B, T, 360] probabilities.
            thred: Voicing threshold.

        Returns:
            F0 array in Hz.
        """
        hidden = hidden.squeeze(0).cpu().numpy()

        # For each frame, find the center of mass of the probability distribution
        # to get a sub-bin-resolution pitch estimate
        center = np.argmax(hidden, axis=1)
        hidden[hidden < thred] = 0

        # Weighted average around peak for sub-bin resolution
        starts = np.clip(center - 4, 0, hidden.shape[1] - 1)
        ends = np.clip(center + 5, 0, hidden.shape[1])

        f0 = np.zeros(hidden.shape[0])
        for i in range(hidden.shape[0]):
            s, e = starts[i], ends[i]
            if e <= s:
                continue
            weights = hidden[i, s:e]
            w_sum = weights.sum()
            if w_sum < thred:
                continue
            # Weighted average of cents
            cent_values = self.cents_mapping[s + 4: e + 4]  # offset by padding
            if len(cent_values) != len(weights):
                cent_values = cent_values[:len(weights)]
            f0[i] = np.sum(cent_values * weights) / w_sum

        # Convert cents to Hz
        f0 = 10 * 2 ** (f0 / 1200)
        f0[f0 < 20] = 0  # Below human vocal range = unvoiced

        return f0
