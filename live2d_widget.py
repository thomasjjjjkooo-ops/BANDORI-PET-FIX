import math
import ctypes
import OpenGL.GL as gl
from PySide6.QtCore import Qt, QPoint, QElapsedTimer, Signal
from PySide6.QtGui import QMouseEvent, QCursor, QGuiApplication, QSurfaceFormat, QOpenGLContext, QMoveEvent, QResizeEvent
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from live2d_quality import LIVE2D_QUALITY_PROFILES, normalize_live2d_quality
from platform_patch import set_live2d_texture_quality

class Live2DWidget(QOpenGLWidget):
    model_loaded = Signal()

    @staticmethod
    def configure_default_surface_format():
        """Apply the OpenGL surface format Live2D requires.

        Must be called before QApplication is constructed so the global shared
        GL context (created when AA_ShareOpenGLContexts is set) gets the
        correct alpha/stencil buffers. Otherwise shader linking can fail with
        GL_INVALID_OPERATION on glGetAttribLocation.
        """
        fmt = QSurfaceFormat()
        fmt.setAlphaBufferSize(8)
        fmt.setSamples(0)
        fmt.setDepthBufferSize(0)
        fmt.setStencilBufferSize(8)
        fmt.setSwapInterval(1)
        fmt.setVersion(2, 1)
        fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile)
        QSurfaceFormat.setDefaultFormat(fmt)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = None
        self._live2d = None
        self._model_path = ""
        self._pending_model = ""
        self._quality_profile = "balanced"
        self._system_scale = 1.0
        
        self._dragging = False
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._window_drag_callback = None
        self._click_callback = None
        self._right_click_callback = None
        self._drag_locked = False
        self._initialized_gl = False
        
        self._fps = 120
        self._vsync = True
        self._static_render = False
        self._static_render_done = False
        self._clear_color = (0.0, 0.0, 0.0, 0.0)
        self._hit_alpha_threshold = 8
        self._hit_probe_offsets = (
            (0, 0),
            (-3, 0), (3, 0), (0, -3), (0, 3),
            (-6, 0), (6, 0), (0, -6), (0, 6),
        )
        self._hit_alpha_cache = {}
        self._hit_alpha_cache_ttl_ms = 100
        self._hit_pbo_ids = []
        self._hit_pbo_next = 0
        self._hit_pbo_pending = []
        self._hit_pbo_supported = None
        self._hit_pbo_size = 4
        self._hit_clock = QElapsedTimer()
        self._hit_clock.start()

        # 性能优化：缓存属性
        self._cache_w = 1
        self._cache_h = 1
        self._cache_w_half = 0.5
        self._cache_h_half = 0.5
        self._cache_global_x = 0
        self._cache_global_y = 0

        # 性能优化：鼠标脏标记
        self._last_cursor_x = -1
        self._last_cursor_y = -1
        self._head_track_counter = 0

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setAutoFillBackground(False)
        self.setMouseTracking(True)

    def _safe_make_current(self):
        if QOpenGLContext.currentContext() != self.context():
            self.makeCurrent()

    def set_fps(self, fps: int):
        self._fps = max(10, min(fps, 240))

    def set_vsync(self, enabled: bool):
        self._vsync = enabled
        if not self._initialized_gl:
            return
        self._safe_make_current()
        try:
            from OpenGL.WGL.EXT.swap_control import wglSwapIntervalEXT
            wglSwapIntervalEXT(1 if self._vsync else 0)
        except Exception:
            pass
        if not self._static_render:
            self.update()

    def set_render_quality(self, profile: str):
        profile = normalize_live2d_quality(profile)
        if profile == self._quality_profile:
            return
        self._quality_profile = profile
        if self._model_path:
            self._load_model_internal(self._model_path)
            self.update()

    def set_static_render(self, enabled: bool):
        self._static_render = enabled
        self._static_render_done = False
        self.update()

    def set_clear_color(self, r: float, g: float, b: float, a: float):
        self._clear_color = (r, g, b, a)
        self._static_render_done = False
        self.update()

    def set_live2d_module(self, module):
        self._live2d = module

    def set_window_drag_callback(self, cb):
        self._window_drag_callback = cb

    def set_click_callback(self, cb):
        self._click_callback = cb

    def set_right_click_callback(self, cb):
        self._right_click_callback = cb

    def set_drag_locked(self, locked: bool):
        self._drag_locked = locked

    def set_model_path(self, model_json_path: str):
        self._pending_model = model_json_path
        self._static_render_done = False
        self._clear_hit_framebuffer_cache()
        if self._initialized_gl:
            self._load_model_internal(model_json_path)
            self.update()

    def _load_model_internal(self, model_json_path: str):
        if not model_json_path or not self._live2d:
            return
        self._safe_make_current()
        try:
            set_live2d_texture_quality(self._quality_profile)
            disable_precision = LIVE2D_QUALITY_PROFILES[self._quality_profile]["disable_precision"]
            self._model = self._live2d.LAppModel()
            self._model.LoadModelJson(model_json_path, disable_precision=disable_precision)
            self._model.Resize(self._cache_w, self._cache_h)
            self._model_path = model_json_path
            self.model_loaded.emit()
        except Exception as e:
            print(f"Failed to load model: {e}")
            self._model = None
            self._model_path = ""

    @property
    def model(self):
        return self._model

    @property
    def model_path(self):
        return self._model_path

    def moveEvent(self, event: QMoveEvent):
        global_pos = self.mapToGlobal(QPoint(0, 0))
        self._cache_global_x = global_pos.x()
        self._cache_global_y = global_pos.y()
        super().moveEvent(event)

    def resizeEvent(self, event: QResizeEvent):
        size = event.size()
        self._cache_w = size.width()
        self._cache_h = size.height()
        self._cache_w_half = self._cache_w * 0.5
        self._cache_h_half = self._cache_h * 0.5
        super().resizeEvent(event)

    def initializeGL(self):
        if self._live2d:
            self._live2d.glInit()
        self._system_scale = QGuiApplication.primaryScreen().devicePixelRatio()
        self._initialized_gl = True
        
        self._cache_w = self.width()
        self._cache_h = self.height()
        self._cache_w_half = self._cache_w * 0.5
        self._cache_h_half = self._cache_h * 0.5
        pos = self.mapToGlobal(QPoint(0, 0))
        self._cache_global_x = pos.x()
        self._cache_global_y = pos.y()

        if self._pending_model:
            self._load_model_internal(self._pending_model)
        self._init_hit_pbos()
        self.update()

    def resizeGL(self, w: int, h: int):
        self._clear_hit_framebuffer_cache()
        gl.glViewport(0, 0, int(w * self._system_scale), int(h * self._system_scale))
        if self._model:
            self._model.Resize(w, h)

    def paintGL(self):
        if self._static_render and self._static_render_done:
            return

        model = self._model
        if not self._live2d or not model:
            return

        try:
            gl.glEnable(gl.GL_MULTISAMPLE)
        except Exception:
            pass
        
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDisable(gl.GL_DITHER)

        gl.glClearColor(*self._clear_color)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_STENCIL_BUFFER_BIT)

        gl.glEnable(gl.GL_BLEND)
        gl.glBlendEquationSeparate(gl.GL_FUNC_ADD, gl.GL_FUNC_ADD)

        self._live2d.clearBuffer()
        gl.glClearColor(*self._clear_color)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_STENCIL_BUFFER_BIT)
        self._update_head_tracking(model)
        model.Update()
        model.Draw()
        if self._static_render:
            self._static_render_done = True
        elif self.isVisible():
            self.update()

    def _update_head_tracking(self, model):
        if not self._dragging and model is not None:
            self._head_track_counter += 1
            if self._head_track_counter >= 3:
                self._head_track_counter = 0
                
                g_pos = QCursor.pos()
                gx, gy = g_pos.x(), g_pos.y()
                widget_pos = self.mapToGlobal(QPoint(0, 0))
                self._cache_global_x = widget_pos.x()
                self._cache_global_y = widget_pos.y()

                if gx != self._last_cursor_x or gy != self._last_cursor_y:
                    self._last_cursor_x = gx
                    self._last_cursor_y = gy
                    
                    cx = self._cache_global_x + self._cache_w_half
                    cy = self._cache_global_y + self._cache_h_half
                    dx = gx - cx
                    dy = gy - cy
                    
                    dist = math.hypot(dx, dy)
                    if dist > 0:
                        max_dist = 600.0
                        norm = 1.0 if dist > max_dist else dist / max_dist
                        factor = norm / dist
                        ux = dx * factor
                        uy = dy * factor
                        
                        local_x = cx + ux * max_dist - self._cache_global_x
                        local_y = cy + uy * max_dist - self._cache_global_y
                        model.Drag(local_x, local_y)

    def mousePressEvent(self, event: QMouseEvent):
        if self._drag_locked:
            super().mousePressEvent(event)
            return
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        x = event.scenePosition().x()
        y = event.scenePosition().y()
        if self._is_model_hit_at(x, y):
            self._dragging = True
            gpos = event.globalPosition()
            self._drag_start_x = gpos.x()
            self._drag_start_y = gpos.y()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.RightButton:
            x = event.scenePosition().x()
            y = event.scenePosition().y()
            if self._is_model_hit_at(x, y) and self._right_click_callback:
                gpos = event.globalPosition()
                self._right_click_callback(int(gpos.x()), int(gpos.y()))
            return
        if self._dragging:
            self._dragging = False
        elif self._click_callback:
            self._click_callback()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_locked:
            return
        if self._dragging and self._window_drag_callback:
            gpos = event.globalPosition()
            dx = int(gpos.x() - self._drag_start_x)
            dy = int(gpos.y() - self._drag_start_y)
            if dx != 0 or dy != 0:
                self._window_drag_callback(dx, dy)
                self._drag_start_x = gpos.x()
                self._drag_start_y = gpos.y()

    def alpha_at_global(self, global_pos: QPoint) -> int:
        local = self.mapFromGlobal(global_pos)
        if not self.rect().contains(local):
            return 0
        if not self._is_in_model_hit_area(local.x(), local.y()):
            return 0
        alpha = self._get_alpha_fast(local.x(), local.y())
        return 0 if alpha is None else alpha

    def is_model_hit_at_global(self, global_pos: QPoint) -> bool:
        local = self.mapFromGlobal(global_pos)
        if not self.rect().contains(local):
            return False
        return self._is_model_hit_at(local.x(), local.y())

    def model_hit_state_at_global(self, global_pos: QPoint):
        local = self.mapFromGlobal(global_pos)
        if not self.rect().contains(local):
            return False
        return self._hit_state_at(local.x(), local.y())

    def _is_model_hit_at(self, x: float, y: float) -> bool:
        if not self._model:
            return False
        state = self._hit_state_at(x, y)
        return state is True

    def _hit_state_at(self, x: float, y: float):
        if not self._model or not self._is_in_model_hit_area(x, y):
            return False
        alpha = self._alpha_near(x, y)
        if alpha is None:
            return None
        return alpha > self._hit_alpha_threshold

    def _is_in_model_hit_area(self, x: float, y: float) -> bool:
        return self._is_in_sdk_hit_area(x, y) or self._is_in_custom_hit_area(x, y)

    def _is_in_sdk_hit_area(self, x: float, y: float) -> bool:
        model = self._model
        try:
            setting = getattr(model, "modelSetting", None)
            if setting is None or setting.getHitAreaNum() <= 0:
                return False
            return model.HitTest("", x, y) is not None
        except Exception:
            return False

    def _is_in_custom_hit_area(self, x: float, y: float) -> bool:
        model = self._model
        try:
            setting = getattr(model, "modelSetting", None)
            config = getattr(setting, "json", {}) if setting is not None else {}
            areas = config.get("hit_areas_custom") or {}
            if not areas:
                return False
            sx, sy = model.matrixManager.screenToScene(x, y)
            for name, x_range in areas.items():
                if not name.endswith("_x") or not isinstance(x_range, list) or len(x_range) != 2:
                    continue
                y_range = areas.get(f"{name[:-2]}_y")
                if not isinstance(y_range, list) or len(y_range) != 2:
                    continue
                min_x, max_x = sorted((float(x_range[0]), float(x_range[1])))
                min_y, max_y = sorted((float(y_range[0]), float(y_range[1])))
                if min_x <= sx <= max_x and min_y <= sy <= max_y:
                    return True
        except Exception:
            return False
        return False

    def _clear_hit_framebuffer_cache(self):
        self._hit_alpha_cache.clear()
        self._clear_pending_hit_pbos()

    def _init_hit_pbos(self):
        if self._hit_pbo_supported is not None:
            return
        try:
            if not all(
                hasattr(gl, name)
                for name in (
                    "glGenBuffers", "glBindBuffer", "glBufferData", "glFenceSync",
                    "glClientWaitSync", "glDeleteSync", "glMapBuffer", "glUnmapBuffer",
                )
            ):
                raise RuntimeError("PBO sync functions are unavailable")
            self._hit_pbo_ids = []
            for _ in self._hit_probe_offsets:
                pbo = gl.glGenBuffers(1)
                if isinstance(pbo, (list, tuple)):
                    pbo = pbo[0]
                self._hit_pbo_ids.append(int(pbo))
                gl.glBindBuffer(gl.GL_PIXEL_PACK_BUFFER, int(pbo))
                gl.glBufferData(gl.GL_PIXEL_PACK_BUFFER, self._hit_pbo_size, None, gl.GL_STREAM_READ)
            gl.glBindBuffer(gl.GL_PIXEL_PACK_BUFFER, 0)
            self._hit_pbo_supported = True
        except Exception:
            try:
                gl.glBindBuffer(gl.GL_PIXEL_PACK_BUFFER, 0)
            except Exception:
                pass
            self._hit_pbo_ids = []
            self._hit_pbo_pending = []
            self._hit_pbo_supported = False

    def _clear_pending_hit_pbos(self):
        if not self._hit_pbo_pending:
            return
        pending = self._hit_pbo_pending
        self._hit_pbo_pending = []
        for request in pending:
            fence = request.get("fence")
            if fence:
                try:
                    gl.glDeleteSync(fence)
                except Exception:
                    pass

    def _process_hit_pbo_results(self):
        if not self._hit_pbo_supported or not self._hit_pbo_pending:
            return
        ready = []
        still_pending = []
        for request in self._hit_pbo_pending:
            fence = request.get("fence")
            try:
                status = gl.glClientWaitSync(fence, 0, 0)
            except Exception:
                still_pending.append(request)
                continue
            if status in (gl.GL_ALREADY_SIGNALED, gl.GL_CONDITION_SATISFIED):
                ready.append(request)
            else:
                still_pending.append(request)
        self._hit_pbo_pending = still_pending

        now = self._hit_clock.elapsed()
        for request in ready:
            fence = request.get("fence")
            try:
                gl.glBindBuffer(gl.GL_PIXEL_PACK_BUFFER, request["pbo"])
                ptr = gl.glMapBuffer(gl.GL_PIXEL_PACK_BUFFER, gl.GL_READ_ONLY)
                if ptr:
                    data = ctypes.string_at(ptr, self._hit_pbo_size)
                    self._hit_alpha_cache[request["key"]] = (data[3], now)
                    gl.glUnmapBuffer(gl.GL_PIXEL_PACK_BUFFER)
            except Exception:
                pass
            finally:
                try:
                    gl.glBindBuffer(gl.GL_PIXEL_PACK_BUFFER, 0)
                except Exception:
                    pass
                if fence:
                    try:
                        gl.glDeleteSync(fence)
                    except Exception:
                        pass
        if len(self._hit_alpha_cache) > 128:
            expired = [
                key for key, (_, timestamp) in self._hit_alpha_cache.items()
                if now - timestamp > self._hit_alpha_cache_ttl_ms
            ]
            for key in expired:
                self._hit_alpha_cache.pop(key, None)

    def _queue_hit_pbo_read(self, key: tuple[int, int], sx: int, sy: int):
        if not self._hit_pbo_supported or not self._hit_pbo_ids:
            return
        if any(request["key"] == key for request in self._hit_pbo_pending):
            return
        if len(self._hit_pbo_pending) >= len(self._hit_pbo_ids):
            return
        pending_pbos = {request["pbo"] for request in self._hit_pbo_pending}
        pbo = None
        for _ in self._hit_pbo_ids:
            candidate = self._hit_pbo_ids[self._hit_pbo_next]
            self._hit_pbo_next = (self._hit_pbo_next + 1) % len(self._hit_pbo_ids)
            if candidate not in pending_pbos:
                pbo = candidate
                break
        if pbo is None:
            return
        try:
            gl.glBindBuffer(gl.GL_PIXEL_PACK_BUFFER, pbo)
            gl.glReadPixels(sx, sy, 1, 1, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, ctypes.c_void_p(0))
            fence = gl.glFenceSync(gl.GL_SYNC_GPU_COMMANDS_COMPLETE, 0)
            if not fence:
                raise RuntimeError("PBO fence creation failed")
            self._hit_pbo_pending.append({"pbo": pbo, "key": key, "fence": fence})
        except Exception:
            self._hit_pbo_supported = False
            self._clear_pending_hit_pbos()
        finally:
            try:
                gl.glBindBuffer(gl.GL_PIXEL_PACK_BUFFER, 0)
            except Exception:
                pass

    def _alpha_near(self, x: float, y: float):
        alpha = 0
        known = False
        for dx, dy in self._hit_probe_offsets:
            px = x + dx
            py = y + dy
            sample_alpha = self._get_alpha_fast(px, py)
            if sample_alpha is None:
                continue
            known = True
            alpha = max(alpha, sample_alpha)
            if alpha > self._hit_alpha_threshold:
                break
        if not known:
            return None
        return alpha

    def _get_alpha_fast(self, x: float, y: float):
        if not self._initialized_gl or not self._model:
            return 0
        if x < 0 or y < 0 or x >= self._cache_w or y >= self._cache_h:
            return 0

        try:
            self._safe_make_current()
            self._init_hit_pbos()
            self._process_hit_pbo_results()
            sx = int(x * self._system_scale)
            sy = int((self._cache_h - 1 - y) * self._system_scale)
            key = (sx, sy)
            now = self._hit_clock.elapsed()
            cached = self._hit_alpha_cache.get(key)
            if cached and now - cached[1] <= self._hit_alpha_cache_ttl_ms:
                return cached[0]
            self._queue_hit_pbo_read(key, sx, sy)
            if cached:
                return cached[0]
            return None
        except Exception:
            return 0
