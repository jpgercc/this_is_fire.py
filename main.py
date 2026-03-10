import pygame
import sys
import numpy as np

# ── Cell / grid config ─────────────────────────────────────────────────────────
CELL_W  = 9
CELL_H  = 15
FPS     = 30

COLS      = 72
FIRE_ROWS = 36
BASE_ROWS = 5
BTN_ROWS  = 3

UI_ROWS    = BTN_ROWS + 1
TOTAL_ROWS = UI_ROWS + FIRE_ROWS + BASE_ROWS

WIN_W = COLS   * CELL_W
WIN_H = TOTAL_ROWS * CELL_H

FIRE_Y_OFFSET = UI_ROWS * CELL_H

# ── Fake title-bar ─────────────────────────────────────────────────────────────
TITLEBAR_H       = 28
TITLEBAR_COL     = (30,  30,  30)
TITLEBAR_ACTIVE  = (50,  50,  50)
TITLEBAR_TEXT    = (200, 200, 200)
CLOSE_COL        = (180,  60,  60)
CLOSE_HOV        = (220,  80,  80)
BORDER_COL       = (70,   70,  70)

# ── Colours ────────────────────────────────────────────────────────────────────
BLACK      = (0,   0,   0)
WHITE      = (220, 220, 220)
DIM        = (90,  90,  90)
MID        = (155, 155, 155)
DESKTOP_BG = (18,  18,  22)

CHARS = "  ..,'`^\":;-~=+<>!?i|l1ItrfjJYxnuvczXYUCLO0QZmwpqbdkhaoe*%&#MW&8B@"

# ── Fire seed mask ─────────────────────────────────────────────────────────────
def make_weights(cols):
    cx, sigma = cols / 2.0, cols * 0.085
    x = np.arange(cols, dtype=np.float32)
    w = np.exp(-0.5 * ((x - cx) / sigma) ** 2)
    w[w < 0.04] = 0.0
    return w

# ── Fire simulation ────────────────────────────────────────────────────────────
class FireSim:
    def __init__(self, cols, rows):
        self.cols, self.rows = cols, rows
        self.grid    = np.zeros((rows, cols), dtype=np.float32)
        self.weights = make_weights(cols)
        rng = np.random.default_rng(42)
        self.bias        = rng.uniform(0.0, 0.06, cols).astype(np.float32)
        self.wind        = 0.0
        self.wind_target = 0.0

    def set_wind(self, wind):
        self.wind_target = float(np.clip(wind, -4.0, 4.0))

    def step(self):
        g = self.grid
        rows, cols, w = self.rows, self.cols, self.weights

        self.wind        += (self.wind_target - self.wind) * 0.25
        self.wind_target *= 0.85

        g[rows-1, :] = np.clip(np.random.uniform(0.88, 1.0,  cols) * w,        0, 1)
        g[rows-2, :] = np.clip(np.random.uniform(0.70, 0.95, cols) * (w**1.3), 0, 1)
        g[rows-3, :] = np.maximum(g[rows-3, :],
                        np.random.uniform(0.45, 0.75, cols) * (w**2.0))

        below = g[1:, :]
        drift = np.random.choice([-1, 0, 0, 0, 1]) + int(round(self.wind))
        left  = np.roll(below,  1 + drift, axis=1)
        right = np.roll(below, -1 + drift, axis=1)

        wn  = np.clip(self.wind / 4.0, -1.0, 1.0)
        avg = 0.55*below + (0.225 - wn*0.12)*left + (0.225 + wn*0.12)*right

        hf    = np.linspace(0.28, 0.07, rows-1, dtype=np.float32)[:, np.newaxis]
        noise = np.random.uniform(0.0, 1.0, (rows-1, cols)).astype(np.float32)
        decay = np.clip(hf * noise - self.bias[np.newaxis, :], 0.0, 0.35)

        g[:-1, :] = np.clip(avg - decay, 0.0, 1.0)
        g *= np.minimum(w + 0.25, 1.0)[np.newaxis, :]

    def cool_down(self):
        self.grid *= 0.82
        self.grid[self.grid < 0.012] = 0.0

