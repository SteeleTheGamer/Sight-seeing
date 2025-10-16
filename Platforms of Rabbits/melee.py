"""
melee.py — A small, refactor-friendly 4-direction melee system for Pygame.

Goals for students:
- Read and understand a self-contained module (state machine + hitbox).
- Identify interfaces and seams (timers, collision, damage callback).
- Integrate into an existing game loop with minimal assumptions.
- Refactor safely (e.g., swap collision strategy, add combos, add specs).

This module purposely has:
- Clear docstrings and comments.
- Small API surface (MeleeController) that a "Player" can own.
- Inversion of control for damage (on_hit callback).
- No demo loop (library-style).
"""

from dataclasses import dataclass
from typing import Callable, Optional
import pygame


# -----------------------------------------
# Data: AttackSpec (students can extend this)
# -----------------------------------------
@dataclass
class AttackSpec:
    """All tunables for a single melee move."""
    windup_ms: int = 120
    active_ms: int = 180
    recovery_ms: int = 200
    damage: int = 1

    # Hitbox sizes: horizontal (left/right) and vertical (up/down)
    hitbox_w: int = 44
    hitbox_h: int = 24
    hitbox_w_v: int = 24
    hitbox_h_v: int = 44

    # Placement & behavior
    front_gap_px: int = 6                # offset from the player's body
    multi_hit_interval_ms: int = 0       # 0 = once per target per swing

    # Behavior flags
    lock_facing_during_attack: bool = False  # if True, keep facing fixed from start

    @property
    def total_ms(self) -> int:
        return self.windup_ms + self.active_ms + self.recovery_ms


# ------------------------------------------------
# Internal: AttackHitbox (lives across many frames)
# ------------------------------------------------
class AttackHitbox(pygame.sprite.Sprite):
    """
    A persistent collider that follows the owner and only deals damage during
    the 'active' window. It does NOT call enemy.take_damage() directly; instead
    it calls the provided on_hit(attacker, enemy, spec) callback.

    Students may refactor:
    - Collision strategy (rect overlap -> masks or polygons).
    - Hit limits (once per target vs multi-hit every N ms).
    """

    def __init__(
        self,
        owner: pygame.sprite.Sprite,
        enemies: pygame.sprite.Group,
        spec: AttackSpec,
        facing_vec: pygame.Vector2,
        on_hit: Callable[[pygame.sprite.Sprite, pygame.sprite.Sprite, AttackSpec], None],
    ):
        super().__init__()
        self.owner = owner
        self.enemies_group = enemies
        self.spec = spec
        self.on_hit = on_hit

        # Normalize facing to {-1,0,1} per axis (4-way)
        fx = 1 if facing_vec.x > 0 else (-1 if facing_vec.x < 0 else 0)
        fy = 1 if facing_vec.y > 0 else (-1 if facing_vec.y < 0 else 0)
        self.facing = pygame.Vector2(fx, fy)

        # Timing
        self.elapsed = 0
        self.active_start = self.spec.windup_ms
        self.active_end = self.spec.windup_ms + self.spec.active_ms
        self.duration = self.spec.total_ms
        self.active = False

        # Dimensions (horizontal vs vertical)
        if self.facing.y == 0:  # left/right -> horizontal rectangle
            size = (self.spec.hitbox_w, self.spec.hitbox_h)
        else:                    # up/down   -> vertical rectangle
            size = (self.spec.hitbox_w_v, self.spec.hitbox_h_v)

        self.image = pygame.Surface(size, pygame.SRCALPHA)
        self.rect = self.image.get_rect()

        # Track who we've hit (for once-per-target or throttled re-hits)
        self.last_hit_time_by_enemy: dict[pygame.sprite.Sprite, int] = {}

        # Position immediately so callers/tests can inspect location right after spawn
        self._reposition()

    # ---------- helpers ----------
    def _reposition(self) -> None:
        """Place the hitbox just beyond the owner's rect in the facing direction."""
        pr = self.owner.rect
        gap = self.spec.front_gap_px

        if self.facing.x == 1:       # right
            self.rect.midleft = (pr.right + gap, pr.centery)
        elif self.facing.x == -1:    # left
            self.rect.midright = (pr.left - gap, pr.centery)
        elif self.facing.y == -1:    # up
            self.rect.midbottom = (pr.centerx, pr.top - gap)
        elif self.facing.y == 1:     # down
            self.rect.midtop = (pr.centerx, pr.bottom + gap)

    # ---------- core update ----------
    def update(self, dt_ms: int) -> None:
        """
        Advance attack timeline. Only apply hits during the active window.
        The visual is intentionally transparent; the owning game can draw VFX separately.
        """
        self.elapsed += dt_ms
        self._reposition()

        self.active = self.active_start <= self.elapsed < self.active_end

        if self.active:
            # Basic rect-overlap collision; students can refactor later.
            for enemy in pygame.sprite.spritecollide(self, self.enemies_group, False):
                if self.spec.multi_hit_interval_ms <= 0:
                    # Once-per-target per swing (no re-hits allowed this swing)
                    if enemy in self.last_hit_time_by_enemy:
                        continue
                    self.on_hit(self.owner, enemy, self.spec)
                    self.last_hit_time_by_enemy[enemy] = self.elapsed
                else:
                    # Allow re-hits, throttled by interval
                    last_t = self.last_hit_time_by_enemy.get(enemy, -10_000_000)
                    if self.elapsed - last_t >= self.spec.multi_hit_interval_ms:
                        self.on_hit(self.owner, enemy, self.spec)
                        self.last_hit_time_by_enemy[enemy] = self.elapsed

        # End of attack lifespan
        if self.elapsed >= self.duration:
            self.kill()


