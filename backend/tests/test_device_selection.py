import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services import device


def _fake_torch(*, cuda=False, xpu=False, mps=False, cuda_count=1, xpu_count=1):
    return SimpleNamespace(
        cuda=SimpleNamespace(
            is_available=lambda: cuda,
            device_count=lambda: cuda_count,
        ),
        xpu=SimpleNamespace(
            is_available=lambda: xpu,
            device_count=lambda: xpu_count,
        ),
        backends=SimpleNamespace(
            mps=SimpleNamespace(is_available=lambda: mps),
        ),
    )


class DeviceSelectionTests(unittest.TestCase):
    def test_auto_prefers_cuda_then_xpu_then_mps(self):
        for availability, expected in (
            ({"cuda": True, "xpu": True, "mps": True}, "cuda"),
            ({"xpu": True, "mps": True}, "xpu"),
            ({"mps": True}, "mps"),
        ):
            with self.subTest(expected=expected), patch.object(
                device, "torch", _fake_torch(**availability)
            ):
                self.assertEqual(device.resolve_device("auto", "embeddings"), expected)

    def test_auto_falls_back_to_cpu_when_no_accelerator_is_available(self):
        with patch.object(device, "torch", _fake_torch()):
            self.assertEqual(device.resolve_device("auto", "reranking"), "cpu")

    def test_explicit_cpu_and_accelerator_are_respected(self):
        with patch.object(device, "torch", _fake_torch(xpu=True)):
            self.assertEqual(device.resolve_device("cpu", "embeddings"), "cpu")
            self.assertEqual(device.resolve_device("xpu:0", "embeddings"), "xpu:0")

    def test_explicit_unavailable_accelerator_fails_clearly(self):
        with patch.object(device, "torch", _fake_torch()):
            with self.assertRaisesRegex(RuntimeError, "explicitly configured"):
                device.resolve_device("xpu", "embeddings")

    def test_invalid_or_missing_device_index_is_rejected(self):
        with patch.object(device, "torch", _fake_torch(cuda=True, cuda_count=1)):
            with self.assertRaisesRegex(RuntimeError, "only 1 cuda device"):
                device.resolve_device("cuda:1", "embeddings")
            with self.assertRaisesRegex(ValueError, "Unsupported"):
                device.resolve_device("gpu", "embeddings")


if __name__ == "__main__":
    unittest.main()