# ── Campfire base art ──────────────────────────────────────────────────────────
BASE_ART = [
    r"          )  (         ",
    r"       ( /(  )\ )      ",
    r"  .--./`-'`-/`-'\.--.  ",
    r" /____\__|__|__/____\ ",
    r"'------'--''--'------'",
]

# ── ASCII button ───────────────────────────────────────────────────────────────
class AsciiButton:
    ON_LABEL  = " EXTINGUISH FIRE "
    OFF_LABEL = "   IGNITE FIRE   "

    def __init__(self, font, content_w):
        self.font      = font
        self.content_w = content_w
        self.active    = True
        inner  = f"[{self.ON_LABEL}]"
        border = "+" + "-" * (len(inner) + 2) + "+"
        self._bw   = len(border)
        left_px    = (content_w - self._bw * CELL_W) // 2
        self.rect  = pygame.Rect(left_px, CELL_H, self._bw * CELL_W, CELL_H)

    def _lines(self):
        label  = self.ON_LABEL if self.active else self.OFF_LABEL
        inner  = f"[{label}]"
        border = "+" + "-" * (len(inner) + 2) + "+"
        return [border, "| " + inner + " |", border]

    def draw(self, surface, mouse_in_content):
        hovered = self.rect.collidepoint(mouse_in_content)
        for i, line in enumerate(self._lines()):
            col  = WHITE if (hovered or i == 1) else DIM
            surf = self.font.render(line, True, col)
            x    = (self.content_w - surf.get_width()) // 2
            surface.blit(surf, (x, i * CELL_H))

    def handle_click(self, pos):
        if self.rect.collidepoint(pos):
            self.active = not self.active
            return True
        return False

# ── Heat colour ────────────────────────────────────────────────────────────────
def heat_col(v):
    if v > 0.75: return WHITE
    if v > 0.45: return MID
    return DIM

