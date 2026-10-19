from __future__ import annotations

from enum import StrEnum

from football_manager.domain import MatchSnapshot
from football_manager.simulation import MatchEvent, MatchEventType, RestartType, TeamSide


class CommentaryDensity(StrEnum):
    HIGHLIGHTS = "highlights"
    NORMAL = "normal"
    DETAILED = "detailed"


class CommentaryFormatter:
    """Turn structured match events into deterministic Spanish commentary."""

    def __init__(
        self,
        snapshot: MatchSnapshot,
        *,
        density: CommentaryDensity = CommentaryDensity.DETAILED,
    ) -> None:
        self.snapshot = snapshot
        self.density = CommentaryDensity(density)
        self._names: dict[str, str] = {}
        self._team_names = {
            TeamSide.HOME: snapshot.home_team.club_short_name,
            TeamSide.AWAY: snapshot.away_team.club_short_name,
        }
        self._pending_pass_action: dict[str, str] = {}
        for side, team in (
            (TeamSide.HOME, snapshot.home_team),
            (TeamSide.AWAY, snapshot.away_team),
        ):
            for player in team.starters + team.bench:
                agent_id = f"{side.value}:{player.player_id}"
                display = player.full_name.strip()
                if display.lower().startswith("player ") and player.assigned_slot_id:
                    display = f"{team.club_short_name} {player.assigned_slot_id.upper()}"
                self._names[agent_id] = display

    def set_density(self, density: CommentaryDensity | str) -> None:
        self.density = CommentaryDensity(density)

    def format_event(self, event: MatchEvent) -> str | None:
        if event.event_type is MatchEventType.PASS and event.value("status") == "attempt":
            if event.actor_agent_id is not None:
                self._pending_pass_action[event.actor_agent_id] = event.value("action") or "pass"
            return None

        message = self._message(event)
        if message is None:
            return None
        return f"{event.time_label:>6}  {message}"

    def _message(self, event: MatchEvent) -> str | None:
        t = event.event_type
        actor = self._player(event.actor_agent_id)
        secondary = self._player(event.secondary_agent_id)

        if t is MatchEventType.MATCH_START:
            return "Comienza el partido."
        if t is MatchEventType.PERIOD_START:
            if event.phase.value == "first_half":
                return "Rueda la pelota."
            if event.phase.value == "second_half":
                return "Comienza el segundo tiempo."
            if event.phase.value == "extra_time_first_half":
                return "Comienza el primer tiempo del alargue."
            if event.phase.value == "extra_time_second_half":
                return "Comienza el segundo tiempo del alargue."
            return "Se reanuda el juego."
        if t is MatchEventType.ADDED_TIME:
            seconds = int(float(event.value("seconds") or 0))
            minutes = max(1, round(seconds / 60))
            return f"Se adicionan {minutes} minuto{'s' if minutes != 1 else ''}."
        if t is MatchEventType.HALF_TIME:
            return "Final del período."
        if t is MatchEventType.EXTRA_TIME:
            return "Habrá alargue."
        if t is MatchEventType.PENALTY_SHOOTOUT:
            return "La definición se va a los penales."
        if t is MatchEventType.MATCH_END:
            return "Final del partido."

        if t is MatchEventType.PASS:
            return self._pass_message(event, actor, secondary)

        if t is MatchEventType.CARRY:
            if event.value("outcome") is None:
                return None
            if not self._routine(event, detailed_divisor=3, normal_divisor=9):
                return None
            if event.value("outcome") == "completed":
                return self._variant(
                    event,
                    f"{actor} conduce y gana metros.",
                    f"{actor} avanza con la pelota controlada.",
                    f"{actor} progresa en conducción.",
                )
            return f"{actor} pierde el control durante la conducción."

        if t is MatchEventType.RECOVERY:
            if not self._routine(event, detailed_divisor=3, normal_divisor=7):
                return None
            return self._variant(
                event,
                f"{actor} recupera la posesión.",
                f"{actor} gana la segunda pelota.",
                f"{actor} corta y vuelve a darle la pelota a su equipo.",
            )

        if t is MatchEventType.DRIBBLE:
            if self.density is CommentaryDensity.HIGHLIGHTS and (
                event.value("outcome") != "beats_defender" or event.sequence % 4 != 0
            ):
                return None
            outcome = event.value("outcome")
            if outcome == "beats_defender":
                return f"{actor} supera a {secondary} en el uno contra uno."
            if outcome == "defender_wins":
                return f"{secondary} le gana el duelo a {actor}."
            return f"Duelo entre {actor} y {secondary}: la pelota queda dividida."

        if t is MatchEventType.CROSS:
            if event.value("status") == "attempt":
                return None
            outcome = event.value("outcome")
            if self.density is CommentaryDensity.HIGHLIGHTS and event.sequence % 3 != 0:
                return None
            if outcome == "completed":
                return f"{actor} mete el centro y encuentra a {secondary}."
            if outcome == "intercepted":
                return f"{secondary} corta el centro de {actor}."
            if self.density is CommentaryDensity.HIGHLIGHTS:
                return None
            return f"El centro de {actor} no encuentra destinatario."

        if t is MatchEventType.SHOT:
            xg = self._float(event.value("xg"))
            suffix = f" (xG {xg:.2f})" if xg is not None else ""
            return self._variant(
                event,
                f"¡{actor} remata!{suffix}",
                f"{actor} prueba al arco.{suffix}",
                f"Llega el disparo de {actor}.{suffix}",
            )

        if t is MatchEventType.GOAL:
            xg = self._float(event.value("xg"))
            suffix = f" xG {xg:.2f}." if xg is not None else ""
            return f"¡GOOOOOOOOOOOL DE {actor.upper()}!{suffix}"

        if t is MatchEventType.SAVE:
            return f"¡Ataja {actor}! Le niega el gol a {secondary}."
        if t is MatchEventType.BLOCK:
            return f"{actor} bloquea el remate de {secondary}."
        if t is MatchEventType.WOODWORK:
            return f"¡Al palo! {actor} estuvo muy cerca."
        if t is MatchEventType.OFF_TARGET:
            return f"{actor} remata desviado."

        if t is MatchEventType.TACKLE:
            if self.density is CommentaryDensity.HIGHLIGHTS:
                return None
            outcome = event.value("outcome")
            if outcome == "defender_control":
                return f"{actor} entra limpio sobre {secondary} y recupera."
            if outcome == "attacker_retains":
                return f"{secondary} resiste la entrada de {actor} y sigue con la pelota."
            return f"{actor} disputa la pelota con {secondary}; queda suelta."

        if t is MatchEventType.FOUL:
            if self.density is CommentaryDensity.HIGHLIGHTS and event.value("penalty_area") != "true":
                return None
            if event.value("advantage") == "true":
                return f"Falta de {actor} sobre {secondary}, pero el árbitro da ventaja."
            return f"Falta de {actor} sobre {secondary}."

        if t is MatchEventType.CARD:
            card = event.value("card")
            if card == "yellow":
                return f"Amarilla para {actor}."
            if card == "second_yellow_red":
                return f"Segunda amarilla y expulsión para {actor}."
            if card == "red":
                return f"¡Roja directa para {actor}!"
            return f"Tarjeta para {actor}."

        if t is MatchEventType.PENALTY_AWARDED:
            side = self._team(event.side)
            return f"¡PENAL PARA {side}!"

        if t is MatchEventType.PENALTY_KICK:
            scored = event.value("scored") == "true"
            shootout = event.value("shootout") == "true"
            if shootout:
                return f"Penal de {actor}: {'GOL' if scored else 'ATAJADO / ERRADO'}."
            return f"{actor} ejecuta el penal: {'gol' if scored else 'no convierte'}."

        if t is MatchEventType.SUBSTITUTION:
            return f"Cambio en {self._team(event.side)}: sale {actor}, entra {secondary}."

        if t is MatchEventType.TACTICAL_CHANGE:
            return f"{self._team(event.side)} cambia el plan: {event.value('label') or 'ajuste táctico'}."

        if t is MatchEventType.RESTART:
            return self._restart_message(event, actor)

        return None

    def _pass_message(self, event: MatchEvent, actor: str, secondary: str) -> str | None:
        outcome = event.value("outcome")
        if outcome is None:
            return None
        action = self._pending_pass_action.pop(event.actor_agent_id or "", "pass")
        if outcome == "completed":
            if not self._routine(event, detailed_divisor=4, normal_divisor=12):
                return None
            if action == "progressive_pass":
                return f"{actor} rompe una línea con un pase hacia {secondary}."
            if action in {"long_pass", "clearance"}:
                return f"{actor} cambia en largo y encuentra a {secondary}."
            return self._variant(
                event,
                f"{actor} toca para {secondary}.",
                f"{actor} encuentra a {secondary}.",
                f"{actor} asegura la posesión con {secondary}.",
            )
        if outcome == "intercepted":
            if self.density is CommentaryDensity.HIGHLIGHTS and event.sequence % 8 != 0:
                return None
            return f"{secondary} intercepta el pase de {actor}."
        if outcome == "bad_control":
            if self.density is CommentaryDensity.HIGHLIGHTS:
                if event.sequence % 10 != 0:
                    return None
            elif not self._routine(event, detailed_divisor=3, normal_divisor=8):
                return None
            if event.secondary_agent_id is None:
                return f"El receptor no logra controlar el pase de {actor}."
            return f"{secondary} no puede controlar el pase de {actor}."
        if self.density is CommentaryDensity.HIGHLIGHTS:
            if event.sequence % 10 != 0:
                return None
        elif not self._routine(event, detailed_divisor=4, normal_divisor=10):
            return None
        return f"{actor} entrega mal y pierde la pelota."

    def _restart_message(self, event: MatchEvent, actor: str) -> str | None:
        restart = event.restart_type
        side = self._team(event.side)
        if restart is RestartType.CORNER:
            return f"Córner para {side}. Lo ejecuta {actor}."
        if restart is RestartType.FREE_KICK:
            return f"Tiro libre para {side}."
        if restart is RestartType.GOAL_KICK:
            if self.density is CommentaryDensity.HIGHLIGHTS:
                return None
            return f"Saque de arco para {side}."
        if restart is RestartType.THROW_IN:
            if not self._routine(event, detailed_divisor=8, normal_divisor=30):
                return None
            return f"Lateral para {side}."
        if restart is RestartType.KICKOFF:
            return None
        return None

    def _routine(self, event: MatchEvent, *, detailed_divisor: int, normal_divisor: int) -> bool:
        if self.density is CommentaryDensity.HIGHLIGHTS:
            return False
        divisor = detailed_divisor if self.density is CommentaryDensity.DETAILED else normal_divisor
        return event.sequence % divisor == 0

    @staticmethod
    def _variant(event: MatchEvent, *variants: str) -> str:
        return variants[event.sequence % len(variants)]

    def _player(self, agent_id: str | None) -> str:
        if agent_id is None:
            return "un jugador"
        return self._names.get(agent_id, agent_id)

    def _team(self, side: TeamSide | None) -> str:
        if side is None:
            return "el equipo"
        return self._team_names[TeamSide(side)]

    @staticmethod
    def _float(value: str | None) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except ValueError:
            return None
