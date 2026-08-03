import sys, math
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image
from stitcher import grid_geometry, compose, natural_key, shorten

def box(w, h, c): return Image.new("RGB", (w, h), c)

# 1. single row, no gap
W,H,p = grid_geometry([(100,80),(60,120)], 0, 2)
assert (W,H) == (160,120), (W,H)
assert p == [(0,20),(100,0)], p          # shorter image centred vertically

# 2. row with gap
W,H,p = grid_geometry([(100,80),(60,120)], 40, 2)
assert (W,H) == (200,120), (W,H)
assert p[1][0] == 140, p

# 3. column
W,H,p = grid_geometry([(100,80),(60,120)], 10, 1)
assert (W,H) == (100,210), (W,H)
assert p == [(0,0),(20,90)], p           # narrower image centred horizontally

# 4. 2x2 grid with a ragged last row
sizes = [(100,100),(50,50),(80,80)]
W,H,p = grid_geometry(sizes, 20, 2)
assert (W,H) == (170,200), (W,H)   # col widths sized independently: 100 + 50 + gap
assert p[2] == (10,120), p               # third image centred in col 0 of row 1

# 5. cols clamped to n, empty case
assert grid_geometry([(10,10)], 5, 9)[:2] == (10,10)
assert grid_geometry([], 5, 2) == (0,0,[])

# 6. compose actually writes pixels where geometry says
canvas = compose([box(40,40,(255,0,0)), box(40,40,(0,0,255))], 20, 2)
assert canvas.size == (100,40)
assert canvas.getpixel((5,20)) == (255,0,0)
assert canvas.getpixel((50,20)) == (0,0,0)      # the black bar
assert canvas.getpixel((80,20)) == (0,0,255)

# 7. RGBA and greyscale inputs survive
canvas = compose([Image.new("RGBA",(20,20),(1,2,3,128)), Image.new("L",(20,20),99)], 0, 2)
assert canvas.mode == "RGB" and canvas.size == (40,20)

# 8. helpers
assert natural_key("p2.png") < natural_key("p10.png")
assert shorten("a"*40) == "a"*24 and shorten("short") == "short"

print("all layout tests pass")