# ── Fake draggable window ──────────────────────────────────────────────────────
class FakeWindow:
    def __init__(self, desktop_w, desktop_h, font, title="This is fire"):
        self.title = title
        self.font  = font
        self.w     = WIN_W
        self.h     = WIN_H + TITLEBAR_H
        self.x     = (desktop_w - self.w) // 2
        self.y     = (desktop_h - self.h) // 2

        self._dragging  = False
        self._drag_off  = (0, 0)
        self._prev_x    = float(self.x)
        self._smoothed  = 0.0

        self.close_rect    = pygame.Rect(self.w - TITLEBAR_H, 0, TITLEBAR_H, TITLEBAR_H)
        self._content_surf = pygame.Surface((self.w, WIN_H))
        self._cache: dict  = {}

        self.fire   = FireSim(COLS, FIRE_ROWS)
        self.button = AsciiButton(font, self.w)
        self.alive  = True

    def _glyph(self, ch, col):
        key = (ch, col)
        if key not in self._cache:
            self._cache[key] = self.font.render(ch, True, col)
        return self._cache[key]

    def handle_event(self, event):
        mx, my = pygame.mouse.get_pos()
        rx, ry = mx - self.x, my - self.y

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.close_rect.collidepoint(rx, ry):
                self.alive = False
                return
            if 0 <= rx < self.w and 0 <= ry < TITLEBAR_H:
                self._dragging = True
                self._drag_off = (rx, ry)
                return
            if 0 <= rx < self.w and TITLEBAR_H <= ry < self.h:
                self.button.handle_click((rx, ry - TITLEBAR_H))

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._dragging = False

        elif event.type == pygame.MOUSEMOTION:
            if self._dragging:
                self.x = mx - self._drag_off[0]
                self.y = my - self._drag_off[1]

    def update_wind(self):
        dx = float(self.x) - self._prev_x
        self._prev_x   = float(self.x)
        raw = dx * 0.55
        self._smoothed += (raw - self._smoothed) * 0.4
        self.fire.set_wind(self._smoothed)

    def step(self):
        self.update_wind()
        if self.button.active:
            self.fire.step()
        else:
            self.fire.cool_down()

    def draw(self, desktop):
        mx, my = pygame.mouse.get_pos()
        rx, ry = mx - self.x, my - self.y

        # ── Title bar ──────────────────────────────────────────────────────────
        tb_col = TITLEBAR_ACTIVE if self._dragging else TITLEBAR_COL
        tb = pygame.Surface((self.w, TITLEBAR_H))
        tb.fill(tb_col)
        tf = self.font.render(self.title, True, TITLEBAR_TEXT)
        tb.blit(tf, (8, (TITLEBAR_H - tf.get_height()) // 2))
        close_hov = self.close_rect.collidepoint(rx, ry)
        pygame.draw.rect(tb, CLOSE_HOV if close_hov else CLOSE_COL, self.close_rect)
        xf = self.font.render("X", True, WHITE)
        tb.blit(xf, (
            self.close_rect.x + (TITLEBAR_H - xf.get_width())  // 2,
            self.close_rect.y + (TITLEBAR_H - xf.get_height()) // 2,
        ))

        # ── Content ────────────────────────────────────────────────────────────
        cs = self._content_surf
        cs.fill(BLACK)
        mouse_in_content = (rx, ry - TITLEBAR_H)
        self.button.draw(cs, mouse_in_content)

        grid = self.fire.grid
        for r in range(FIRE_ROWS):
            for c in range(COLS):
                v = float(grid[r, c])
                if v < 0.018:
                    continue
                idx = min(int(v * (len(CHARS) - 1)), len(CHARS) - 1)
                cs.blit(self._glyph(CHARS[idx], heat_col(v)),
                        (c * CELL_W, FIRE_Y_OFFSET + r * CELL_H))

        base_y = FIRE_Y_OFFSET + FIRE_ROWS * CELL_H
        for ri, line in enumerate(BASE_ART):
            x_off = (self.w - len(line) * CELL_W) // 2
            for ci, ch in enumerate(line):
                if ch != ' ':
                    cs.blit(self._glyph(ch, WHITE),
                            (x_off + ci * CELL_W, base_y + ri * CELL_H))

        # ── Blit to desktop ────────────────────────────────────────────────────
        pygame.draw.rect(desktop, BORDER_COL,
                         (self.x - 1, self.y - 1, self.w + 2, self.h + 2), 1)
        desktop.blit(tb, (self.x, self.y))
        desktop.blit(cs, (self.x, self.y + TITLEBAR_H))

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    pygame.init()
    info = pygame.display.Info()
    DW, DH = info.current_w, info.current_h

    # Borderless fullscreen
    screen = pygame.display.set_mode((DW, DH), pygame.NOFRAME)
    pygame.display.set_caption("This is fire")
    clock  = pygame.time.Clock()

    try:
        font = pygame.font.SysFont("Courier New", CELL_H - 1, bold=True)
    except Exception:
        font = pygame.font.SysFont("monospace", CELL_H - 1, bold=True)

    fake_win  = FakeWindow(DW, DH, font)
    hint_font = pygame.font.SysFont("Courier New", 11)
    hint_surf = hint_font.render(
        "Drag the title bar to blow the fire · ESC to quit", True, (60, 60, 70))

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            fake_win.handle_event(event)

        if not fake_win.alive:
            running = False

        fake_win.step()

        # ── Desktop background ────────────────────────────────────────────────
        screen.fill(DESKTOP_BG)
        for gx in range(0, DW, 40):
            pygame.draw.line(screen, (22, 22, 28), (gx, 0), (gx, DH))
        for gy in range(0, DH, 40):
            pygame.draw.line(screen, (22, 22, 28), (0, gy), (DW, gy))

        fake_win.draw(screen)
        screen.blit(hint_surf, (8, DH - hint_surf.get_height() - 6))

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()