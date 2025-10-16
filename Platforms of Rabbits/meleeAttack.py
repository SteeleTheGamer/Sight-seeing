"""
Directional melee attack (↑ ↓ ← →) with clear phases (windup → active → recovery).

What this file shows:
- A persistent hitbox sprite that lasts longer than one frame.
- A simple finite state machine (FSM) to time attack phases.
- Axis-aligned hitboxes that move/rotate with player facing.
- Basic collision + "once per target" damage behavior.
- A tiny demo harness so students can run and tinker.

Controls:
  Arrow keys = move and set facing
  J          = attack
  ESC / close window = quit
"""

import pygame

# -----------------------------
# Tunables (students tweak here)
# -----------------------------
WINDUP_MS    = 120   # time before hit becomes "active" and can do damage
ACTIVE_MS    = 180   # time during which hitbox deals damage
RECOVERY_MS  = 200   # time after the swing ends (cannot start a new one)
TOTAL_MS     = WINDUP_MS + ACTIVE_MS + RECOVERY_MS

# Hitbox sizes per orientation (horizontal vs vertical)
HITBOX_W, HITBOX_H       = 44, 24   # width/height for left or right swings
HITBOX_W_V, HITBOX_H_V   = 24, 44   # width/height for up or down swings

FRONT_GAP     = 6       # small gap so hitbox sits just beyond the player's body
PLAYER_SPEED  = 0.22    # pixels per millisecond; easy to tune & frame-rate independent

# Colors for quick visual debugging (RGBA)
CLR_WINDUP  = (255, 235,  0,  90)   # yellow
CLR_ACTIVE  = (255,  60, 60, 120)   # red
CLR_RECOV   = (180, 180,180,  50)   # gray
CLR_BG      = ( 25,  25, 32)        # background
CLR_TEXT    = (220, 220,220)        # HUD text
CLR_PLAYER  = (200, 200,200)
CLR_ENEMY   = ( 80, 170, 80)
CLR_FLASH   = (220,  60, 60)


# -----------------------------
# Utility: facing from keyboard
# -----------------------------
def dir_from_keys(keys: pygame.key.ScancodeWrapper, last_vec: pygame.Vector2) -> pygame.Vector2:
    """
    Determine a 4-way facing vector from the arrow keys.
    Keeps the last facing direction if no direction keys are pressed.

    Returns one of: (-1,0), (1,0), (0,-1), (0,1) or the previous value.
    """
    x = (1 if keys[pygame.K_RIGHT] else 0) - (1 if keys[pygame.K_LEFT] else 0)
    y = (1 if keys[pygame.K_DOWN]  else 0) - (1 if keys[pygame.K_UP]   else 0)

    # If both are pressed, prefer the last axis so the facing doesn't flicker.
    if x and y:
        if abs(last_vec.x) > abs(last_vec.y):
            y = 0
        else:
            x = 0

    if x or y:
        return pygame.Vector2(x, y)
    return last_vec


# -----------------------------
# Enemy (very minimal)
# -----------------------------
class Enemy(pygame.sprite.Sprite):
    """
    A very simple enemy with HP that briefly flashes when hit.
    Students can replace this with their own enemy class.
    """
    def __init__(self, pos, hp=6):
        super().__init__()
        self.image = pygame.Surface((30, 30))
        self.rect = self.image.get_rect(center=pos)
        self.max_hp = hp
        self.hp = hp
        self.flash_ms = 0  # counts down to stop flashing

    def take_damage(self, dmg: int) -> None:
        """Reduce HP and start a short flash as feedback."""
        self.hp = max(0, self.hp - dmg)
        self.flash_ms = 120  # flash for 120 ms
        print(f"[HIT] Enemy at {self.rect.center} -> HP {self.hp}/{self.max_hp}")

    def update(self, dt_ms: int) -> None:
        """Update the flash timer and color accordingly."""
        if self.flash_ms > 0:
            self.flash_ms -= dt_ms
            self.image.fill(CLR_FLASH)
        else:
            self.image.fill(CLR_ENEMY)


