"""Legacy camera FocalPlane specs (from exifToolWriter.ts CAMERA_SPECS)."""

from __future__ import annotations

from typing import TypedDict


class CameraSpec(TypedDict):
    focal_plane_x_res: float
    focal_plane_y_res: float
    pixel_width: int
    pixel_height: int
    sensor_width: float
    sensor_height: float


CAMERA_SPECS: dict[str, CameraSpec] = {
    "Canon EOS-1D X": {
        "focal_plane_x_res": 3545.83,
        "focal_plane_y_res": 3526.53,
        "pixel_width": 5184,
        "pixel_height": 3456,
        "sensor_width": 36.0,
        "sensor_height": 24.0,
    },
    "Canon EOS-1D X Mark II": {
        "focal_plane_x_res": 3545.83,
        "focal_plane_y_res": 3526.53,
        "pixel_width": 5472,
        "pixel_height": 3648,
        "sensor_width": 36.0,
        "sensor_height": 24.0,
    },
    "Canon EOS-1D X Mark III": {
        "focal_plane_x_res": 3545.83,
        "focal_plane_y_res": 3526.53,
        "pixel_width": 5472,
        "pixel_height": 3648,
        "sensor_width": 36.0,
        "sensor_height": 24.0,
    },
    "Canon EOS 5D Mark IV": {
        "focal_plane_x_res": 3796.99,
        "focal_plane_y_res": 3797.00,
        "pixel_width": 6720,
        "pixel_height": 4480,
        "sensor_width": 36.0,
        "sensor_height": 24.0,
    },
    "Canon EOS 5D Mark III": {
        "focal_plane_x_res": 3479.17,
        "focal_plane_y_res": 3479.17,
        "pixel_width": 5760,
        "pixel_height": 3840,
        "sensor_width": 36.0,
        "sensor_height": 24.0,
    },
    "Canon EOS 6D Mark II": {
        "focal_plane_x_res": 3545.83,
        "focal_plane_y_res": 3526.53,
        "pixel_width": 6240,
        "pixel_height": 4160,
        "sensor_width": 35.9,
        "sensor_height": 24.0,
    },
    "Canon EOS 90D": {
        "focal_plane_x_res": 5765.00,
        "focal_plane_y_res": 5765.00,
        "pixel_width": 6960,
        "pixel_height": 4640,
        "sensor_width": 22.3,
        "sensor_height": 14.9,
    },
    "Canon EOS 850D": {
        "focal_plane_x_res": 5765.00,
        "focal_plane_y_res": 5765.00,
        "pixel_width": 6000,
        "pixel_height": 4000,
        "sensor_width": 22.3,
        "sensor_height": 14.9,
    },
    "Canon EOS R5": {
        "focal_plane_x_res": 4016.06,
        "focal_plane_y_res": 4016.06,
        "pixel_width": 8192,
        "pixel_height": 5464,
        "sensor_width": 36.0,
        "sensor_height": 24.0,
    },
    "Canon EOS R6": {
        "focal_plane_x_res": 3545.83,
        "focal_plane_y_res": 3526.53,
        "pixel_width": 5472,
        "pixel_height": 3648,
        "sensor_width": 36.0,
        "sensor_height": 24.0,
    },
    "Canon EOS R6 Mark II": {
        "focal_plane_x_res": 3545.83,
        "focal_plane_y_res": 3526.53,
        "pixel_width": 5472,
        "pixel_height": 3648,
        "sensor_width": 36.0,
        "sensor_height": 24.0,
    },
    "Canon EOS R3": {
        "focal_plane_x_res": 3545.83,
        "focal_plane_y_res": 3526.53,
        "pixel_width": 6000,
        "pixel_height": 4000,
        "sensor_width": 36.0,
        "sensor_height": 24.0,
    },
    "Nikon D850": {
        "focal_plane_x_res": 4016.06,
        "focal_plane_y_res": 4016.06,
        "pixel_width": 8256,
        "pixel_height": 5504,
        "sensor_width": 35.9,
        "sensor_height": 23.9,
    },
    "Nikon D780": {
        "focal_plane_x_res": 3545.83,
        "focal_plane_y_res": 3526.53,
        "pixel_width": 6048,
        "pixel_height": 4024,
        "sensor_width": 35.9,
        "sensor_height": 23.9,
    },
    "Nikon D750": {
        "focal_plane_x_res": 3545.83,
        "focal_plane_y_res": 3526.53,
        "pixel_width": 6016,
        "pixel_height": 4016,
        "sensor_width": 35.9,
        "sensor_height": 24.0,
    },
    "Nikon D7500": {
        "focal_plane_x_res": 5765.00,
        "focal_plane_y_res": 5765.00,
        "pixel_width": 5568,
        "pixel_height": 3712,
        "sensor_width": 23.5,
        "sensor_height": 15.7,
    },
    "Nikon D5600": {
        "focal_plane_x_res": 5765.00,
        "focal_plane_y_res": 5765.00,
        "pixel_width": 6000,
        "pixel_height": 4000,
        "sensor_width": 23.5,
        "sensor_height": 15.6,
    },
    "Nikon Z6 II": {
        "focal_plane_x_res": 3545.83,
        "focal_plane_y_res": 3526.53,
        "pixel_width": 6048,
        "pixel_height": 4024,
        "sensor_width": 35.9,
        "sensor_height": 23.9,
    },
    "Nikon Z7 II": {
        "focal_plane_x_res": 4267.72,
        "focal_plane_y_res": 4267.72,
        "pixel_width": 8256,
        "pixel_height": 5504,
        "sensor_width": 35.9,
        "sensor_height": 23.9,
    },
    "Sony A7R IV": {
        "focal_plane_x_res": 4267.72,
        "focal_plane_y_res": 4267.72,
        "pixel_width": 9504,
        "pixel_height": 6336,
        "sensor_width": 35.7,
        "sensor_height": 23.8,
    },
    "Sony A7R V": {
        "focal_plane_x_res": 4267.72,
        "focal_plane_y_res": 4267.72,
        "pixel_width": 9504,
        "pixel_height": 6336,
        "sensor_width": 35.7,
        "sensor_height": 23.8,
    },
    "Sony A7 IV": {
        "focal_plane_x_res": 3545.83,
        "focal_plane_y_res": 3526.53,
        "pixel_width": 7008,
        "pixel_height": 4672,
        "sensor_width": 35.9,
        "sensor_height": 23.9,
    },
    "Sony A7 III": {
        "focal_plane_x_res": 3545.83,
        "focal_plane_y_res": 3526.53,
        "pixel_width": 6000,
        "pixel_height": 4000,
        "sensor_width": 35.6,
        "sensor_height": 23.8,
    },
    "Sony A9 II": {
        "focal_plane_x_res": 3545.83,
        "focal_plane_y_res": 3526.53,
        "pixel_width": 6000,
        "pixel_height": 4000,
        "sensor_width": 35.6,
        "sensor_height": 23.8,
    },
    "Sony A6600": {
        "focal_plane_x_res": 6240.00,
        "focal_plane_y_res": 6240.00,
        "pixel_width": 6000,
        "pixel_height": 4000,
        "sensor_width": 23.5,
        "sensor_height": 15.6,
    },
    "Pentax K-1 Mark II": {
        "focal_plane_x_res": 3543.31,
        "focal_plane_y_res": 3543.31,
        "pixel_width": 7360,
        "pixel_height": 4912,
        "sensor_width": 35.9,
        "sensor_height": 24.0,
    },
    "Pentax K-3 Mark III": {
        "focal_plane_x_res": 5765.00,
        "focal_plane_y_res": 5765.00,
        "pixel_width": 6192,
        "pixel_height": 4128,
        "sensor_width": 23.3,
        "sensor_height": 15.5,
    },
    "Pentax K-70": {
        "focal_plane_x_res": 5765.00,
        "focal_plane_y_res": 5765.00,
        "pixel_width": 6016,
        "pixel_height": 4000,
        "sensor_width": 23.5,
        "sensor_height": 15.6,
    },
    "Fujifilm X-T4": {
        "focal_plane_x_res": 6240.00,
        "focal_plane_y_res": 6240.00,
        "pixel_width": 6240,
        "pixel_height": 4160,
        "sensor_width": 23.5,
        "sensor_height": 15.6,
    },
    "Fujifilm X-T5": {
        "focal_plane_x_res": 7752.00,
        "focal_plane_y_res": 7752.00,
        "pixel_width": 8240,
        "pixel_height": 5504,
        "sensor_width": 23.5,
        "sensor_height": 15.6,
    },
    "Fujifilm X-S10": {
        "focal_plane_x_res": 6240.00,
        "focal_plane_y_res": 6240.00,
        "pixel_width": 6240,
        "pixel_height": 4160,
        "sensor_width": 23.5,
        "sensor_height": 15.6,
    },
    "Fujifilm GFX 50S II": {
        "focal_plane_x_res": 3200.00,
        "focal_plane_y_res": 3200.00,
        "pixel_width": 8256,
        "pixel_height": 6192,
        "sensor_width": 43.8,
        "sensor_height": 32.9,
    },
    "OM System OM-1": {
        "focal_plane_x_res": 9600.00,
        "focal_plane_y_res": 9600.00,
        "pixel_width": 5184,
        "pixel_height": 3888,
        "sensor_width": 17.4,
        "sensor_height": 13.0,
    },
    "Olympus OM-D E-M1 Mark III": {
        "focal_plane_x_res": 9600.00,
        "focal_plane_y_res": 9600.00,
        "pixel_width": 5184,
        "pixel_height": 3888,
        "sensor_width": 17.4,
        "sensor_height": 13.0,
    },
    "Panasonic Lumix S5 II": {
        "focal_plane_x_res": 3545.83,
        "focal_plane_y_res": 3526.53,
        "pixel_width": 6000,
        "pixel_height": 4000,
        "sensor_width": 35.6,
        "sensor_height": 23.8,
    },
    "Panasonic Lumix G9 II": {
        "focal_plane_x_res": 9600.00,
        "focal_plane_y_res": 9600.00,
        "pixel_width": 5776,
        "pixel_height": 4336,
        "sensor_width": 17.3,
        "sensor_height": 13.0,
    },
    "Apple iPhone 15 Pro": {
        "focal_plane_x_res": 14400.00,
        "focal_plane_y_res": 14400.00,
        "pixel_width": 4032,
        "pixel_height": 3024,
        "sensor_width": 6.765,
        "sensor_height": 5.074,
    },
    "Apple iPhone 15 Pro Max": {
        "focal_plane_x_res": 14400.00,
        "focal_plane_y_res": 14400.00,
        "pixel_width": 4032,
        "pixel_height": 3024,
        "sensor_width": 6.765,
        "sensor_height": 5.074,
    },
    "Apple iPhone 16": {
        "focal_plane_x_res": 14400.00,
        "focal_plane_y_res": 14400.00,
        "pixel_width": 4032,
        "pixel_height": 3024,
        "sensor_width": 6.765,
        "sensor_height": 5.074,
    },
    "Apple iPhone 16 Pro": {
        "focal_plane_x_res": 14400.00,
        "focal_plane_y_res": 14400.00,
        "pixel_width": 4032,
        "pixel_height": 3024,
        "sensor_width": 6.765,
        "sensor_height": 5.074,
    },
    "Apple iPhone 16 Pro Max": {
        "focal_plane_x_res": 14400.00,
        "focal_plane_y_res": 14400.00,
        "pixel_width": 4032,
        "pixel_height": 3024,
        "sensor_width": 6.765,
        "sensor_height": 5.074,
    },
    "Apple iPhone 14 Pro": {
        "focal_plane_x_res": 14400.00,
        "focal_plane_y_res": 14400.00,
        "pixel_width": 4032,
        "pixel_height": 3024,
        "sensor_width": 6.765,
        "sensor_height": 5.074,
    },
    "Apple iPhone 14": {
        "focal_plane_x_res": 14400.00,
        "focal_plane_y_res": 14400.00,
        "pixel_width": 4032,
        "pixel_height": 3024,
        "sensor_width": 6.765,
        "sensor_height": 5.074,
    },
    "Apple iPhone 13 Pro": {
        "focal_plane_x_res": 14400.00,
        "focal_plane_y_res": 14400.00,
        "pixel_width": 4032,
        "pixel_height": 3024,
        "sensor_width": 6.765,
        "sensor_height": 5.074,
    },
    "Apple iPhone 13": {
        "focal_plane_x_res": 14400.00,
        "focal_plane_y_res": 14400.00,
        "pixel_width": 4032,
        "pixel_height": 3024,
        "sensor_width": 6.765,
        "sensor_height": 5.074,
    },
    "HUAWEI P60 Pro": {
        "focal_plane_x_res": 14400.00,
        "focal_plane_y_res": 14400.00,
        "pixel_width": 4000,
        "pixel_height": 3000,
        "sensor_width": 6.4,
        "sensor_height": 4.8,
    },
    "HUAWEI Mate 60 Pro": {
        "focal_plane_x_res": 14400.00,
        "focal_plane_y_res": 14400.00,
        "pixel_width": 4000,
        "pixel_height": 3000,
        "sensor_width": 6.4,
        "sensor_height": 4.8,
    },
    "Samsung Galaxy S24 Ultra": {
        "focal_plane_x_res": 14400.00,
        "focal_plane_y_res": 14400.00,
        "pixel_width": 4000,
        "pixel_height": 3000,
        "sensor_width": 6.4,
        "sensor_height": 4.8,
    },
}


def lookup_camera_spec(make: str | None, model: str | None) -> CameraSpec | None:
    if not model:
        return None
    model = str(model).strip()
    make = str(make or "").strip()
    full = f"{make} {model}".strip()
    if full in CAMERA_SPECS:
        return CAMERA_SPECS[full]
    if model in CAMERA_SPECS:
        return CAMERA_SPECS[model]
    for key, spec in CAMERA_SPECS.items():
        if model in key or key in model:
            return spec
    return None

