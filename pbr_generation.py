import cv2
import numpy as np


def ensure_rgb(image: np.ndarray) -> np.ndarray:
    if image.ndim != 3:
        raise ValueError("Expected a color image.")

    if image.shape[2] == 4:
        return image[:, :, :3].copy()

    if image.shape[2] == 3:
        return image.copy()

    raise ValueError("Expected an RGB or RGBA image.")


def preserve_alpha(
    original: np.ndarray,
    rgb_result: np.ndarray,
) -> np.ndarray:
    if original.shape[2] == 4:
        alpha = original[:, :, 3:4]
        return np.concatenate(
            (rgb_result, alpha),
            axis=2,
        )

    return rgb_result


def grayscale_to_rgba(
    grayscale: np.ndarray,
    alpha: np.ndarray | None = None,
) -> np.ndarray:
    grayscale = np.clip(
        grayscale,
        0,
        255,
    ).astype(np.uint8)

    rgb = cv2.cvtColor(
        grayscale,
        cv2.COLOR_GRAY2RGB,
    )

    if alpha is None:
        alpha = np.full(
            (
                grayscale.shape[0],
                grayscale.shape[1],
                1,
            ),
            255,
            dtype=np.uint8,
        )
    elif alpha.ndim == 2:
        alpha = alpha[:, :, np.newaxis]

    return np.concatenate(
        (rgb, alpha),
        axis=2,
    )


def normalize_grayscale(
    image: np.ndarray,
) -> np.ndarray:
    image = image.astype(np.float32)

    minimum = float(np.min(image))
    maximum = float(np.max(image))

    if maximum - minimum < 1e-6:
        return np.zeros_like(
            image,
            dtype=np.uint8,
        )

    normalized = (
        (image - minimum)
        / (maximum - minimum)
        * 255.0
    )

    return np.clip(
        normalized,
        0,
        255,
    ).astype(np.uint8)


def generate_height_map(
    image: np.ndarray,
    blur_radius: int = 5,
    contrast: float = 1.25,
    invert: bool = False,
) -> np.ndarray:
    """
    Estimate height from luminance.

    Brighter pixels become higher by default. This assumption can be
    reversed because different materials require different mappings.
    """

    rgb = ensure_rgb(image)

    grayscale = cv2.cvtColor(
        rgb,
        cv2.COLOR_RGB2GRAY,
    )

    blur_radius = max(
        1,
        int(blur_radius),
    )

    if blur_radius % 2 == 0:
        blur_radius += 1

    if blur_radius > 1:
        grayscale = cv2.GaussianBlur(
            grayscale,
            (blur_radius, blur_radius),
            0,
        )

    grayscale_float = grayscale.astype(
        np.float32
    )

    mean_value = float(
        np.mean(grayscale_float)
    )

    adjusted = (
        grayscale_float - mean_value
    ) * max(0.0, float(contrast)) + mean_value

    adjusted = np.clip(
        adjusted,
        0,
        255,
    ).astype(np.uint8)

    if invert:
        adjusted = 255 - adjusted

    alpha = (
        image[:, :, 3]
        if image.shape[2] == 4
        else None
    )

    return grayscale_to_rgba(
        adjusted,
        alpha,
    )


def generate_normal_map(
    height_map: np.ndarray,
    strength: float = 2.5,
    blur_radius: int = 1,
    invert_y: bool = False,
) -> np.ndarray:
    """
    Generate a tangent-space normal map from a height map.
    """

    if height_map.ndim == 3:
        height = height_map[:, :, 0]
    else:
        height = height_map

    height = height.astype(
        np.float32
    ) / 255.0

    blur_radius = max(
        1,
        int(blur_radius),
    )

    if blur_radius % 2 == 0:
        blur_radius += 1

    if blur_radius > 1:
        height = cv2.GaussianBlur(
            height,
            (blur_radius, blur_radius),
            0,
        )

    gradient_x = cv2.Sobel(
        height,
        cv2.CV_32F,
        1,
        0,
        ksize=3,
    )

    gradient_y = cv2.Sobel(
        height,
        cv2.CV_32F,
        0,
        1,
        ksize=3,
    )

    strength = max(
        0.0,
        float(strength),
    )

    normal_x = -gradient_x * strength
    normal_y = -gradient_y * strength

    if invert_y:
        normal_y *= -1.0

    normal_z = np.ones_like(
        height,
        dtype=np.float32,
    )

    length = np.sqrt(
        normal_x ** 2
        + normal_y ** 2
        + normal_z ** 2
    )

    length = np.maximum(
        length,
        1e-6,
    )

    normal_x /= length
    normal_y /= length
    normal_z /= length

    red = (
        normal_x * 0.5 + 0.5
    ) * 255.0

    green = (
        normal_y * 0.5 + 0.5
    ) * 255.0

    blue = (
        normal_z * 0.5 + 0.5
    ) * 255.0

    normal_rgb = np.stack(
        (red, green, blue),
        axis=2,
    )

    normal_rgb = np.clip(
        normal_rgb,
        0,
        255,
    ).astype(np.uint8)

    if height_map.ndim == 3 and height_map.shape[2] == 4:
        return preserve_alpha(
            height_map,
            normal_rgb,
        )

    return normal_rgb


