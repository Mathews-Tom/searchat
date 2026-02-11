"""Tests for searchat.gpu_check."""
from __future__ import annotations

import logging
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from searchat.gpu_check import check_nvidia_gpu, get_gpu_name, check_and_warn_gpu


class TestCheckNvidiaGpu:
    """Tests for check_nvidia_gpu."""

    @patch("subprocess.run")
    def test_gpu_present(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        assert check_nvidia_gpu() is True

    @patch("subprocess.run")
    def test_gpu_absent_nonzero_exit(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        assert check_nvidia_gpu() is False

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_nvidia_smi_not_found(self, mock_run):
        assert check_nvidia_gpu() is False

    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired("nvidia-smi", 2))
    def test_nvidia_smi_timeout(self, mock_run):
        assert check_nvidia_gpu() is False


class TestGetGpuName:
    """Tests for get_gpu_name."""

    @patch("subprocess.run")
    def test_returns_gpu_name(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="NVIDIA GeForce RTX 3090\n",
        )
        assert get_gpu_name() == "NVIDIA GeForce RTX 3090"

    @patch("subprocess.run")
    def test_returns_none_on_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        assert get_gpu_name() is None

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_returns_none_when_not_found(self, mock_run):
        assert get_gpu_name() is None

    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired("nvidia-smi", 2))
    def test_returns_none_on_timeout(self, mock_run):
        assert get_gpu_name() is None


class TestCheckAndWarnGpu:
    """Tests for check_and_warn_gpu."""

    @patch.dict("sys.modules", {"torch": None})
    def test_returns_early_when_torch_missing(self):
        """No torch → import fails → returns without action."""
        # torch is set to None in sys.modules → ImportError on import
        check_and_warn_gpu()

    def test_returns_early_when_torch_import_error(self, monkeypatch):
        """ImportError for torch exits silently."""
        import sys

        # Remove torch if present, then ensure import raises
        original = sys.modules.get("torch")
        sys.modules["torch"] = None  # Causes ImportError on `import torch`
        try:
            check_and_warn_gpu()
        finally:
            if original is not None:
                sys.modules["torch"] = original
            else:
                sys.modules.pop("torch", None)

    def test_cuda_available_logs_info(self, caplog, monkeypatch):
        """When CUDA is available, log GPU info and return."""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.get_device_name.return_value = "RTX 3090"
        mock_torch.backends.mps.is_available.return_value = False

        import sys
        original = sys.modules.get("torch")
        sys.modules["torch"] = mock_torch
        try:
            with caplog.at_level(logging.INFO):
                check_and_warn_gpu()
            assert "CUDA" in caplog.text
        finally:
            if original is not None:
                sys.modules["torch"] = original
            else:
                sys.modules.pop("torch", None)

    def test_mps_available_logs_info(self, caplog, monkeypatch):
        """When MPS is available, log GPU info and return."""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_torch.backends.mps.is_available.return_value = True

        import sys
        original = sys.modules.get("torch")
        sys.modules["torch"] = mock_torch
        try:
            with caplog.at_level(logging.INFO):
                check_and_warn_gpu()
            assert "MPS" in caplog.text
        finally:
            if original is not None:
                sys.modules["torch"] = original
            else:
                sys.modules.pop("torch", None)

    @patch("searchat.gpu_check.check_nvidia_gpu", return_value=False)
    def test_no_gpu_hardware_returns_silently(self, mock_check, caplog, monkeypatch):
        """No GPU hardware, CPU torch → no warning."""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_torch.backends.mps.is_available.return_value = False

        import sys
        original = sys.modules.get("torch")
        sys.modules["torch"] = mock_torch
        try:
            with caplog.at_level(logging.WARNING):
                check_and_warn_gpu()
            assert "GPU DETECTED" not in caplog.text
        finally:
            if original is not None:
                sys.modules["torch"] = original
            else:
                sys.modules.pop("torch", None)

    def test_cuda_is_available_exception(self, caplog, monkeypatch):
        """Exception during cuda.is_available() is caught silently."""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.side_effect = RuntimeError("CUDA error")
        mock_torch.backends.mps.is_available.side_effect = RuntimeError("MPS error")

        import sys
        original = sys.modules.get("torch")
        sys.modules["torch"] = mock_torch
        try:
            with patch("searchat.gpu_check.check_nvidia_gpu", return_value=False):
                check_and_warn_gpu()
        finally:
            if original is not None:
                sys.modules["torch"] = original
            else:
                sys.modules.pop("torch", None)

    def test_get_device_name_exception(self, caplog, monkeypatch):
        """Exception during get_device_name() is caught silently."""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.get_device_name.side_effect = RuntimeError("device error")
        mock_torch.backends.mps.is_available.return_value = False

        import sys
        original = sys.modules.get("torch")
        sys.modules["torch"] = mock_torch
        try:
            with caplog.at_level(logging.INFO):
                check_and_warn_gpu()
            assert "CUDA" in caplog.text
        finally:
            if original is not None:
                sys.modules["torch"] = original
            else:
                sys.modules.pop("torch", None)

    @patch("searchat.gpu_check.get_gpu_name", return_value="RTX 4090")
    @patch("searchat.gpu_check.check_nvidia_gpu", return_value=True)
    def test_gpu_detected_but_cpu_torch_warns(self, mock_check, mock_name, caplog, monkeypatch):
        """GPU hardware exists but torch is CPU-only → show warning."""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_torch.backends.mps.is_available.return_value = False

        import sys
        original = sys.modules.get("torch")
        sys.modules["torch"] = mock_torch
        try:
            with caplog.at_level(logging.WARNING):
                check_and_warn_gpu()
            assert "GPU DETECTED" in caplog.text
            assert "RTX 4090" in caplog.text
        finally:
            if original is not None:
                sys.modules["torch"] = original
            else:
                sys.modules.pop("torch", None)
