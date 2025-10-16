# Web/pygbag-ready version
import asyncio
import pygame as pg
import sys
from pathlib import Path

# -------- Game settings --------
FPS = 60
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
SPEED = 5

# Visual & collision
IMAGE_HEIGHT = 100
HITBOX_HEIGHT = 68
HITBOX_WIDTH  = 75
JUMP_POWER = 15
GRAVITY = 1

# Colors
PLATFORM_COLOR = (0, 0, 0)
BG_COLOR = (200, 220, 255)
GRID_SPACING = 50
GRID_COLOR = (180, 200, 230)

# -------- Assets helper (web-safe) --------
ASSETS = Path("assets")

def load_image(name, size=None):
    """
    Load image from assets/ with convert_alpha.
    On failure, draw a magenta 'missing' placeholder so the game still runs.
    """
    p = ASSETS / name
    try:
        img = pg.image.load(p.as_posix()).convert_alpha()
        if size:
            img = pg.transform.scale(img, size)
        return img
    except Exception as e:
        w, h = size if size else (64, 64)
        surf = pg.Surface((w, h), pg.SRCALPHA)
        surf.fill((255, 0, 255, 180))
        f = pg.font.Font(None, 18)
        surf.blit(f.render("missing", True, (0, 0, 0)), (6, h//2 - 8))
        print(f"[WARN] Could not load {p}: {e}")
        return surf

# -------- Level geometry --------
Wall  = pg.Rect(-20, 0, 10, 600)
# Avoid huge widths in the browser; big numbers can cause canvas/perf issues
Wallb = pg.Rect(810, 100, 5000, 500)

LEVEL1    = [Wall, Wallb, pg.Rect(0, 500, 800, 40), pg.Rect(500, 400, 200, 20), pg.Rect(700, 320, 100, 20)]
LEVEL2    = [pg.Rect(-50, 0, 10, 600), Wallb, pg.Rect(100, 220, 100, 20), pg.Rect(120, 120, 700, 20), pg.Rect(-150, 320, 250, 20)]
LEVEL3    = [pg.Rect(-50, 0, 10, 600), Wallb, pg.Rect(-75, 500, 375, 40), pg.Rect(500, 250, 700, 20)]
LEVEL4    = [pg.Rect(-50, 0, 10, 600), Wallb, pg.Rect(-250, 500, 325, 40)]
LEVEL67   = [pg.Rect(-50, 0, 10, 600), Wallb, pg.Rect(500, 400, 200, 20), pg.Rect(0, 500, 800, 40)]
LEVEL2BUFF= [pg.Rect(100, 220, 500, 20), pg.Rect(100, 120, 700, 20), pg.Rect(-100, 320, 200, 20)]
LEVELFLOOR= [pg.Rect(-50, 0, 10, 600), Wallb, pg.Rect(0, 500, 800, 40)]
LEVELS    = [LEVEL1, LEVEL2, LEVEL3, LEVEL4]

# -------- Entities --------
class Springs:
    def __init__(self, x, y):
        self.image = load_image("spring.png", (75, 63))
        self.rect  = self.image.get_rect(topleft=(x, y))
    def draw(self, surface): surface.blit(self.image, self.rect.topleft)

class Springsv:
    def __init__(self, x, y, direction=1):
        # If you rename this file, update the string here.
        self.image = load_image("pixil-frame-0 (76).png", (24, 63))
        self.rect  = self.image.get_rect(topleft=(x, y))
        self.direction = direction
    def draw(self, surface): surface.blit(self.image, self.rect.topleft)

class Spikes:
    def __init__(self, x, y, direction=1):
        self.image = load_image("tophatspike.png", (50, 50))
        self.rect  = self.image.get_rect(topleft=(x, y))
    def draw(self, surface): surface.blit(self.image, self.rect.topleft)

class Portals:
    def __init__(self, x, y):
        self.image = load_image("portal.png", (74, 55))
        self.rect  = self.image.get_rect(topleft=(x, y))
    def draw(self, surface): surface.blit(self.image, self.rect.topleft)

class Player:
    def __init__(self, x, y):
        self.image = load_image("goober.png")  # use original size
        self.rect  = pg.Rect(x, y, HITBOX_WIDTH, HITBOX_HEIGHT)
        self.vel_y = 0
        self.vel_x = 0
        self.on_ground = False

    def handle_input(self, keys):
        # don't move here; only set desired velocity
        self.vel_x = 0
        if keys[pg.K_a] or keys[pg.K_LEFT]:
            self.vel_x = -SPEED
        if keys[pg.K_d] or keys[pg.K_RIGHT]:
            self.vel_x = SPEED
        if keys[pg.K_q]:
            self.vel_x = -SPEED * 2
        if keys[pg.K_e]:
            self.vel_x = SPEED * 2
        if (keys[pg.K_SPACE] or keys[pg.K_w] or keys[pg.K_UP]) and self.on_ground:
            self.vel_y = -JUMP_POWER
            self.on_ground = False

    def apply_gravity(self):
        self.vel_y += GRAVITY
        self.rect.x += int(self.vel_x)
        self.rect.y += self.vel_y
        # friction
        self.vel_x *= 0.8
        if abs(self.vel_x) < 0.2:
            self.vel_x = 0

    def check_collisions(self, platforms):
        self.on_ground = False
        for plat in platforms:
            if self.rect.colliderect(plat):
                # vertical
                if self.vel_y > 0 and self.rect.bottom - self.vel_y <= plat.top:
                    self.rect.bottom = plat.top
                    self.vel_y = 0
                    self.on_ground = True
                elif self.vel_y < 0 and self.rect.top - self.vel_y >= plat.bottom:
                    self.rect.top = plat.bottom
                    self.vel_y = 0
                else:
                    # horizontal
                    if self.rect.centerx < plat.centerx:
                        self.rect.right = plat.left
                    else:
                        self.rect.left = plat.right

    def spring_collisions(self, springs, springsv):
        for spring in springs:
            if self.rect.colliderect(spring.rect):
                if self.vel_y > 0 and self.rect.bottom <= spring.rect.top + self.vel_y:
                    self.vel_y = -JUMP_POWER * 1.5
        for sprin in springsv:
            if self.rect.colliderect(sprin.rect):
                self.vel_x += sprin.direction * SPEED * 2

    def spike_collisions(self, spikes):
        # FIX: check spike.rect (not spike)
        for spike in spikes:
            if self.rect.colliderect(spike.rect):
                return True
        return False

    def update(self, platforms, springs, springsv, spikes):
        self.apply_gravity()
        self.check_collisions(platforms)
        self.spring_collisions(springs, springsv)
        return self.spike_collisions(spikes)

    def draw(self, surface):
        draw_x = self.rect.centerx - self.image.get_width() // 2
        draw_y = self.rect.bottom - self.image.get_height()
        surface.blit(self.image, (draw_x, draw_y))

# -------- Level data --------
def leveldata(levelindex):
    SLEVEL3  = [Springs(250, 450)]
    SLEVEL4  = [Springs(100, 430), Springs(350, 220)]
    SLEVEL5  = [Springs(25, 500), Springs(100, 500), Springs(175, 500), Springs(250, 500),
                Springs(325, 500), Springs(400, 500), Springs(475, 500), Springs(550, 500),
                Springs(625, 500), Springs(700, 500)]
    SLEVEL67 = [Springs(500, 375)]
    SLEVEL8  = [Springs(240, 450)]
    SVLEVEL5 = [Springsv(5, 10, 1), Springsv(5, 75, 1), Springsv(5, 150, 1), Springsv(5, 225, 1),
                Springsv(5, 300, 1), Springsv(5, 375, 1), Springsv(5, 450, 1),
                Springsv(775, 10, -1), Springsv(775, 75, -1), Springsv(775, 150, -1),
                Springsv(775, 225, -1), Springsv(775, 300, -1), Springsv(775, 375, -1),
                Springsv(775, 450, -1)]
    SPLEVEL6     = [Spikes(250, 450)]
    SPLEVEL7     = [Spikes(250, 450), Spikes(300, 450)]
    SPLEVEL8     = [Spikes(300, 450), Spikes(350, 450), Spikes(400, 450), Spikes(450, 450), Spikes(500, 450), Spikes(550, 450)]
    SPLEVEL1BUFF = [Spikes(510, 350)]
    SPLEVEL3BUFF = [Spikes(475, 250)]
    SPLEVEL67BUFF= [Spikes(200, 450), Spikes(250, 450), Spikes(285, 450)]

    if levelindex == 0:
        return LEVEL1,  Portals(730, 240), [],        [],        25, 200, []
    elif levelindex == 1:
        return LEVEL2,  Portals(730,  50), [],        [],        25, 200, []
    elif levelindex == 2:
        return LEVEL3,  Portals(730, 200), SLEVEL3,   [],        25, 200, []
    elif levelindex == 3:
        return LEVEL4,  Portals(730, 260), SLEVEL4,   [],        25, 200, []
    elif levelindex == 4:
        return LEVEL4,  Portals(400, 150), SLEVEL5,   SVLEVEL5,  10, 300, []
    elif levelindex == 5:
        return LEVEL67, Portals(400, 150), SLEVEL67,  [],        10, 300, SPLEVEL6
    elif levelindex == 6:
        return LEVEL67, Portals(400, 155), SLEVEL67,  [],        10, 300, SPLEVEL7
    elif levelindex == 7:
        return LEVELFLOOR, Portals(700, 450), SLEVEL8, [],       10, 300, SPLEVEL8
    elif levelindex == 8:
        return LEVEL1,  Portals(730, 240), [],        [],        25, 200, SPLEVEL1BUFF
    elif levelindex == 9:
        return LEVEL2BUFF, Portals(730, 50), [],      [],        25, 200, []
    elif levelindex == 10:
        return LEVEL3,  Portals(730,  50), SLEVEL3,   [],        25, 200, SPLEVEL3BUFF
    elif levelindex == 11:
        return LEVEL67, Portals(700, 450), [],        [],        25, 200, SPLEVEL67BUFF
    elif levelindex == 12:
        return LEVEL67, Portals(700, 450), [],        [],        25, 200, SPLEVEL67BUFF
    else:
        return LEVEL1,  None,              [],        [],        25, 200, []

def draw_grid(surface):
    for x in range(0, SCREEN_WIDTH, GRID_SPACING):
        pg.draw.line(surface, GRID_COLOR, (x, 0), (x, SCREEN_HEIGHT))
    for y in range(0, SCREEN_HEIGHT, GRID_SPACING):
        pg.draw.line(surface, GRID_COLOR, (0, y), (SCREEN_WIDTH, y))

# -------- ASYNC main (required for pygbag) --------
async def main():
    pg.init()
    screen = pg.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pg.display.set_caption("Forgiving Platformer Hitbox (Web)")
    clock = pg.time.Clock()

    # Let the web FS mount before heavy work
    await asyncio.sleep(0)

    indexlevel = 0
    platforms, portal, springs, springsv, start_x, start_y, spikes = leveldata(indexlevel)
    player = Player(start_x, start_y)

    running = True
    while running:
        for event in pg.event.get():
            if event.type == pg.QUIT:
                running = False

        keys = pg.key.get_pressed()
        player.handle_input(keys)
        hit_spike = player.update(platforms, springs, springsv, spikes)

        # Respawn instead of hard exit() when hitting spikes
        if hit_spike:
            player.rect.topleft = (start_x, start_y)
            player.vel_x = 0
            player.vel_y = 0

        # Level advance
        if portal and player.rect.colliderect(portal.rect):
            indexlevel += 1
            platforms, portal, springs, springsv, start_x, start_y, spikes = leveldata(indexlevel)
            player.rect.topleft = (start_x, start_y)
            player.vel_x = 0
            player.vel_y = 0

        # ---- draw ----
        screen.fill(BG_COLOR)
        draw_grid(screen)
        for plat in platforms:
            pg.draw.rect(screen, PLATFORM_COLOR, plat)
        for spring in springs:
            spring.draw(screen)
        for sprin in springsv:
            sprin.draw(screen)
        for spike in spikes:
            spike.draw(screen)
            pg.draw.rect(screen, (255, 0, 0), spike.rect, 2)  # debug
        if portal:
            portal.draw(screen)
        player.draw(screen)
        #pg.draw.rect(screen, (255, 0, 0), player.rect, 2)      # debug

        pg.display.flip()

        # CRUCIAL for web
        await asyncio.sleep(0)
        clock.tick(FPS)

    pg.quit()
    sys.exit()

if __name__ == "__main__":
    asyncio.run(main())
