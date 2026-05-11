import os
import io

import OpenGL.GL as gl
from PIL import Image
from process_utils import app_base_dir
from zst_model_archive import is_virtual_path, load_virtual_bytes

BASE_DIR = str(app_base_dir())
MODELS_DIR = os.path.join(BASE_DIR, "models")
_LIVE2D_TEXTURE_QUALITY = "balanced"
_TEXTURE_MAX_ANISOTROPY_EXT = 0x84FE
_MAX_TEXTURE_MAX_ANISOTROPY_EXT = 0x84FF
_TEXTURE_DATA_CACHE = {}


def set_live2d_texture_quality(profile: str):
    global _LIVE2D_TEXTURE_QUALITY
    if profile in {"performance", "balanced", "quality", "ultra"}:
        _LIVE2D_TEXTURE_QUALITY = profile
    else:
        _LIVE2D_TEXTURE_QUALITY = "balanced"


def _texture_options() -> tuple[int, int, bool, float]:
    if _LIVE2D_TEXTURE_QUALITY == "performance":
        return gl.GL_NEAREST, gl.GL_NEAREST, False, 1.0
    if _LIVE2D_TEXTURE_QUALITY == "quality":
        return gl.GL_LINEAR_MIPMAP_LINEAR, gl.GL_LINEAR, True, 1.0
    if _LIVE2D_TEXTURE_QUALITY == "ultra":
        return gl.GL_LINEAR_MIPMAP_LINEAR, gl.GL_LINEAR, True, 4.0
    return gl.GL_LINEAR, gl.GL_LINEAR, False, 1.0


def _apply_anisotropy(level: float):
    if level <= 1.0:
        return
    try:
        max_level = float(gl.glGetFloatv(_MAX_TEXTURE_MAX_ANISOTROPY_EXT))
        gl.glTexParameterf(
            gl.GL_TEXTURE_2D,
            _TEXTURE_MAX_ANISOTROPY_EXT,
            min(level, max_level),
        )
    except Exception:
        pass


def _bleed_transparent_edges(image: Image.Image, passes: int = 2) -> Image.Image:
    pixels = image.load()
    width, height = image.size

    for _ in range(passes):
        updates = []
        for y in range(height):
            for x in range(width):
                alpha = pixels[x, y][3]
                if alpha >= 255:
                    continue

                red = green = blue = count = 0
                for nx, ny in (
                    (x - 1, y),
                    (x + 1, y),
                    (x, y - 1),
                    (x, y + 1),
                ):
                    if nx < 0 or ny < 0 or nx >= width or ny >= height:
                        continue
                    nr, ng, nb, na = pixels[nx, ny]
                    if na <= alpha:
                        continue
                    red += nr
                    green += ng
                    blue += nb
                    count += 1

                if count:
                    updates.append((x, y, red // count, green // count, blue // count, alpha))

        if not updates:
            break
        for x, y, red, green, blue, alpha in updates:
            pixels[x, y] = (red, green, blue, alpha)

    return image


class PatchedPlatformManager:
    """Wraps PlatformManager to fix motion/expression file paths.

    The model.json files reference motion files with paths like
    ``../_mtn_emp/{char}/motion.mtn`` but ``_mtn_emp`` is at the models
    root, not inside each character directory.
    """

    def __init__(self, original_pm):
        self._original = original_pm

    def loadBytes(self, path) -> bytes:
        if is_virtual_path(path):
            try:
                return load_virtual_bytes(path)
            except KeyError:
                fixed = self._fix_mtn_path(path)
                if fixed:
                    return self._original.loadBytes(fixed)
                raise
        if not os.path.exists(path):
            fixed = self._fix_mtn_path(path)
            if fixed:
                path = fixed
        return self._original.loadBytes(path)

    def loadLive2DModel(self, path, version, disable_precision):
        if is_virtual_path(path):
            from live2d.v2.core import Live2DModelOpenGL
            return Live2DModelOpenGL.loadModel(load_virtual_bytes(path), version, disable_precision)
        return self._original.loadLive2DModel(path, version, disable_precision)

    def loadTexture(self, live2DModel, no, path):
        cache_key = self._texture_cache_key(path)
        cached = _TEXTURE_DATA_CACHE.get(cache_key)
        if cached is None:
            if is_virtual_path(path):
                source_image = Image.open(io.BytesIO(load_virtual_bytes(path)))
            else:
                source_image = Image.open(path)
            image = source_image
            try:
                if image.mode != "RGBA":
                    image = image.convert("RGBA")
                elif _LIVE2D_TEXTURE_QUALITY in {"quality", "ultra"}:
                    image = image.copy()
                if _LIVE2D_TEXTURE_QUALITY in {"quality", "ultra"}:
                    image = _bleed_transparent_edges(image)
                width, height = image.size
                cached = (width, height, image.tobytes())
                _TEXTURE_DATA_CACHE[cache_key] = cached
            finally:
                if image is not source_image:
                    image.close()
                source_image.close()
        width, height, image_data = cached
        min_filter, mag_filter, use_mipmap, anisotropy = _texture_options()

        texture = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
        gl.glTexImage2D(
            gl.GL_TEXTURE_2D,
            0,
            gl.GL_RGBA,
            width,
            height,
            0,
            gl.GL_RGBA,
            gl.GL_UNSIGNED_BYTE,
            image_data,
        )
        if use_mipmap:
            try:
                gl.glGenerateMipmap(gl.GL_TEXTURE_2D)
            except Exception:
                min_filter = gl.GL_LINEAR
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, min_filter)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, mag_filter)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
        _apply_anisotropy(anisotropy)
        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        live2DModel.setTexture(no, texture)

    @staticmethod
    def _texture_cache_key(path: str):
        if is_virtual_path(path):
            return (_LIVE2D_TEXTURE_QUALITY, path)
        try:
            stat = os.stat(path)
            return (_LIVE2D_TEXTURE_QUALITY, os.path.abspath(path), stat.st_mtime_ns, stat.st_size)
        except OSError:
            return (_LIVE2D_TEXTURE_QUALITY, os.path.abspath(path))

    def jsonParseFromBytes(self, path):
        return self._original.jsonParseFromBytes(path)

    @staticmethod
    def _fix_mtn_path(path: str) -> str:
        norm = os.path.normpath(os.path.abspath(path))
        if os.path.exists(norm):
            return norm

        basename = os.path.basename(path)
        mtn_emp_dir = os.path.join(MODELS_DIR, "_mtn_emp")
        if not os.path.isdir(mtn_emp_dir):
            return ""

        for root, _dirs, files in os.walk(mtn_emp_dir):
            if basename in files:
                return os.path.join(root, basename)

        return ""
