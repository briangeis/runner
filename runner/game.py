"""The game loop and state machine.

A port of main() in the original, which nested four loops: an outer
title/quit loop, a lives loop, a per-life intro sequence, and the play loop
that ran until shields hit zero.  The mothership fight lived in a loop of its
own that duplicated most of the play loop; here it is a mode within the single
play loop instead, so the two cannot drift apart.
"""

from __future__ import annotations

import math
import sys

import pygame

from . import balance, config, controls, hud, shop, title, transitions
from .assets import banner
from .display import Display
from .enemies import (
    Enemy,
    EnemyField,
    EnemyState,
    Explosion,
    PowerUp,
    apply_powerup,
)
from .font import tech_font
from .mothership import Mothership
from .player import Player
from .shots import EnemyShot, MothershipShot, PlayerShot
from .starfield import Starfield
from .state import GameState

#: Length of the star-only lead-in before each life.
#:
#: The original ran 100 ticks, about 5.5s, and it was the whole of what sat
#: between pressing a key and playing.  The port puts a level card and a
#: fly-in after it, so the same 5.5s became dead air ahead of an announcement:
#: 8.2s before every life, in a game where dying is routine.  A breath of
#: empty space is enough now that something follows it, and the whole opening
#: comes to 3.9s.
STARFIELD_INTRO_SECONDS = 1.2

#: The fly-in raises the ship at 1.5x normal speed, as the original did.
FLY_IN_MULTIPLIER = 1.5

#: Live enemies allowed alongside the boss. The original allowed five.
BOSS_ENEMY_CAP = 5

#: How long the "LEVEL 01" card holds before the ship flies in.
LEVEL_CARD_SECONDS = 1.8


