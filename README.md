# This is Fire!

A real-time ASCII fire simulation built with pygame. The flame reacts to how you drag the window — move it left or right and watch the fire lean with the wind.

---

## Requirements

- Python 3.10+
- pygame
- numpy

Install dependencies with:

```bash
pip install pygame numpy
```

---

## Running

```bash
python campfire.py
```

The app launches in **borderless fullscreen** mode. A simulated window appears in the centre of your screen — you can drag it by its title bar.

| Action | Effect |
|---|---|
| Drag title bar left/right | Wind blows the fire in that direction |
| Click `EXTINGUISH FIRE` button | Gradually cools the fire down |
| Click `IGNITE FIRE` button | Re-ignites the fire |
| Click `✕` or press `ESC` | Quit |

> **Why borderless fullscreen?** The standard OS window freezes pygame when you click and drag its title bar. By running fullscreen and drawing a fake window inside pygame, the simulation loop never pauses.

---

## How It Works

### 1. Gaussian Flame Shape — `make_weights(cols)`

The fire is confined to a narrow campfire column using a **Gaussian (normal) distribution** centred horizontally:

```
w(x) = exp( -0.5 · ((x − μ) / σ)² )
```

where `μ = cols / 2` (centre column) and `σ = cols × 0.085` (tight spread). Any weight below `0.04` is zeroed out, creating a hard cutoff at the edges. This mask is reapplied every frame so heat cannot bleed sideways into empty space.

---

### 2. Heat Seeding — bottom rows

Each frame, the three bottom rows are seeded with fresh heat drawn from **uniform random distributions**, weighted by the Gaussian mask raised to increasing powers:

| Row | Distribution | Mask power | Effect |
|---|---|---|---|
| Bottom | `U(0.88, 1.00) · w¹` | 1 | Full-width white-hot base |
| -1 | `U(0.70, 0.95) · w^1.3` | 1.3 | Slightly narrower, cooler |
| -2 | `U(0.45, 0.75) · w²` | 2.0 | Narrow ember core |

Raising the mask to higher powers sharpens the Gaussian, making upper seed rows progressively narrower and producing a natural tapering flame silhouette.

---

### 3. Upward Propagation — cellular automaton

Each non-seed cell is updated by looking at the **three cells directly below it** (left, centre, right). A weighted average simulates heat rising:

```
avg = 0.55 · below_centre
    + (0.225 − wind_norm · 0.12) · below_left
    + (0.225 + wind_norm · 0.12) · below_right
```

The `wind_norm` term (ranging from −1 to +1) shifts the weight balance between left and right, causing the flame to lean in the drag direction.

A **random horizontal drift** (`−1`, `0`, or `+1` columns, biased toward `0`) is added each frame via `numpy.roll`, creating turbulent flickering.

---

### 4. Decay — height-dependent cooling

After averaging, a decay value is subtracted from each cell:

```
decay(r, c) = clip( height_factor(r) · noise(r, c) − bias(c), 0, 0.35 )
```

- **`height_factor`** is a linear ramp from `0.28` (top of grid) to `0.07` (just above the seed rows), so the flame cools fast at the tip and slowly near the base.
- **`noise`** is a fresh `U(0, 1)` sample every frame, giving each cell independent stochastic cooling.
- **`bias`** is a fixed per-column offset sampled once at startup from `U(0, 0.06)`. Columns with a higher bias resist decay, creating persistent brighter streaks that give the flame a realistic irregular silhouette.

---

### 5. Wind — exponential smoothing

Wind is derived from the **velocity of the fake window** as it is dragged:

```
raw_wind  = Δx · 0.55
smoothed += (raw_wind − smoothed) · 0.4      # low-pass filter
```

The `0.4` factor is the **smoothing coefficient** of a first-order IIR (infinite impulse response) low-pass filter. A value of `1.0` would mean instant response; lower values add inertia so the flame leans and recovers gradually rather than snapping.

Inside the fire simulation the wind target also decays each frame:

```
wind_target *= 0.85
```

This means the fire naturally calms down after you stop dragging, with an exponential decay toward zero (half-life of roughly 4 frames).

---

### 6. ASCII Rendering

Heat values `v ∈ [0, 1]` are mapped to a 67-character gradient string:

```
"  ..,'`^\":;-~=+<>!?i|l1ItrfjJYxnuvczXYUCLO0QZmwpqbdkhaoe*%&#MW&8B@"
```

The character index is `floor(v · (len − 1))`. Cells below `0.018` are skipped entirely (rendered as background black), avoiding unnecessary draw calls for cold pixels.

Brightness is bucketed into three colours:

| Heat range | Colour |
|---|---|
| v > 0.75 | White (220, 220, 220) — white-hot core |
| 0.45 < v ≤ 0.75 | Mid grey (155, 155, 155) — active flame |
| v ≤ 0.45 | Dim grey (90, 90, 90) — dying embers |

All rendered glyphs are cached in a dictionary keyed by `(character, colour)` to avoid re-rasterising the same surface on every frame.