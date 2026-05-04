import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")


class PatchedPlatformManager:
    """Wraps PlatformManager to fix motion/expression file paths.

    The model.json files reference motion files with paths like
    ``../_mtn_emp/{char}/motion.mtn`` but ``_mtn_emp`` is at the models
    root, not inside each character directory.
    """

    def __init__(self, original_pm):
        self._original = original_pm

    def loadBytes(self, path) -> bytes:
        if not os.path.exists(path):
            fixed = self._fix_mtn_path(path)
            if fixed:
                path = fixed
        return self._original.loadBytes(path)

    def loadLive2DModel(self, path, version, disable_precision):
        return self._original.loadLive2DModel(path, version, disable_precision)

    def loadTexture(self, live2DModel, no, path):
        return self._original.loadTexture(live2DModel, no, path)

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
