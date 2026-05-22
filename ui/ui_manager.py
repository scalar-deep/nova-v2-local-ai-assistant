"""
PyGame-based UI manager for Wayland display.
"""

import os
import pygame
from enum import Enum
from typing import Optional, Tuple, Dict
from pathlib import Path
from threading import Thread, Lock, Event
import time
import math


class UIState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    ERROR = "error"


class UIManager:
    """Manages the animated face display."""
    
    def __init__(
        self,
        width: int = 800,
        height: int = 480,
        assets_path: str = "/home/nova-v2/nova-v2/assets/face",
        fps: int = 30,
        use_framebuffer: bool = True
    ):
        self.width = width
        self.height = height
        self.assets_path = Path(assets_path)
        self.fps = fps
        self.use_framebuffer = use_framebuffer
        
        self._state = UIState.IDLE
        self._state_lock = Lock()
        self._running = False
        self._ready = Event()
        self._thread: Optional[Thread] = None
        
        # Audio amplitude for reactive animations
        self._audio_amplitude = 0.0
        
        # Animation frame counters
        self._frame_count = 0
        
        # Colors
        self.bg_color = (10, 10, 20)  # Dark blue-black
        self.accent_color = (0, 200, 255)  # Cyan
        
        # Face assets (populated in render thread)
        self._faces: Dict[str, pygame.Surface] = {}
        self._face_rects: Dict[str, pygame.Rect] = {}

        # Temporary image display, used for showing captured photos
        self._temp_image_path: Optional[str] = None
        self._temp_image_until: float = 0.0
        self._temp_image_lock = Lock()
    
    def set_state(self, state: UIState):
        """Set the current UI state (thread-safe)."""
        with self._state_lock:
            self._state = state
    
    def set_audio_amplitude(self, amplitude: float):
        """Set audio amplitude for reactive animations (0.0 - 1.0)."""
        self._audio_amplitude = max(0.0, min(1.0, amplitude))

    def show_image(self, image_path: str, duration: float = 3.0):
        """Temporarily show an image on screen for a fixed duration."""
        with self._temp_image_lock:
            self._temp_image_path = str(image_path)
            self._temp_image_until = time.time() + float(duration)
        print(f"[ui] showing image for {duration:.1f}s: {image_path}")
    
    def start(self):
        """Start the UI render loop in a background thread."""
        self._running = True
        self._thread = Thread(target=self._render_loop, daemon=True)
        self._thread.start()
        # Wait for pygame to initialize in the render thread
        self._ready.wait(timeout=5.0)
    
    def stop(self):
        """Stop the UI (pygame cleanup happens in render thread)."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
    
    def _render_loop(self):
        """Main render loop — owns the pygame display context."""
        # --- Initialize pygame in THIS thread (required for EGL/Wayland) ---
        os.environ.setdefault("XDG_RUNTIME_DIR", "/run/user/1000")
        os.environ.setdefault("WAYLAND_DISPLAY", "wayland-0")
        os.environ["SDL_VIDEODRIVER"] = "wayland"
        
        try:
            pygame.display.init()
            pygame.font.init()
            screen = pygame.display.set_mode(
                (self.width, self.height),
                pygame.FULLSCREEN | pygame.HWSURFACE | pygame.DOUBLEBUF
            )
            pygame.display.set_caption("Nova-V2")
            print(f"    Display driver: wayland")
        except pygame.error as e:
            print(f"    Wayland display failed: {e}, UI disabled")
            self._ready.set()
            return
        
        try:
            pygame.mouse.set_visible(False)
        except:
            pass
        
        # Load fonts
        font_small = pygame.font.Font(None, 24)
        font_medium = pygame.font.Font(None, 36)
        
        # Load PNG face assets
        self._load_faces()
        
        # Signal that we're ready
        self._ready.set()
        
        clock = pygame.time.Clock()
        
        while self._running:
            # Handle PyGame events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False
                    break
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self._running = False
                        break
            
            if not self._running:
                break
            
            # Clear screen
            screen.fill(self.bg_color)

            # Temporary captured-photo display takes priority over face states.
            if self._render_temp_image_if_active(screen):
                try:
                    pygame.display.flip()
                except pygame.error:
                    break

                self._frame_count += 1
                clock.tick(self.fps)
                continue
            
            # Get current state
            with self._state_lock:
                state = self._state
            
            # Render current state
            if state == UIState.IDLE:
                self._render_idle(screen)
            elif state == UIState.LISTENING:
                self._render_listening(screen)
            elif state == UIState.THINKING:
                self._render_thinking(screen, font_medium)
            elif state == UIState.SPEAKING:
                self._render_speaking(screen)
            elif state == UIState.ERROR:
                self._render_error(screen, font_medium)
            
            # Status text
            status_text = f"Status: {state.value.upper()}"
            text_surface = font_small.render(status_text, True, (100, 100, 100))
            text_rect = text_surface.get_rect(center=(self.width // 2, self.height - 20))
            screen.blit(text_surface, text_rect)
            
            # Flip
            try:
                pygame.display.flip()
            except pygame.error:
                break
            
            self._frame_count += 1
            clock.tick(self.fps)
        
        # Cleanup in this thread
        pygame.display.quit()
        pygame.font.quit()
    
    def _render_temp_image_if_active(self, screen) -> bool:
        """Render a temporary image if one is active. Returns True if rendered."""
        with self._temp_image_lock:
            image_path = self._temp_image_path
            active = image_path and time.time() < self._temp_image_until

            if not active:
                self._temp_image_path = None
                self._temp_image_until = 0.0
                return False

        try:
            image = pygame.image.load(image_path).convert()
            img_w, img_h = image.get_size()

            if img_w <= 0 or img_h <= 0:
                return False

            scale = min(self.width / img_w, self.height / img_h)
            new_w = max(1, int(img_w * scale))
            new_h = max(1, int(img_h * scale))

            image = pygame.transform.smoothscale(image, (new_w, new_h))
            rect = image.get_rect(center=(self.width // 2, self.height // 2))

            screen.fill((0, 0, 0))
            screen.blit(image, rect)
            return True

        except Exception as e:
            print(f"[ui] image display error: {e}")
            with self._temp_image_lock:
                self._temp_image_path = None
                self._temp_image_until = 0.0
            return False

    def _load_faces(self):
        """Load PNG face assets, scale to fit display, and center."""
        target_height = int(self.height * 0.8)
        
        for png_file in self.assets_path.glob("*.png"):
            stem = png_file.stem
            try:
                surface = pygame.image.load(str(png_file)).convert_alpha()
                orig_w, orig_h = surface.get_size()
                scale = target_height / orig_h
                new_w = int(orig_w * scale)
                surface = pygame.transform.smoothscale(surface, (new_w, target_height))
                rect = surface.get_rect(center=(self.width // 2, self.height // 2))
                self._faces[stem] = surface
                self._face_rects[stem] = rect
                print(f"    Loaded face: {stem} ({new_w}x{target_height})")
            except Exception as e:
                print(f"    Warning: Failed to load {png_file.name}: {e}")
        
        if self._faces:
            print(f"  Loaded {len(self._faces)} face assets")
        else:
            print("  No face assets found, using procedural fallback")
    
    def _blit_face(self, screen, name: str) -> bool:
        """Blit a named face to screen. Returns True if successful."""
        if name in self._faces:
            screen.blit(self._faces[name], self._face_rects[name])
            return True
        return False
    
    # --- Render methods ---
    
    def _render_idle(self, screen):
        blink_interval = self.fps * 3
        blink_duration = self.fps // 3
        cycle_pos = self._frame_count % blink_interval
        is_blinking = cycle_pos < blink_duration
        
        if is_blinking and "winking" in self._faces:
            self._blit_face(screen, "winking")
        elif not self._blit_face(screen, "happy"):
            self._draw_procedural_face(screen, is_blinking, mouth_openness=0.0)
    
    def _render_listening(self, screen):
        if not self._blit_face(screen, "happy_eye_glistening"):
            self._draw_procedural_face(screen, False, mouth_openness=0.0, eye_scale=1.3)
    
    def _render_thinking(self, screen, font):
        if not self._blit_face(screen, "thinking"):
            self._draw_procedural_face(screen, False, mouth_openness=0.0)
        
        # Spinning dots overlay
        cx, cy = self.width // 2, self.height - 60
        num_dots = 8
        angle_offset = self._frame_count * 5
        for i in range(num_dots):
            angle = math.radians(angle_offset + i * (360 / num_dots))
            x = cx + int(25 * math.cos(angle))
            y = cy + int(25 * math.sin(angle))
            dot_size = max(2, 6 - int((i / num_dots) * 3))
            pygame.draw.circle(screen, self.accent_color, (x, y), dot_size)
    
    def _render_speaking(self, screen):
        if not self._blit_face(screen, "happy"):
            mouth = self._audio_amplitude * 0.8 + 0.1
            self._draw_procedural_face(screen, False, mouth_openness=mouth)
    
    def _render_error(self, screen, font):
        if not self._blit_face(screen, "irritated"):
            self._draw_procedural_face(screen, True, mouth_openness=0.3)
        
        overlay = pygame.Surface((self.width, self.height))
        overlay.fill((255, 0, 0))
        overlay.set_alpha(30)
        screen.blit(overlay, (0, 0))
        
        text = font.render("Error", True, (255, 100, 100))
        screen.blit(text, text.get_rect(center=(self.width // 2, self.height // 2 + 150)))
    
    def _draw_procedural_face(self, screen, eyes_closed=False, mouth_openness=0.0, eye_scale=1.0):
        """Fallback procedural face when PNGs aren't available."""
        cx = self.width // 2
        cy = self.height // 2 - 30
        ew = int(80 * eye_scale)
        eh = int(50 * eye_scale) if not eyes_closed else 8
        sp = 120
        ey = cy - 30
        
        pygame.draw.ellipse(screen, self.accent_color, (cx - sp - ew // 2, ey - eh // 2, ew, eh), 3)
        pygame.draw.ellipse(screen, self.accent_color, (cx + sp - ew // 2, ey - eh // 2, ew, eh), 3)
        
        if not eyes_closed:
            ps = int(15 * eye_scale)
            pygame.draw.circle(screen, self.accent_color, (cx - sp, ey), ps)
            pygame.draw.circle(screen, self.accent_color, (cx + sp, ey), ps)
        
        my = cy + 60
        mw = 100
        mh = int(20 + mouth_openness * 40)
        if mouth_openness > 0.1:
            pygame.draw.ellipse(screen, self.accent_color, (cx - mw // 2, my - mh // 2, mw, mh), 3)
        else:
            pygame.draw.line(screen, self.accent_color, (cx - mw // 2, my), (cx + mw // 2, my), 3)
