"""
demo_melee.py — Tiny **playable** demo showing how to use melee.py

What this file demonstrates:
- Creating a Player that owns a MeleeController from `melee.py`
- Moving the player around (arrow keys) and attacking (J)
- Two enemies that can be damaged
- How to compute a simple 4-way facing vector from keyboard input
- How to *visualize* the otherwise-invisible hitboxes for learning/debugging

Controls:
  Arrows  = move + set facing (4-way)
  J       = attack (windup -> active -> recovery)
  ESC     = quit

Tip for students:
- The reusable/“library” logic lives in `melee.py`.
- This file is just a minimal game loop that *uses* that library.
"""

import pygame
from melee import MeleeController, AttackSpec

# ----------------------------
# Simple configuration / colors
# ----------------------------
W, H = 640, 400
BG = (25, 25, 32)
CLR_PLAYER = (200, 200, 200)
CLR_ENEMY = (80, 170, 80)
CLR_FLASH = (220, 60, 60)
CLR_TEXT = (220, 220, 220)


def dir_from_keys(keys: pygame.key.ScancodeWrapper, last: pygame.Vector2) -> pygame.Vector2:
    """
    Compute a **4-way** facing vector from the current keyboard state.
    Returns one of: (-1,0), (1,0), (0,-1), (0,1).
    If no direction keys are pressed, keeps the previous value (`last`).

    Why the “prefer last axis” logic?
    - If the player holds LEFT+UP together, you must pick one axis for a 4-way system.
    - Preferring the last axis avoids flickering between directions frame-to-frame.
    """
    x = (1 if keys[pygame.K_RIGHT] else 0) - (1 if keys[pygame.K_LEFT] else 0)
    y = (1 if keys[pygame.K_DOWN] else 0) - (1 if keys[pygame.K_UP] else 0)

    if x and y:  # both pressed
        if abs(last.x) > abs(last.y):
            y = 0
        else:
            x = 0

    return pygame.Vector2(x, y) if (x or y) else last


class Enemy(pygame.sprite.Sprite):
    """
    Very small enemy:
    - Has HP and flashes red briefly when damaged (simple feedback).
    - Provides a `take_damage` method so the MeleeController's `on_hit` callback
      can interact with it without tight coupling.
    """
    def __init__(self, pos, hp: int = 6):
        super().__init__()
        self.image = pygame.Surface((30, 30))
        self.rect = self.image.get_rect(center=pos)
        self.max_hp = hp
        self.hp = hp
        self.flash_ms = 0  # visual flash time remaining (milliseconds)

    def take_damage(self, dmg: int) -> None:
        self.hp = max(0, self.hp - dmg)
        self.flash_ms = 120  # flash for 120 ms when hit

    def update(self, dt: int) -> None:
        # Show red while flashing; otherwise green
        if self.flash_ms > 0:
            self.flash_ms -= dt
            self.image.fill(CLR_FLASH)
        else:
            self.image.fill(CLR_ENEMY)