class Game:
    """Owns the window and drives every screen."""

    def __init__(self) -> None:
        # The window must exist before any sprite can be convert_alpha()ed,
        # so the display is built first.
        self.display = Display()
        self.clock = pygame.time.Clock()
        self.state = GameState()
        self._confirmed = False
        #: Transient on-screen message: bounties, power-up pickups, the cheat.
        self.banner = ""
        self.banner_timer = 0.0
        #: Set when the shop is left, which ends the level.
        self.level_complete = False
        self.starfield = Starfield()
        self.player = Player()

        self.enemies = EnemyField()
        self.player_shots: list[PlayerShot] = []
        self.enemy_shots: list[EnemyShot] = []
        self.aimed_shot: MothershipShot | None = None
        self.boss: Mothership | None = None
        #: The mothership's death blast, which has no enemy slot of its own.
        self.blast: Explosion | None = None
        self.portal: shop.Portal | None = None

    # -- top level --------------------------------------------------------

    def run(self) -> int:
        while not self.state.quitting:
            if not title.show(self.display, self.clock):
                break
            if not title.show_controls(self.display, self.clock):
                break

            self.state.reset_for_new_game()
            self._play_session()

            if not self.state.quitting:
                if not self._game_over():
                    break
        return 0

    def _play_session(self) -> None:
        """One game: levels loop until the lives run out.

        A level is the full cycle the original never assembled: starfield,
        level card, the ship flying in, play until the mothership is lured out
        and destroyed, then the shop.  Leaving the shop starts the next level.
        Dying costs a ship and restarts the same level.
        """
        while self.state.lives > 0 and not self.state.quitting:
            self._reset_round()
            if not self._starfield_intro():
                return
            if not self._level_card():
                return
            if not self._fly_in():
                return

            completed = self._play()
            if self.state.quitting:
                return

            if completed:
                self.state.level += 1
                # Not reset_for_new_life: finishing a level must not refill
                # shields, or the shop shelf the player just paid for is
                # refunded to everyone for free a second later.
                self.state.reset_for_new_level()
                continue

            if not transitions.whiten(self.display, self.clock):
                self.state.quitting = True
                return

            self.state.lives -= 1
            if self.state.lives > 0:
                self.state.reset_for_new_life()

    def _level_card(self) -> bool:
        """Announce the level over the starfield before the ship arrives."""
        font = tech_font()
        elapsed = 0.0
        while elapsed < LEVEL_CARD_SECONDS:
            delta = self._tick()
            elapsed += delta
            if not self._pump():
                return False
            self.starfield.update(delta)
            self.display.clear()
            self.starfield.draw(self.display.buffer)
            font.draw_centered(
                self.display.buffer,
                config.SCREEN_HEIGHT // 2 - 4,
                f"LEVEL {self.state.level:02d}",
            )
            hud.draw(self.display.buffer, self.state)
            self.display.present()
        return True

    def _reset_round(self) -> None:
        self.enemies.clear()
        self.player_shots.clear()
        self.enemy_shots.clear()
        self.aimed_shot = None
        self.boss = None
        self.blast = None
        self.portal = None

    # -- per-life intro ---------------------------------------------------

    def _starfield_intro(self) -> bool:
        elapsed = 0.0
        while elapsed < STARFIELD_INTRO_SECONDS:
            delta = self._tick()
            elapsed += delta
            if not self._pump():
                return False
            self.starfield.update(delta)
            self.display.clear()
            self.starfield.draw(self.display.buffer)
            hud.draw(self.display.buffer, self.state)
            self.display.present()
        return True

    def _fly_in(self) -> bool:
        """Bring the ship up from below the screen to its starting position."""
        self.player.x = float((config.SCREEN_WIDTH - self.player.width) // 2)
        self.player.y = float(config.SCREEN_HEIGHT)
        target = float((config.SCREEN_HEIGHT - self.player.height) // 2)

        speed = balance.PLAYER_SPEED_PX_S * FLY_IN_MULTIPLIER
        while self.player.y > target:
            delta = self._tick()
            if not self._pump():
                return False
            self.player.y = max(target, self.player.y - speed * delta)
            self.player.animate_idle(delta)
            self.starfield.update(delta)

            self.display.clear()
            self.starfield.draw(self.display.buffer)
            self.player.draw(self.display.buffer, self.state)
            hud.draw(self.display.buffer, self.state)
            self.display.present()
        return True

    # -- the play loop ----------------------------------------------------

    def _play(self) -> bool:
        """Run one level. True if it was completed, False if the ship died."""
        self.level_complete = False
        while not self.state.dead and not self.state.quitting:
            delta = self._tick()
            if not self._pump():
                return False

            self.banner_timer = max(0.0, self.banner_timer - delta)
            self.state.tick_timers(delta)
            self._update_entities(delta)
            self._resolve_collisions()
            self._advance_encounters(delta)
            if self.level_complete:
                return True
            self._draw_play()
        return False

    def _update_entities(self, delta: float) -> None:
        input_state = controls.read()
        self.player_shots.extend(
            self.player.update(self.state, input_state, delta)
        )
        # Enforce the bolt cap the original tracked as MAX_SHOTS.
        if len(self.player_shots) > self.state.max_shots:
            del self.player_shots[: len(self.player_shots) - self.state.max_shots]

        for shot in self.player_shots:
            shot.update(delta)
        self.player_shots = [shot for shot in self.player_shots if shot.alive]

        live_cap = BOSS_ENEMY_CAP if self.boss else None
        self._admit_enemy_shots(
            self.enemies.update(delta, self.state, live_cap=live_cap)
        )

        for shot in self.enemy_shots:
            shot.update(delta)
        self.enemy_shots = [shot for shot in self.enemy_shots if shot.alive]

        if self.aimed_shot is not None:
            self.aimed_shot.update(delta)
            if not self.aimed_shot.alive:
                self.aimed_shot = None

        if self.blast is not None:
            self.blast.update(delta)
            if not self.blast.alive:
                self.blast = None

        self.starfield.update(delta)

    def _admit_enemy_shots(self, bolts: list[EnemyShot]) -> None:
        """Add what fits under the shared enemy-fire cap and drop the rest.

        The boss and the regular enemies draw on the same six slots, so both
        go through here, so the cap means the same thing to both.
        """
        room = balance.MAX_ENEMY_SHOTS - len(self.enemy_shots)
        if room > 0:
            self.enemy_shots.extend(bolts[:room])

    @staticmethod
    def _already_hit(shot: PlayerShot, target: Enemy | Mothership) -> bool:
        """Whether this target has already taken damage from this volley.

        Without this, a triple shot lands all three bolts inside the 47px
        mothership for triple damage, which made her trivial once upgraded.
        Capping it at one keeps weapon tier as the damage stat and shot count
        as the coverage stat, and three bolts can still hit three *different*
        enemies. Bolts remain strictly vertical, so hitting anything still
        means flying underneath it.

        The marker lives on the target itself, so a slot that is recycled
        into a fresh enemy cannot inherit the immunity of the one before it.
        """
        if target.last_volley == shot.volley_id:
            return True
        target.last_volley = shot.volley_id
        return False

    def _resolve_collisions(self) -> None:
        player_box = self.player.hitbox

        # Player bolts against enemies.
        for shot in self.player_shots:
            if not shot.alive:
                continue
            for enemy in self.enemies:
                if enemy.state is not EnemyState.LIVE:
                    continue
                if shot.rect.colliderect(enemy.hitbox):
                    shot.alive = False
                    if self._already_hit(shot, enemy):
                        break
                    # Weapon tier is the damage, so upgrades shorten every
                    # fight rather than only the boss's.
                    if enemy.take_hit(shot.weapon):
                        enemy.explode()
                        self.state.score += balance.enemy_score(enemy.type.index)
                    break

        # Player bolts against the boss.
        if self.boss is not None:
            for shot in self.player_shots:
                if shot.alive and shot.rect.colliderect(self.boss.hitbox):
                    shot.alive = False
                    if self._already_hit(shot, self.boss):
                        continue
                    if self.boss.hit(shot.weapon):
                        self._boss_defeated()
                        break
        self.player_shots = [shot for shot in self.player_shots if shot.alive]

        # Enemies and power-ups against the player.
        for enemy in self.enemies:
            if not enemy.hitbox.colliderect(player_box):
                continue
            if enemy.state is EnemyState.LIVE:
                enemy.explode()
                self.state.damage()
            elif enemy.state is EnemyState.POWER:
                enemy.state = EnemyState.DEAD
                if enemy.power is not None:
                    before_money, before_score = self.state.money, self.state.score
                    granted = apply_powerup(self.state, enemy.power)
                    gained = max(
                        self.state.money - before_money,
                        self.state.score - before_score,
                    )
                    self._announce_powerup(granted, gained)

        # Enemy fire against the player.
        for shot in self.enemy_shots:
            if shot.alive and shot.rect.colliderect(player_box):
                shot.alive = False
                self.state.damage()
        self.enemy_shots = [shot for shot in self.enemy_shots if shot.alive]

        if self.aimed_shot is not None and self.aimed_shot.rect.colliderect(
            player_box
        ):
            self.aimed_shot = None
            if not self.state.invincible:
                self.state.kill()

        # Flying into her is fatal, and shields do not soften it. Ramming an
        # ordinary enemy destroys it and costs a shield, which is a trade; she
        # is forty-seven pixels of capital ship and there is no trade to make.
        #
        # Invincibility answers this exactly as it answers the killshot above.
        # Anything else would leave brushing her hull deadlier than the attack
        # she spends the best part of two seconds lining up.
        if (
            self.boss is not None
            and not self.state.invincible
            and self.boss.hitbox.colliderect(player_box)
        ):
            self.state.kill()

    def _advance_encounters(self, delta: float) -> None:
        """Trigger the boss, then the shop, in the order the original did."""
        if (
            self.boss is None
            and not self.state.shop_visible
            and self.state.kills >= balance.KILLS_FOR_BOSS
        ):
            self._summon_boss()

        if self.boss is not None:
            bolts, aimed = self.boss.update(delta, self.player.rect)
            self._admit_enemy_shots(bolts)
            if aimed is not None and self.aimed_shot is None:
                self.aimed_shot = aimed

        if self.portal is not None:
            self.portal.update(delta)
            if self.portal.accepts(self.player.rect):
                self._enter_shop()

    def _summon_boss(self) -> None:
        self.state.mothership_active = True
        # She detonates the spaceships only. Asteroids are indifferent to
        # her, and a power-up already earned should not be confiscated.
        self.enemies.explode_all(spaceships_only=True)
        # Each boss beaten this game makes the next one tougher.
        self.boss = Mothership(self.state.bosses_beaten)

    def _boss_defeated(self) -> None:
        wreck = self.boss.rect if self.boss is not None else None
        self.boss = None
        # Pay a bounty before incrementing, so the first boss pays the base.
        # The original paid nothing, leaving drops as the only income.
        self.state.score += balance.boss_score(self.state.bosses_beaten)
        bounty = balance.boss_reward(self.state.bosses_beaten)
        if bounty:
            self.state.money += bounty
            self.banner = f"BOUNTY {bounty}"
            self.banner_timer = 2.0
        self.state.bosses_beaten += 1
        self.state.mothership_active = False
        # Her bolts outlive her, as they did in the original: a won fight can
        # still kill you, which was always the funnier outcome.
        # Progress toward the next one starts fresh.  This is also what keeps
        # her from being summoned again the instant self.boss goes None, so it
        # has to happen here rather than on the way in.
        self.state.kills = 0
        self.enemies.explode_all()
        # Every ship dies in an explosion; hers is simply a different one.
        # The artwork carries the same animation twice, and the red copy
        # exists because a green blast looked wrong coming off a green
        # mothership.
        if wreck is not None:
            self.blast = Explosion(wreck, "explosion_alt")
        self.state.shop_visible = True
        self.portal = shop.Portal()

    def _enter_shop(self) -> None:
        """Visit the shop, which ends the level.

        The original dropped the player straight back into the same endless
        round. Ending the level here is what closes the loop: the next one
        starts over with its starfield, card and fly-in.
        """
        # Invincibility ends here rather than at her death, since she can
        # still land a parting shot. Carrying it into the shop would make
        # shield purchases a guess.
        self.state.invincible = False
        self.state.invincible_timer = 0.0

        # Fade the ship and portal out but leave the sky running; it is the
        # same sky the next level opens on.
        if not transitions.fade_sprites(self.display, self.clock, self.starfield):
            self.state.quitting = True
            return

        if not shop.run(self.display, self.clock, self.state, self.starfield):
            return

        self.state.shop_visible = False
        self.portal = None
        self.level_complete = True

    def _draw_play(self) -> None:
        self.display.clear()
        self.starfield.draw(self.display.buffer)

        if self.aimed_shot is not None:
            self.aimed_shot.draw(self.display.buffer)
        self.enemies.draw(self.display.buffer)
        for shot in self.player_shots:
            shot.draw(self.display.buffer)
        for shot in self.enemy_shots:
            shot.draw(self.display.buffer)
        if self.portal is not None:
            self.portal.draw(self.display.buffer)
        self.player.draw(self.display.buffer, self.state)
        if self.boss is not None:
            self.boss.draw(self.display.buffer)
        if self.blast is not None:
            self.blast.draw(self.display.buffer)

        hud.draw(self.display.buffer, self.state)
        self._draw_banner()
        self.display.present()

    def _draw_banner(self) -> None:
        if self.banner_timer <= 0.0:
            return
        tech_font().draw_centered(
            self.display.buffer, config.SCREEN_HEIGHT - 14, self.banner
        )

    # -- game over --------------------------------------------------------

    def _game_over(self) -> bool:
        font = tech_font()
        elapsed = 0.0

        while True:
            delta = self._tick()
            elapsed += delta
            if not self._pump():
                return False
            if elapsed > 0.75 and self._confirmed:
                return True

            self.starfield.update(delta)
            self.display.clear()
            self.starfield.draw(self.display.buffer)

            middle = config.SCREEN_HEIGHT // 2
            font.draw_centered(self.display.buffer, middle - 30, "GAME OVER")
            font.draw_centered(
                self.display.buffer,
                middle - 10,
                f"FINAL SCORE {self.state.score:06d}",
            )
            if int(elapsed * 2) % 2 == 0:
                font.draw_centered(self.display.buffer, middle + 20, "PRESS ANY KEY")
            self.display.present()

    # -- plumbing ---------------------------------------------------------

    def _tick(self) -> float:
        return self.clock.tick(config.TARGET_FPS) / 1000.0

    def _pump(self) -> bool:
        """Drain the event queue. Returns False if the window was closed."""
        self._confirmed = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.state.quitting = True
                return False
            if event.type == pygame.VIDEORESIZE:
                self.display.handle_resize(event.size)
            controls.handle_device_event(event)

            intent = controls.intent_of(event)
            if intent is controls.Intent.QUIT:
                self.state.quitting = True
                return False
            if intent is controls.Intent.FULLSCREEN:
                self.display.toggle_fullscreen()
            elif intent is controls.Intent.CHEAT and config.ENABLE_DEBUG_CHEAT:
                self._apply_cheat()
            elif controls.dismisses(intent):
                self._confirmed = True
        return True

    #: What each power-up says when collected. The original showed nothing at
    #: all, so a rare upgrade was indistinguishable from a points pickup.
    POWERUP_LABELS = {
        "SHIELD": "SHIELDS RESTORED",
        "INVINCIBLE": "INVINCIBLE",
        "EXTRA_SHIP": "EXTRA SHIP",
    }

    #: Upgrade tracks, mapped to the name the shop files them under, so a
    #: drop and the shelf selling the same thing announce the same words.
    _TIER_TRACKS = {
        "WEAPON": "WEAPON",
        "SHOT": "SHOT",
        "FIRE_RATE": "FIRE RATE",
    }

    def _announce_powerup(self, power: PowerUp, amount: int = 0) -> None:
        name = power.name
        if name in self._TIER_TRACKS:
            tier = {
                "WEAPON": self.state.curr_weapon,
                "SHOT": self.state.shot_tier,
                "FIRE_RATE": self.state.fire_tier,
            }[name]
            label = shop.tier_label(self._TIER_TRACKS[name], tier)
        elif name == "POINTS":
            label = f"+{amount} POINTS"
        elif name == "MONEY":
            label = f"+{amount} MONEY"
        else:
            label = self.POWERUP_LABELS.get(name, name)
        self.banner = label
        self.banner_timer = 1.4

    def _apply_cheat(self) -> None:
        """The original's P key: toggle invincibility and hand over $1000."""
        if self.state.invincible:
            self.state.invincible = False
            self.state.invincible_timer = 0.0
            self.banner = "CHEAT OFF"
        else:
            # Endless, unlike the power-up: the cheat exists to sit in a
            # fight and watch it, which a timer keeps interrupting.
            self.state.grant_invincibility(math.inf)
            self.state.money += config.DEBUG_CHEAT_MONEY
            self.banner = f"CHEAT ON  +{config.DEBUG_CHEAT_MONEY}"
        self.banner_timer = 1.4


def main() -> int:
    pygame.init()
    controls.init()
    pygame.display.set_caption(config.WINDOW_TITLE)
    try:
        return Game().run()
    finally:
        pygame.quit()
        _print_banner()


def _print_banner() -> None:
    """Print the exit banner, as the original did on returning to DOS.

    Only when stdout is a terminal. Launched from a desktop shortcut there
    may be no console attached, and on Windows writing to a detached stdout
    can raise.
    """
    if not sys.stdout or not sys.stdout.isatty():
        return
    art = banner()
    if art:
        print(art)
