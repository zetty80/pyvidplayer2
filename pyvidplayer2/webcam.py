import cv2
import pygame
import time
import numpy as np
from typing import Callable, Union, Tuple
from .post_processing import PostProcessing
from .error import *


class Webcam:
    """
    Refer to "https://github.com/anrayliu/pyvidplayer2/blob/main/documentation.md" for detailed documentation.
    """

    def __init__(self, post_process: Callable[[np.ndarray], np.ndarray] = PostProcessing.none,
                 interp: Union[str, int] = "linear", fps: int = 30, cam_id: int = 0,
                 capture_size: Tuple[int, int] = (0, 0)) -> None:
        self._vid = cv2.VideoCapture(cam_id)

        if not self._vid.isOpened():
            raise WebcamNotFoundError("Failed to find a webcam.")

        self.original_size = (0, 0)
        if capture_size == (0, 0):
            self.original_size = (
            int(self._vid.get(cv2.CAP_PROP_FRAME_WIDTH)), int(self._vid.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        else:
            self.resize_capture(capture_size)

        self.current_size = self.original_size
        self.aspect_ratio = self.original_size[0] / self.original_size[1]

        self.frame_data = None
        self.frame_surf = None

        self.active = False
        self.closed = False

        self.post_func = post_process
        self.interp = interp
        self.fps = fps
        self.cam_id = cam_id

        self._frames = 0
        self._last_tick = 0

        self.set_interp(self.interp)

        self.play()

    def __str__(self):
        return f"<Webcam(fps={self.fps})>"

    def _resize_frame(self, data, size, interp):
        return cv2.resize(data, dsize=size, interpolation=interp)

    def _update(self):
        if self.active:

            if time.time() - self._last_tick > 1 / self.fps:
                self._last_tick = time.time()

                has_frame, data = self._vid.read()

                if has_frame:
                    if self.original_size != self.current_size:
                        data = self._resize_frame(data, self.current_size, self.interp)
                    data = self.post_func(data)

                    self.frame_data = data
                    self.frame_surf = self._create_frame(data)

                    self._frames += 1

                    return True

        return False

    def update(self) -> bool:
        """
        Allows webcam to perform required operations. Draw method already calls this method, so it's usually not used. Returns True if a new frame is ready to be displayed.
        """
        return self._update()

    def set_post_func(self, func: Callable[[np.ndarray], np.ndarray]) -> None:
        """
        Changes the post processing function. Works the same as the post_func parameter.
        """
        self.post_func = func

    def set_interp(self, interp: Union[str, int]) -> None:
        """
        Changes the interpolation technique that OpenCV uses. Works the same as the interp parameter. Does nothing if OpenCV is not installed.
        """
        # cv2 will always be installed for webcam

        if interp in ("nearest", 0):
            self.interp = cv2.INTER_NEAREST
        elif interp in ("linear", 1):
            self.interp = cv2.INTER_LINEAR
        elif interp in ("area", 3):
            self.interp = cv2.INTER_AREA
        elif interp in ("cubic", 2):
            self.interp = cv2.INTER_CUBIC
        elif interp in ("lanczos4", 4):
            self.interp = cv2.INTER_LANCZOS4
        else:
            raise ValueError("Interpolation technique not recognized.")

    def play(self) -> None:
        """
        Sets video active to True.
        """
        self.active = True

    def stop(self) -> None:
        """
        Sets video active to False.
        """
        self.active = False
        self.frame_data = None
        self.frame_surf = None

    def resize(self, size: Tuple[int, int]) -> None:
        """
        Sets the current size of the video. This will also resize the current frame information, so no need
        to buffer a new frame.
        """
        self.current_size = size
        if self.frame_data is not None:
            self.frame_data = self._resize_frame(self.frame_data, self.current_size, self.interp)
            self.frame_surf = self._create_frame(self.frame_data)

    def resize_capture(self, size: Tuple[int, int]) -> bool:
        """
        Changes the resolution at which frames are captured from the webcam. Returns True if a resolution was found that matched the given size exactly. Otherwise, False will be returned and the closest matching resolution will be used.
        """
        self._vid.set(cv2.CAP_PROP_FRAME_WIDTH, size[0])
        self._vid.set(cv2.CAP_PROP_FRAME_HEIGHT, size[1])
        self.original_size = (
        int(self._vid.get(cv2.CAP_PROP_FRAME_WIDTH)), int(self._vid.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        return self.original_size == size

    def change_resolution(self, height: int) -> None:
        """
        Given a height, webcam will scale its dimensions while maintaining aspect ratio.
        Will scale width to an even number. Otherwise same as resize method.
        """
        w = int(height * self.aspect_ratio)
        if w % 2 == 1:
            w += 1
        self.resize((w, height))

    def close(self) -> None:
        """
        Releases resources. Always recommended to call when done. Attempting to use video after it has been closed
        may cause unexpected behaviour.
        """
        self.stop()
        self._vid.release()
        self.closed = True

    def get_pos(self) -> float:
        """
        Returns how long the webcam has been active. Is not reset if webcam is stopped.
        """
        return self._frames / self.fps

    def draw(self, surf: pygame.Surface, pos: Tuple[int, int], force_draw: bool = True) -> bool:
        """
        Draws the current video frame onto the given surface, at the given position.
        If force_draw is True, a surface will be drawn every time this is called.
        Otherwise, only new frames will be drawn.
        This reduces CPU usage but will cause flickering if anything is drawn under or above the video.
        This method also returns whether a frame was drawn.
        """
        if (self._update() or force_draw) and self.frame_surf is not None:
            self._render_frame(surf, pos)
            return True
        return False

    def _create_frame(self, data):
        return pygame.image.frombuffer(data.tobytes(), self.current_size, "BGR")

    def _render_frame(self, surf, pos):
        surf.blit(self.frame_surf, pos)

    def preview(self, max_fps: int = 60) -> None:
        """
        Opens a window and plays the webcam. This method will hang until the window is closed.
        Videos are played at whatever fps the webcam object is set to.
        """
        win = pygame.display.set_mode(self.current_size)
        pygame.display.set_caption(f"webcam")
        self.play()
        clock = pygame.time.Clock()
        while self.active:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.stop()
            clock.tick(max_fps)
            self.draw(win, (0, 0), force_draw=False)
            pygame.display.update()
        pygame.display.quit()
        self.close()