class Player(pygame.sprite.Sprite):
    """
    Minimal player:
    - Moves with arrow keys.
    - Maintains a facing vector (used by the melee system).
    - Owns a MeleeController that spawns/updates attack hitboxes.
    """
    def __init__(self, enemies: pygame.sprite.Group, attacks: pygame.sprite.Group):
        super().__init__()
        self.image = pygame.Surface((30, 44))
        self.image.fill(CLR_PLAYER)
        self.rect = self.image.get_rect(center=(W // 3, H // 2))

        # Movement/facing
        self.facing = pygame.Vector2(1, 0)  # start facing right
        self.speed = 0.22  # pixels per millisecond (frame-rate independent)

        # ---- Glue functions passed into MeleeController ----
        def get_facing() -> pygame.Vector2:
            """
            Provide a 4-way facing to the controller.
            Controller expects components ∈ {-1, 0, 1}.
            """
            fx = 1 if self.facing.x > 0 else (-1 if self.facing.x < 0 else 0)
            fy = 1 if self.facing.y > 0 else (-1 if self.facing.y < 0 else 0)
            return pygame.Vector2(fx, fy)

        def on_hit(attacker: pygame.sprite.Sprite, target: pygame.sprite.Sprite, spec: AttackSpec) -> None:
            """
            Decoupled damage application — the *controller* never mutates enemies.
            Instead, we do it here via a callback. Easy to swap for armor, crits, etc.
            """
            if hasattr(target, "take_damage"):
                target.take_damage(spec.damage)

        # Tunable attack timings (students can adjust feel here)
        spec = AttackSpec(windup_ms=120, active_ms=180, recovery_ms=200, damage=1)

        # The controller owns the attack state machine + spawns the hitbox Sprite.
        self.melee = MeleeController(self, enemies, attacks, spec, on_hit, get_facing)

    def handle_input(self, dt: int) -> pygame.key.ScancodeWrapper:
        """
        Move the player using arrow keys and update the facing vector.
        Returns `keys` in case the caller wants to use it for other actions.
        """
        keys = pygame.key.get_pressed()
        d = self.speed * dt  # distance this frame

        if keys[pygame.K_LEFT]:
            self.rect.x -= d
        if keys[pygame.K_RIGHT]:
            self.rect.x += d
        if keys[pygame.K_UP]:
            self.rect.y -= d
        if keys[pygame.K_DOWN]:
            self.rect.y += d

        # Update facing based on current input (stays the same if no key pressed)
        self.facing = dir_from_keys(keys, self.facing)
        return keys


def main() -> None:
    """Entry point: creates the world, runs the main loop, and draws debug info."""
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Melee demo (J to attack, arrows to move, ESC to quit)")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 18)

    # Sprite groups:
    # - `enemies` are passed to the melee system for collision checks.
    # - `attacks` holds the transient hitbox Sprites spawned by the controller.
    enemies = pygame.sprite.Group(
        Enemy((W * 2 // 3, H // 2 - 40)),
        Enemy((W * 2 // 3, H // 2 + 40)),
    )
    attacks = pygame.sprite.Group()
    player = Player(enemies, attacks)
    world = pygame.sprite.Group(player, *enemies)  # everything we draw normally

    running = True
    while running:
        # dt = elapsed milliseconds since last frame (use ms for timing everywhere)
        dt = clock.tick(60)

        # -----------------
        # EVENT PROCESSING
        # -----------------
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False
                elif e.key == pygame.K_j:
                    # Start an attack only when J is *pressed* (not held).
                    player.melee.try_start()

        # -----------------
        # UPDATE
        # -----------------
        player.handle_input(dt)   # movement + facing
        player.melee.update(dt)   # advance attack state machine
        enemies.update(dt)        # enemy flashes, etc.
        # Note: we don't need to call attacks.update(dt) — the controller already
        # updates the current hitbox. Calling it would be harmless though.

        # -----------------
        # DRAW
        # -----------------
        screen.fill(BG)
        world.draw(screen)

        # Visualize the otherwise-invisible attack hitboxes for learning.
        # Phase colors: yellow = windup, red = active, gray = recovery.
        for hb in attacks.sprites():
            phase_color = (
                (255, 60, 60, 110) if hb.active
                else (255, 235, 0, 90) if hb.elapsed < hb.active_start
                else (180, 180, 180, 50)
            )
            s = pygame.Surface(hb.rect.size, pygame.SRCALPHA)
            s.fill(phase_color)
            screen.blit(s, hb.rect.topleft)

        # Small HUD to make internal state visible while experimenting.
        hud = [
            f"phase={player.melee.phase}",
            f"t={int(player.melee.phase_time)}ms",
            f"facing=({int(player.facing.x)},{int(player.facing.y)})",
            f"enemy_hp={[e.hp for e in enemies]}",
            "Controls: arrows move/face, J attack, ESC quit",
        ]
        for i, line in enumerate(hud):
            screen.blit(font.render(line, True, CLR_TEXT), (8, 8 + i * 18))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
