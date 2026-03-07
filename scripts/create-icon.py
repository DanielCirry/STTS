"""
Generate a friendly STTS icon
Creates an .ico file with a microphone and speech bubble design
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_stts_icon():
    """Create a friendly STTS icon with microphone and speech elements."""

    # Create multiple sizes for ICO file
    sizes = [16, 32, 48, 64, 128, 256]
    images = []

    for size in sizes:
        # Create image with transparent background
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Colors - friendly purple/blue gradient feel
        bg_color = (99, 102, 241)  # Indigo
        accent_color = (168, 85, 247)  # Purple
        white = (255, 255, 255)

        # Draw rounded rectangle background
        margin = size // 10
        corner_radius = size // 4

        # Draw background circle
        draw.ellipse(
            [margin, margin, size - margin, size - margin],
            fill=bg_color
        )

        # Draw microphone icon
        mic_width = size // 4
        mic_height = size // 2.5
        mic_x = size // 2 - mic_width // 2
        mic_y = size // 4

        # Microphone body (rounded rectangle approximation with ellipse + rectangle)
        mic_top = mic_y
        mic_bottom = mic_y + mic_height * 0.6

        # Top of mic (rounded)
        draw.ellipse(
            [mic_x, mic_top, mic_x + mic_width, mic_top + mic_width],
            fill=white
        )

        # Body of mic
        draw.rectangle(
            [mic_x, mic_top + mic_width // 2, mic_x + mic_width, mic_bottom],
            fill=white
        )

        # Bottom of mic (rounded)
        draw.ellipse(
            [mic_x, mic_bottom - mic_width // 2, mic_x + mic_width, mic_bottom + mic_width // 2],
            fill=white
        )

        # Mic stand
        stand_width = size // 12
        stand_x = size // 2 - stand_width // 2
        stand_top = mic_bottom + mic_width // 4
        stand_bottom = size - margin - size // 8

        draw.rectangle(
            [stand_x, stand_top, stand_x + stand_width, stand_bottom],
            fill=white
        )

        # Mic base
        base_width = size // 3
        base_x = size // 2 - base_width // 2
        base_height = size // 16

        draw.ellipse(
            [base_x, stand_bottom - base_height // 2, base_x + base_width, stand_bottom + base_height],
            fill=white
        )

        # Sound waves (speech indicator)
        wave_start_x = size // 2 + mic_width
        wave_y = size // 3

        for i, offset in enumerate([0, size // 10, size // 5]):
            wave_x = wave_start_x + offset
            wave_height = size // 6 - i * (size // 20)
            if wave_height > 2:
                draw.arc(
                    [wave_x, wave_y - wave_height // 2, wave_x + size // 12, wave_y + wave_height // 2],
                    start=-60, end=60,
                    fill=white,
                    width=max(1, size // 32)
                )

        images.append(img)

    return images


def save_icon(images, output_path):
    """Save images as ICO file."""
    # ICO format requires the largest image first
    images_reversed = list(reversed(images))
    images_reversed[0].save(
        output_path,
        format='ICO',
        sizes=[(img.width, img.height) for img in images_reversed]
    )


def main():
    # Determine output path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)

    # Create assets directory if needed
    assets_dir = os.path.join(project_root, 'assets')
    os.makedirs(assets_dir, exist_ok=True)

    output_path = os.path.join(assets_dir, 'stts-icon.ico')

    print("Creating STTS icon...")
    images = create_stts_icon()
    save_icon(images, output_path)
    print(f"Icon saved to: {output_path}")

    # Also create a PNG for preview
    png_path = os.path.join(assets_dir, 'stts-icon.png')
    images[-1].save(png_path, format='PNG')
    print(f"PNG preview saved to: {png_path}")


if __name__ == "__main__":
    main()