# ----------------------------------------
# Public: MeleeController (attach to Player)
# ----------------------------------------
class MeleeController:
    """
    A small state machine and hitbox spawner you can attach to a Player-like object.

    Public API you'll use:
        mc = MeleeController(owner, enemies, attack_group, spec, on_hit, get_facing)
        mc.try_start()               # on input (e.g., button pressed)
        mc.update(dt_ms)             # every frame
        mc.is_attacking              # True whenever within the timeline
        mc.phase                     # "idle" | "windup" | "active" | "recovery"

    Design notes:
    - The controller spawns exactly one AttackHitbox per swing and keeps it updated.
    - Damage is delegated via on_hit callback (no direct enemy mutation).
    - Facing is provided by a function so it stays decoupled from input/movement code.
    """

    def __init__(
        self,
        owner: pygame.sprite.Sprite,
        enemies: pygame.sprite.Group,
        attack_group: pygame.sprite.Group,
        spec: Optional[AttackSpec] = None,
        on_hit: Optional[Callable[[pygame.sprite.Sprite, pygame.sprite.Sprite, AttackSpec], None]] = None,
        get_facing: Optional[Callable[[], pygame.Vector2]] = None,
    ):
        self.owner = owner
        self.enemies = enemies
        self.attack_group = attack_group
        self.spec = spec or AttackSpec()
        self.on_hit = on_hit or (lambda attacker, target, spec: None)
        # get_facing should return a Vector2 with components in {-1,0,1}
        self.get_facing = get_facing or (lambda: pygame.Vector2(1, 0))

        # State machine
        self.phase = "idle"   # "idle" | "windup" | "active" | "recovery"
        self.phase_time = 0   # ms in current phase
        self._locked_facing: Optional[pygame.Vector2] = None
        self._hitbox: Optional[AttackHitbox] = None

    # ---------- properties ----------
    @property
    def is_attacking(self) -> bool:
        return self.phase in ("windup", "active", "recovery")

    # ---------- control ----------
    def try_start(self) -> bool:
        """
        Begin an attack if and only if we're idle.
        Returns True if an attack started.
        """
        if self.phase != "idle":
            return False

        self.phase = "windup"
        self.phase_time = 0

        facing_now = self.get_facing()
        if self.spec.lock_facing_during_attack:
            self._locked_facing = pygame.Vector2(
                1 if facing_now.x > 0 else (-1 if facing_now.x < 0 else 0),
                1 if facing_now.y > 0 else (-1 if facing_now.y < 0 else 0),
            )
        else:
            self._locked_facing = None

        # Spawn the hitbox immediately; it won't deal damage until active window.
        hb = AttackHitbox(
            owner=self.owner,
            enemies=self.enemies,
            spec=self.spec,
            facing_vec=self._get_effective_facing(),
            on_hit=self.on_hit,
        )
        self._hitbox = hb
        self.attack_group.add(hb)
        return True

    def update(self, dt_ms: int) -> None:
        """
        Advance the attack state machine and keep the hitbox following.
        Call this once per frame with dt in milliseconds.
        NOTE: We update the hitbox FIRST so it can self-kill and not leave ghost sprites.
        """
        if self.phase == "idle":
            return

        # 1) Update the hitbox first (so it can self-kill at end of lifespan)
        if self._hitbox:
            self._hitbox.facing = self._get_effective_facing()
            self._hitbox.update(dt_ms)

        # 2) Then advance phase timer and handle transitions
        self.phase_time += dt_ms

        if self.phase == "windup" and self.phase_time >= self.spec.windup_ms:
            self.phase = "active"
        elif self.phase == "active" and self.phase_time >= (self.spec.windup_ms + self.spec.active_ms):
            self.phase = "recovery"
        elif self.phase == "recovery" and self.phase_time >= self.spec.total_ms:
            # Safety: ensure any lingering hitbox is removed from groups
            if self._hitbox and self._hitbox.alive():
                self._hitbox.kill()
            self._hitbox = None
            self.phase = "idle"
            self.phase_time = 0
            return

    # ---------- helpers ----------
    def _get_effective_facing(self) -> pygame.Vector2:
        """Locked facing if enabled, else live facing from the provider."""
        return self._locked_facing if self._locked_facing is not None else self.get_facing()