# -----------------------------
# Attack hitbox (the star)
# -----------------------------
class AttackHitbox(pygame.sprite.Sprite):
    """
    A persistent hitbox that follows the player and deals damage
    only during the 'active' window of the attack.

    Core ideas:
    - Exists for TOTAL_MS (windup+active+recovery).
    - Only checks collisions when 'active' == True.
    - Tracks 'already_hit' so each enemy is damaged at most once
      per swing (simple, predictable behavior for beginners).
    """
    def __init__(self, owner: pygame.sprite.Sprite, enemies: pygame.sprite.Group, facing: pygame.Vector2):
        super().__init__()
        self.owner = owner
        self.enemies = enemies
        # ensure facing components are in {-1, 0, 1}
        fx = 1 if facing.x > 0 else (-1 if facing.x < 0 else 0)
        fy = 1 if facing.y > 0 else (-1 if facing.y < 0 else 0)
        self.facing = pygame.Vector2(fx, fy)

        # Phase timing
        self.elapsed = 0
        self.active_start = WINDUP_MS
        self.active_end   = WINDUP_MS + ACTIVE_MS
        self.duration     = TOTAL_MS
        self.active = False

        # Choose hitbox size based on vertical vs horizontal swing
        if self.facing.y == 0:   # left/right
            size = (HITBOX_W, HITBOX_H)
        else:                     # up/down
            size = (HITBOX_W_V, HITBOX_H_V)

        # This surface is semi-transparent so students can "see" the hitbox
        self.image = pygame.Surface(size, pygame.SRCALPHA)
        self.rect = self.image.get_rect()

        # Record targets we've already hit (so we don't apply damage every frame)
        self.already_hit = set()

        # Draw initial (windup) tint
        self._redraw(CLR_WINDUP)

    # ---- internal helpers ----
    def _reposition(self) -> None:
        """Position the hitbox just in front of the player, based on facing."""
        pr = self.owner.rect
        if self.facing.x == 1:          # face right
            self.rect.midleft  = (pr.right + FRONT_GAP, pr.centery)
        elif self.facing.x == -1:       # face left
            self.rect.midright = (pr.left - FRONT_GAP,  pr.centery)
        elif self.facing.y == -1:       # face up
            self.rect.midbottom = (pr.centerx, pr.top - FRONT_GAP)
        elif self.facing.y == 1:        # face down
            self.rect.midtop    = (pr.centerx, pr.bottom + FRONT_GAP)

    def _redraw(self, color_rgba) -> None:
        """Fill the translucent surface with a color that indicates the phase."""
        self.image.fill((0, 0, 0, 0))  # clear (fully transparent)
        pygame.draw.rect(self.image, color_rgba, self.image.get_rect(), border_radius=4)

    # ---- main update ----
    def update(self, dt_ms: int) -> None:
        """
        Advance the attack timeline and (only while active) check for overlaps.
        """
        self.elapsed += dt_ms
        self._reposition()

        # Determine if we're in the active sub-window this frame.
        self.active = self.active_start <= self.elapsed < self.active_end

        # Pick a color for the current phase (good for student visualization)
        if self.elapsed < self.active_start:
            self._redraw(CLR_WINDUP)
        elif self.active:
            self._redraw(CLR_ACTIVE)
        else:
            self._redraw(CLR_RECOV)

        # Only deal damage when active
        if self.active:
            # spritecollide checks simple rect overlap (fine for a beginner demo).
            # Students can swap for pixel-perfect masks later.
            for enemy in pygame.sprite.spritecollide(self, self.enemies, False):
                if enemy not in self.already_hit:
                    enemy.take_damage(1)  # << easy place to scale damage or add crits, etc.
                    self.already_hit.add(enemy)

        # End of the whole attack
        if self.elapsed >= self.duration:
            self.kill()  # remove from its sprite group


# -----------------------------
# Player
# -----------------------------
class Player(pygame.sprite.Sprite):
    """
    A basic player entity that:
    - Moves with arrow keys (for demo).
    - Tracks a facing vector (↑ ↓ ← →).
    - Starts an attack if currently idle.
    - Owns a reference to its AttackHitbox (if any).
    """
    def __init__(self, enemies: pygame.sprite.Group, attack_group: pygame.sprite.Group):
        super().__init__()
        self.image = pygame.Surface((30, 44))
        self.image.fill(CLR_PLAYER)
        self.rect = self.image.get_rect(center=(140, 180))

        self.enemies = enemies
        self.attack_group = attack_group

        # Attack state machine
        self.state = "idle"   # "idle" | "windup" | "active" | "recovery"
        self.state_time = 0   # milliseconds in current state

        self.facing = pygame.Vector2(1, 0)  # start facing right
        self.attack_hitbox = None  # type: AttackHitbox | None

    def start_attack(self) -> None:
        """
        Begin an attack ONLY if idle.
        (Students: you can allow dash-cancel, jump-cancel, etc., by changing this rule.)
        """
        if self.state == "idle":
            self.state = "windup"
            self.state_time = 0
            hb = AttackHitbox(self, self.enemies, self.facing)
            self.attack_hitbox = hb
            self.attack_group.add(hb)

    def update(self, dt_ms: int, keys: pygame.key.ScancodeWrapper) -> None:
        """
        - Move the player (tiny demo movement).
        - Update facing from current key state.
        - Advance the attack state machine.
        - Keep any existing hitbox aligned to the current facing.
        """
        # --- movement (frame-rate independent) ---
        delta = PLAYER_SPEED * dt_ms
        if keys[pygame.K_LEFT]:  self.rect.x -= delta
        if keys[pygame.K_RIGHT]: self.rect.x += delta
        if keys[pygame.K_UP]:    self.rect.y -= delta
        if keys[pygame.K_DOWN]:  self.rect.y += delta

        # --- facing vector from keys (stays same if no keys pressed) ---
        self.facing = dir_from_keys(keys, self.facing)

        # --- attack state machine (timed by milliseconds) ---
        if self.state in ("windup", "active", "recovery"):
            self.state_time += dt_ms

            # Transition points aligned with the hitbox's own timeline
            if self.state == "windup" and self.state_time >= WINDUP_MS:
                self.state = "active"
            elif self.state == "active" and self.state_time >= WINDUP_MS + ACTIVE_MS:
                self.state = "recovery"
            elif self.state == "recovery" and self.state_time >= TOTAL_MS:
                self.state = "idle"
                self.state_time = 0
                self.attack_hitbox = None  # (the hitbox also kills itself)

        # Keep the hitbox following our current facing (optional: lock facing during windup)
        if self.attack_hitbox:
            self.attack_hitbox.facing = self.facing