def generate_roughness_map(
    image: np.ndarray,
    base_roughness: float = 0.60,
    detail_strength: float = 0.45,
    blur_radius: int = 9,
    invert: bool = False,
) -> np.ndarray:
    """
    Estimate roughness using local luminance variation and saturation.

    This is a visual heuristic, not a physical measurement.
    """

    rgb = ensure_rgb(image)

    rgb_float = rgb.astype(
        np.float32
    ) / 255.0

    grayscale = cv2.cvtColor(
        rgb,
        cv2.COLOR_RGB2GRAY,
    ).astype(np.float32) / 255.0

    hsv = cv2.cvtColor(
        rgb,
        cv2.COLOR_RGB2HSV,
    ).astype(np.float32)

    saturation = hsv[:, :, 1] / 255.0

    blur_radius = max(
        3,
        int(blur_radius),
    )

    if blur_radius % 2 == 0:
        blur_radius += 1

    local_mean = cv2.GaussianBlur(
        grayscale,
        (blur_radius, blur_radius),
        0,
    )

    local_square_mean = cv2.GaussianBlur(
        grayscale ** 2,
        (blur_radius, blur_radius),
        0,
    )

    local_variance = np.maximum(
        local_square_mean - local_mean ** 2,
        0.0,
    )

    local_detail = np.sqrt(
        local_variance
    )

    detail_maximum = float(
        np.max(local_detail)
    )

    if detail_maximum > 1e-6:
        local_detail /= detail_maximum

    base_roughness = float(
        np.clip(
            base_roughness,
            0.0,
            1.0,
        )
    )

    detail_strength = float(
        np.clip(
            detail_strength,
            0.0,
            1.0,
        )
    )

    estimated = (
        base_roughness
        + local_detail * detail_strength
        - saturation * 0.15
    )

    estimated = np.clip(
        estimated,
        0.0,
        1.0,
    )

    roughness = (
        estimated * 255.0
    ).astype(np.uint8)

    if invert:
        roughness = 255 - roughness

    alpha = (
        image[:, :, 3]
        if image.shape[2] == 4
        else None
    )

    return grayscale_to_rgba(
        roughness,
        alpha,
    )


def generate_ao_map(
    height_map: np.ndarray,
    radius: int = 25,
    strength: float = 1.5,
    bias: float = 0.02,
) -> np.ndarray:
    """
    Estimate ambient occlusion from height-map cavities.

    Areas lower than their local neighborhood become darker.
    """

    if height_map.ndim == 3:
        height = height_map[:, :, 0]
    else:
        height = height_map

    height = height.astype(
        np.float32
    ) / 255.0

    radius = max(
        3,
        int(radius),
    )

    if radius % 2 == 0:
        radius += 1

    neighborhood_average = cv2.GaussianBlur(
        height,
        (radius, radius),
        0,
    )

    cavity_depth = (
        neighborhood_average
        - height
        - float(bias)
    )

    cavity_depth = np.maximum(
        cavity_depth,
        0.0,
    )

    strength = max(
        0.0,
        float(strength),
    )

    occlusion = 1.0 - (
        cavity_depth * strength
    )

    occlusion = np.clip(
        occlusion,
        0.0,
        1.0,
    )

    ao = (
        occlusion * 255.0
    ).astype(np.uint8)

    alpha = None

    if (
        height_map.ndim == 3
        and height_map.shape[2] == 4
    ):
        alpha = height_map[:, :, 3]

    return grayscale_to_rgba(
        ao,
        alpha,
    )


def generate_pbr_maps(
    image: np.ndarray,
    height_blur: int = 5,
    height_contrast: float = 1.25,
    height_invert: bool = False,
    normal_strength: float = 2.5,
    normal_blur: int = 1,
    normal_invert_y: bool = False,
    roughness_base: float = 0.60,
    roughness_detail: float = 0.45,
    roughness_blur: int = 9,
    roughness_invert: bool = False,
    ao_radius: int = 25,
    ao_strength: float = 1.5,
) -> dict[str, np.ndarray]:
    height = generate_height_map(
        image,
        blur_radius=height_blur,
        contrast=height_contrast,
        invert=height_invert,
    )

    normal = generate_normal_map(
        height,
        strength=normal_strength,
        blur_radius=normal_blur,
        invert_y=normal_invert_y,
    )

    roughness = generate_roughness_map(
        image,
        base_roughness=roughness_base,
        detail_strength=roughness_detail,
        blur_radius=roughness_blur,
        invert=roughness_invert,
    )

    ambient_occlusion = generate_ao_map(
        height,
        radius=ao_radius,
        strength=ao_strength,
    )

    return {
        "Height": height,
        "Normal": normal,
        "Roughness": roughness,
        "AO": ambient_occlusion,
    }