# =============================================================================
# INTEGRATION GUIDE (leave this comment at the bottom of the file for students)
# =============================================================================
# How to integrate melee.py into an existing Pygame project:
#
# 1) Import and construct in your Player (or wherever appropriate)
# ----------------------------------------------------------------
#   from melee import MeleeController, AttackSpec
#
#   class Player(pygame.sprite.Sprite):
#       def __init__(self, enemies: pygame.sprite.Group, attacks: pygame.sprite.Group):
#           ...
#           self.facing = pygame.Vector2(1, 0)   # maintain this in your movement code
#           def get_facing():
#               # Return a 4-way vector with components in {-1,0,1}
#               fx = 1 if self.facing.x > 0 else (-1 if self.facing.x < 0 else 0)
#               fy = 1 if self.facing.y > 0 else (-1 if self.facing.y < 0 else 0)
#               return pygame.Vector2(fx, fy)
#
#           def on_hit(attacker, enemy, spec: AttackSpec):
#               # Your damage logic here (decoupled)
#               if hasattr(enemy, "take_damage"):
#                   enemy.take_damage(spec.damage)
#
#           spec = AttackSpec(
#               windup_ms=120, active_ms=180, recovery_ms=200, damage=1,
#               lock_facing_during_attack=False
#           )
#           self.melee = MeleeController(
#               owner=self, enemies=enemies, attack_group=attacks,
#               spec=spec, on_hit=on_hit, get_facing=get_facing
#           )
#
# 2) Input: start an attack on button press
# -----------------------------------------
#   for event in pygame.event.get():
#       if event.type == pygame.KEYDOWN and event.key == pygame.K_j:
#           self.melee.try_start()
#
# 3) Update each frame (use your dt in milliseconds)
# --------------------------------------------------
#   self.melee.update(dt_ms)
#   attacks.update(dt_ms)  # optional; harmless even though the controller updates current hitbox
#
# 4) Draw your world as usual
# ---------------------------
#   - The controller spawns AttackHitbox sprites into `attacks` group.
#   - You can draw that group for debugging (translucent rectangles) or ignore it
#     and do your own VFX/animation synced to melee.melee.phase/phase_time.
#
# 5) Tips for refactoring exercises
# ---------------------------------
#   - Replace rect collision with a pluggable "collision strategy" (Strategy pattern).
#   - Extract all tunables to AttackSpec (already done), then try different variants
#     (e.g., HeavyAttackSpec with longer windup and more damage).
#   - Add a combo window: allow try_start() during the last N ms of recovery to chain.
#   - Lock facing during attack to teach input buffering and animation syncing.
#
# End of integration guide.