# -----------------------------
# Demo harness (so students can run this file)
# -----------------------------
def main():
    """Minimal runnable example to see the melee system in action."""
    pygame.init()
    screen = pygame.display.set_mode((520, 360))
    pygame.display.set_caption("Directional Melee Demo")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 18)

    # Make two enemies so it's easy to test up/down vs left/right
    enemies = pygame.sprite.Group(Enemy((260, 120)), Enemy((260, 240)))
    attacks = pygame.sprite.Group()
    player = Player(enemies, attacks)
    world = pygame.sprite.Group(player, *enemies)  # everything drawable except hitboxes

    running = True
    while running:
        dt = clock.tick(60)  # milliseconds since last frame (used everywhere)
        # ---- input events ----
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_j:
                    player.start_attack()

        keys = pygame.key.get_pressed()

        # ---- update phase ----
        player.update(dt, keys)
        enemies.update(dt)
        attacks.update(dt)  # hitboxes live in their own group

        # ---- draw phase ----
        screen.fill(CLR_BG)
        world.draw(screen)
        attacks.draw(screen)  # show translucent hitboxes for learning

        # Tiny HUD so students can "see" state & facing in real time
        hud_lines = [
            f"state={player.state}",
            f"t={int(player.state_time)}ms",
            f"facing=({int(player.facing.x)},{int(player.facing.y)})",
            f"enemy_hp={[e.hp for e in enemies.sprites()]}",
            "Controls: arrows to move/face, J to attack",
        ]
        for i, text in enumerate(hud_lines):
            screen.blit(font.render(text, True, CLR_TEXT), (8, 8 + i*18))

        pygame.display.flip()

    pygame.quit()


# When run directly: start the demo
if __name__ == "__main__":
    main()


# =============================================================================
# Suggested Integration Into Another Program (READ-ME STYLE NOTES)
# =============================================================================
# 1) Copy the pieces
#    - Bring over: AttackHitbox, dir_from_keys, and the Player attack FSM
#      (the state machine lines in Player.update + Player.start_attack).
#    - Keep your own Player/Enemy classes if you like—your Enemy just needs:
#         - a .rect (pygame.Rect for collisions)
#         - a .take_damage(dmg: int) method
#
# 2) Create/keep sprite groups
#    - You need an `enemies` group and an `attacks` group (for hitboxes).
#    - When starting an attack, construct AttackHitbox(...) and add it to `attacks`.
#
# 3) Hook into your main loop
#    Example glue (pseudo-code you can paste into your loop):
#
#        # -- events --
#        for event in pygame.event.get():
#            if event.type == pygame.KEYDOWN:
#                if event.key == pygame.K_j:      # your attack button
#                    player.start_attack()
#
#        # -- per-frame updates --
#        dt = clock.tick(60)                      # milliseconds since last frame
#        keys = pygame.key.get_pressed()
#        player.update(dt, keys)                  # moves + state machine
#        enemies.update(dt)                       # your existing logic is fine
#        attacks.update(dt)                       # keeps hitboxes alive & colliding
#
#        # -- draw --
#        screen.fill((25,25,32))
#        all_sprites.draw(screen)                 # or draw your world however you prefer
#        attacks.draw(screen)                     # can hide later when confident
#        pygame.display.flip()
#
# 4) Pass dt everywhere
#    - Keep things frame-rate independent: use milliseconds (`clock.tick(...)`) to
#      advance timers and movement. Avoid "every N frames" logic.
#
# 5) Tune & extend
#    - Adjust WINDUP_MS, ACTIVE_MS, RECOVERY_MS and hitbox sizes to match your art.
#    - Combos: allow `start_attack()` during a small "combo window" near the end of
#      recovery and spawn a different AttackHitbox (or change damage, size, timing).
#    - 8-way or mouse aim: compute a facing vector from the mouse or WASD and either
#      snap to 8 directions (simple) or use rotated polygons/masks (advanced).
#
# 6) Debugging tips
#    - Leave hitboxes visible until you're confident.
#    - Log hits in Enemy.take_damage; add a small "flash" or sound to confirm.
#    - If you don't see hits: move closer, increase hitbox size, or print
#      `player.facing` and the hitbox rect to confirm alignment.
#
# End of integration notes.
