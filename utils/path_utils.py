"""Path security utilities for ESP-IDF MCP.

Provides safe path resolution to prevent directory traversal attacks.
"""

import os
from pathlib import Path


def resolve_safe_path(base: Path, user_path: str) -> Path:
    """Safely resolve a user-provided path relative to a base directory.

    This function prevents path traversal attacks through multiple layers:
    - Null byte rejection
    - Absolute path handling
    - Early traversal attempt detection
    - Strict prefix matching
    - Component-level validation

    Args:
        base: The base directory that acts as a jail/root.
        user_path: User-provided path (can be relative or absolute).

    Returns:
        Resolved absolute path that is guaranteed to be within base.

    Raises:
        ValueError: If the path attempts to traverse outside base directory.
        TypeError: If user_path is not a string.

    Examples:
        >>> base = Path("/safe/project")
        >>> resolve_safe_path(base, "output.bin")
        Path('/safe/project/output.bin')
        >>> resolve_safe_path(base, "../etc/passwd")
        ValueError: Path traversal attempt detected

    Security:
        - Rejects null bytes immediately
        - Validates absolute paths are within base
        - Normalizes path separators
        - Rejects obvious traversal attempts early
        - Uses strict prefix matching with os.sep
        - Validates each path component against symlinks
    """
    if not isinstance(user_path, str):
        raise TypeError(f"user_path must be a string, got {type(user_path).__name__}")

    # Reject null bytes immediately (security: prevents string truncation attacks)
    if "\x00" in user_path:
        raise ValueError(f"Null byte detected in path: {user_path}")

    # Resolve base to absolute path
    base_resolved = base.resolve()
    base_str = str(base_resolved)

    # Check for absolute paths BEFORE any processing
    # Even absolute paths must be within the base directory
    if os.path.isabs(user_path):
        resolved = Path(user_path).resolve()
        resolved_str = str(resolved)
        # Strict check: absolute path must be exactly base or within base
        if resolved_str == base_str:
            return resolved
        if not resolved_str.startswith(base_str + os.sep):
            raise ValueError(
                f"Absolute path outside base directory: {user_path} "
                f"(resolved to {resolved_str}, outside base {base_str})"
            )
        return resolved

    # Normalize path separators and remove redundant components
    normalized = user_path.replace("\\", "/")

    # Reject obvious traversal attempts early (before path resolution)
    if "../" in normalized or "..\\" in normalized:
        raise ValueError(
            f"Path traversal attempt detected: {user_path} (contains parent directory references)"
        )

    # Resolve the path
    resolved = (base_resolved / normalized).resolve()
    resolved_str = str(resolved)

    # Strict prefix check - must be exactly within base
    # Using os.sep ensures correct separator for platform
    if resolved_str == base_str:
        return resolved  # Exactly the base directory

    if not resolved_str.startswith(base_str + os.sep):
        raise ValueError(
            f"Path traversal attempt detected: {user_path} "
            f"(resolved to {resolved_str}, outside base {base_str})"
        )

    # Additional check: ensure no symlinks escape base
    # This validates the actual path components rather than just string prefix
    try:
        # Get relative path from base to resolved
        relative = resolved.relative_to(base_resolved)
        # Check if any component is ".." (symlink escape)
        if ".." in relative.parts:
            raise ValueError(
                f"Path traversal via symlink detected: {user_path} "
                f"(relative path contains parent references)"
            )
    except ValueError as e:
        # relative_to failed means path is outside base
        raise ValueError(
            f"Path outside base directory: {user_path} "
            f"(resolved to {resolved_str}, outside base {base_str})"
        ) from e

    return resolved


def validate_filename(filename: str) -> bool:
    r"""Validate that a filename contains only safe characters.

    Args:
        filename: The filename to validate.

    Returns:
        True if filename is safe, False otherwise.

    Security:
        - Rejects empty filenames
        - Rejects path separators (/, \\)
        - Rejects control characters
        - Rejects special shell characters that might be problematic
    """
    if not filename:
        return False

    # Reject path separators
    if "/" in filename or "\\" in filename:
        return False

    # Reject control characters
    if any(ord(c) < 32 for c in filename):
        return False

    # Allow alphanumeric, underscore, hyphen, dot, and some special chars
    # This is permissive but reasonable for filenames
    allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-+@")
    return all(c in allowed_chars for c in filename)


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename by replacing unsafe characters.

    Args:
        filename: The filename to sanitize.

    Returns:
        Sanitized filename safe for filesystem operations.

    Note:
        This function replaces unsafe characters with underscores.
        For security validation, use validate_filename() instead.
    """
    if not filename:
        return "unnamed"

    # Replace path separators and control chars
    result = filename.replace("/", "_").replace("\\", "_")
    result = "".join(c if ord(c) >= 32 else "_" for c in result)

    # Replace other potentially problematic characters
    for char in ' <>:"|?*':
        result = result.replace(char, "_")

    return result


__all__ = [
    "resolve_safe_path",
    "validate_filename",
    "sanitize_filename",
]
