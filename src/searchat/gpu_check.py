"""GPU availability check and helpful warnings."""

import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


def check_nvidia_gpu() -> bool:
    """Check if NVIDIA GPU is available via nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            text=True,
            timeout=2
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def get_gpu_name() -> Optional[str]:
    """Get GPU name if available."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            return result.stdout.strip().split('\n')[0]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def check_and_warn_gpu():
    """
    Check if GPU is available but not being used.
    Show helpful warning with installation instructions.
    """
    try:
        import torch
    except ImportError:
        return

    # Only check if PyTorch is using CPU
    device = None
    try:
        if hasattr(torch, 'cuda') and torch.cuda.is_available():
            device = 'cuda'
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            device = 'mps'
    except Exception:
        pass

    # If already using GPU, we're good
    if device:
        logger.info(f"Using GPU acceleration: {device.upper()}")
        if device == 'cuda':
            try:
                gpu_name = torch.cuda.get_device_name(0)
                logger.info(f"GPU: {gpu_name}")
            except Exception:
                pass
        return

    # Check if GPU hardware exists but isn't being used
    gpu_available = check_nvidia_gpu()
    if not gpu_available:
        # No GPU hardware detected, CPU is appropriate
        return

    # GPU exists but PyTorch is CPU-only - show warning
    gpu_name = get_gpu_name()
    gpu_info = f" ({gpu_name})" if gpu_name else ""

    logger.warning("=" * 70)
    logger.warning(f"GPU DETECTED{gpu_info} BUT NOT IN USE")
    logger.warning("=" * 70)
    logger.warning("")
    logger.warning("Searchat is running on CPU, but an NVIDIA GPU is available.")
    logger.warning("To enable GPU acceleration:")
    logger.warning("")
    logger.warning("  1. Uninstall CPU-only PyTorch:")
    logger.warning("     pip uninstall torch torchvision")
    logger.warning("")
    logger.warning("  2. Install CUDA-enabled PyTorch:")
    logger.warning("     pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124")
    logger.warning("")
    logger.warning("  3. Restart searchat")
    logger.warning("")
    logger.warning("=" * 70)
