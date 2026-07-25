import cv2
import numpy as np


def preserve_alpha(
    original: np.ndarray,
    rgb_result: np.ndarray,
) -> np.ndarray:
    """
    Reattach the original alpha channel after processing RGB data.
    """

    if original.shape[2] == 4:
        alpha = original[:, :, 3:4]
        return np.concatenate((rgb_result, alpha), axis=2)

    return rgb_result


def normalize_lighting(
    image: np.ndarray,
    strength: float = 0.65,
    blur_radius: int = 81,
) -> np.ndarray:
    """
    Reduce broad, uneven illumination while preserving local detail.

    strength:
        0.0 leaves the image unchanged.
        1.0 applies the complete correction.

    blur_radius:
        Approximate size of lighting variations to remove.
        Must be odd.
    """

    strength = float(np.clip(strength, 0.0, 1.0))

    if strength == 0.0:
        return image.copy()

    if blur_radius < 3:
        blur_radius = 3

    if blur_radius % 2 == 0:
        blur_radius += 1

    rgb = image[:, :, :3].astype(np.float32)

    illumination = cv2.GaussianBlur(
        rgb,
        (blur_radius, blur_radius),
        0,
    )

    illumination = np.maximum(
        illumination,
        1.0,
    )

    target_brightness = np.mean(
        illumination,
        axis=(0, 1),
        keepdims=True,
    )

    corrected = (
        rgb
        / illumination
        * target_brightness
    )

    corrected = np.clip(
        corrected,
        0,
        255,
    )

    blended = (
        rgb * (1.0 - strength)
        + corrected * strength
    )

    return preserve_alpha(
        image,
        blended.astype(np.uint8),
    )


def reduce_shadows(
    image: np.ndarray,
    strength: float = 0.45,
) -> np.ndarray:
    """
    Brighten dark areas more than bright areas.

    This reduces shadows but does not reconstruct detail that was
    completely lost in an underexposed region.
    """

    strength = float(np.clip(strength, 0.0, 1.0))

    if strength == 0.0:
        return image.copy()

    rgb = image[:, :, :3].astype(np.float32) / 255.0

    luminance = cv2.cvtColor(
        rgb,
        cv2.COLOR_RGB2GRAY,
    )

    shadow_mask = np.clip(
        1.0 - luminance,
        0.0,
        1.0,
    )

    # Emphasize darker regions and minimize changes to highlights.
    shadow_mask = shadow_mask ** 2

    lift_amount = (
        shadow_mask[:, :, np.newaxis]
        * strength
        * 0.65
    )

    lifted = rgb + (
        1.0 - rgb
    ) * lift_amount

    lifted = np.clip(
        lifted * 255.0,
        0,
        255,
    ).astype(np.uint8)

    return preserve_alpha(
        image,
        lifted,
    )


def apply_clahe(
    image: np.ndarray,
    strength: float = 0.65,
    clip_limit: float = 2.0,
    grid_size: int = 8,
) -> np.ndarray:
    """
    Apply local histogram equalization to luminance only.

    Processing only luminance avoids independently shifting the RGB
    channels and creating unusual colors.
    """

    strength = float(np.clip(strength, 0.0, 1.0))

    if strength == 0.0:
        return image.copy()

    rgb = image[:, :, :3]

    lab = cv2.cvtColor(
        rgb,
        cv2.COLOR_RGB2LAB,
    )

    lightness, channel_a, channel_b = cv2.split(
        lab
    )

    clahe = cv2.createCLAHE(
        clipLimit=max(0.1, float(clip_limit)),
        tileGridSize=(
            max(2, int(grid_size)),
            max(2, int(grid_size)),
        ),
    )

    adjusted_lightness = clahe.apply(
        lightness
    )

    blended_lightness = cv2.addWeighted(
        lightness,
        1.0 - strength,
        adjusted_lightness,
        strength,
        0,
    )

    adjusted_lab = cv2.merge(
        (
            blended_lightness,
            channel_a,
            channel_b,
        )
    )

    adjusted_rgb = cv2.cvtColor(
        adjusted_lab,
        cv2.COLOR_LAB2RGB,
    )

    return preserve_alpha(
        image,
        adjusted_rgb,
    )


def gray_world_white_balance(
    image: np.ndarray,
    strength: float = 0.60,
) -> np.ndarray:
    """
    Correct broad color casts using the gray-world assumption.

    This assumes that the average scene color should be approximately
    neutral. It works well for many material photographs but should
    remain optional.
    """

    strength = float(np.clip(strength, 0.0, 1.0))

    if strength == 0.0:
        return image.copy()

    rgb = image[:, :, :3].astype(np.float32)

    channel_means = np.mean(
        rgb,
        axis=(0, 1),
    )

    overall_mean = float(
        np.mean(channel_means)
    )

    safe_means = np.maximum(
        channel_means,
        1.0,
    )

    scale_factors = (
        overall_mean / safe_means
    )

    balanced = rgb * scale_factors

    balanced = np.clip(
        balanced,
        0,
        255,
    )

    blended = (
        rgb * (1.0 - strength)
        + balanced * strength
    )

    return preserve_alpha(
        image,
        blended.astype(np.uint8),
    )


def adjust_saturation(
    image: np.ndarray,
    amount: float = 1.0,
) -> np.ndarray:
    """
    Adjust saturation.

    1.0 means unchanged.
    0.0 means grayscale.
    Values above 1.0 increase saturation.
    """

    amount = float(np.clip(amount, 0.0, 2.0))

    rgb = image[:, :, :3]

    hsv = cv2.cvtColor(
        rgb,
        cv2.COLOR_RGB2HSV,
    ).astype(np.float32)

    hsv[:, :, 1] *= amount

    hsv[:, :, 1] = np.clip(
        hsv[:, :, 1],
        0,
        255,
    )

    adjusted_rgb = cv2.cvtColor(
        hsv.astype(np.uint8),
        cv2.COLOR_HSV2RGB,
    )

    return preserve_alpha(
        image,
        adjusted_rgb,
    )


def apply_texture_adjustments(
    image: np.ndarray,
    lighting_enabled: bool = False,
    lighting_strength: float = 0.65,
    shadow_enabled: bool = False,
    shadow_strength: float = 0.45,
    contrast_enabled: bool = False,
    contrast_strength: float = 0.65,
    color_enabled: bool = False,
    color_strength: float = 0.60,
    saturation: float = 1.0,
) -> np.ndarray:
    """
    Apply all enabled adjustments in a predictable order.

    The original image array is never modified.
    """

    result = image.copy()

    if lighting_enabled:
        result = normalize_lighting(
            result,
            strength=lighting_strength,
        )

    if shadow_enabled:
        result = reduce_shadows(
            result,
            strength=shadow_strength,
        )

    if contrast_enabled:
        result = apply_clahe(
            result,
            strength=contrast_strength,
        )

    if color_enabled:
        result = gray_world_white_balance(
            result,
            strength=color_strength,
        )

    if saturation != 1.0:
        result = adjust_saturation(
            result,
            amount=saturation,
        )

    return result