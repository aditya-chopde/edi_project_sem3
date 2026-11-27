import logging

import torch


logger = logging.getLogger(__name__)
_ACCELERATOR_TYPES = ("cuda", "xpu", "mps")


def _is_available(device_type: str) -> bool:
    if device_type == "cuda":
        return torch.cuda.is_available()
    if device_type == "xpu":
        xpu = getattr(torch, "xpu", None)
        return xpu is not None and xpu.is_available()
    if device_type == "mps":
        mps = getattr(torch.backends, "mps", None)
        return mps is not None and mps.is_available()
    return device_type == "cpu"


def resolve_device(preference: str, purpose: str) -> str:
    requested = preference.strip().lower()
    if requested == "auto":
        for device_type in _ACCELERATOR_TYPES:
            if _is_available(device_type):
                logger.info("Using %s for %s", device_type, purpose)
                return device_type
        logger.info(
            "No supported GPU runtime is available for %s; using CPU", purpose
        )
        return "cpu"

    device_parts = requested.split(":")
    device_type = device_parts[0]
    if (
        device_type not in (*_ACCELERATOR_TYPES, "cpu")
        or len(device_parts) > 2
        or (len(device_parts) == 2 and not device_parts[1].isdigit())
        or (device_type == "mps" and len(device_parts) != 1)
        or (device_type == "cpu" and len(device_parts) != 1)
    ):
        raise ValueError(
            f"Unsupported {purpose} device '{preference}'. "
            "Use auto, cpu, cuda[:index], xpu[:index], or mps."
        )

    if not _is_available(device_type):
        raise RuntimeError(
            f"{purpose.capitalize()} device '{preference}' was explicitly "
            "configured but is unavailable. Install its supported PyTorch "
            "runtime or set the device to 'auto' or 'cpu'."
        )
    if len(device_parts) == 2:
        device_index = int(device_parts[1])
        device_count = getattr(torch, device_type).device_count()
        if device_index >= device_count:
            raise RuntimeError(
                f"{purpose.capitalize()} device '{preference}' is unavailable; "
                f"only {device_count} {device_type} device(s) are available."
            )

    logger.info("Using %s for %s", requested, purpose)
    return requested
