# Event Type Taxonomy

This taxonomy is built for LLM-based event extraction, normalization, scoring, and episode summarization.

## Event Groups

1. `setup`
2. `goal_progress`
3. `conflict`
4. `revelation`
5. `relationship`
6. `status_shift`
7. `resource_gain_loss`
8. `scheme_intrigue`
9. `emotion_romance`
10. `world_rule`
11. `transition`
12. `climax_resolution`

## Full Event Type List

```text
setup.introduction
setup.foreshadowing
setup.mission_assigned
setup.threat_introduced
setup.new_character_entry
setup.new_location_entry
setup.background_exposition

goal_progress.goal_set
goal_progress.goal_change
goal_progress.plan_made
goal_progress.plan_adjusted
goal_progress.clue_found
goal_progress.obstacle_removed
goal_progress.stage_advance

conflict.verbal_clash
conflict.physical_battle
conflict.chase_escape
conflict.competition
conflict.confrontation
conflict.siege_attack
conflict.crisis_outbreak
conflict.survival_crisis

revelation.identity_reveal
revelation.secret_exposed
revelation.truth_discovered
revelation.misunderstanding_formed
revelation.misunderstanding_cleared
revelation.hidden_motive_revealed
revelation.memory_reveal
revelation.lineage_reveal
revelation.traitor_exposed

relationship.alliance_formed
relationship.alliance_broken
relationship.trust_gained
relationship.trust_lost
relationship.master_disciple_bond
relationship.friendship_deepen
relationship.friendship_break
relationship.family_tension
relationship.reconciliation
relationship.betrayal

status_shift.rank_up
status_shift.rank_down
status_shift.power_gain
status_shift.power_loss
status_shift.faction_change
status_shift.leadership_change
status_shift.public_reputation_rise
status_shift.public_reputation_fall
status_shift.political_favor_gain
status_shift.political_favor_loss
status_shift.social_status_change

resource_gain_loss.item_obtained
resource_gain_loss.item_lost
resource_gain_loss.inheritance_obtained
resource_gain_loss.technique_obtained
resource_gain_loss.breakthrough
resource_gain_loss.power_unlocked
resource_gain_loss.power_sealed
resource_gain_loss.injury
resource_gain_loss.healing
resource_gain_loss.territory_gain
resource_gain_loss.territory_loss
resource_gain_loss.information_gain
resource_gain_loss.information_loss

scheme_intrigue.scheme_started
scheme_intrigue.scheme_progressed
scheme_intrigue.scheme_executed
scheme_intrigue.scheme_failed
scheme_intrigue.counter_scheme
scheme_intrigue.test_probe
scheme_intrigue.framed
scheme_intrigue.exonerated
scheme_intrigue.evidence_secured
scheme_intrigue.evidence_destroyed
scheme_intrigue.blackmail
scheme_intrigue.negotiation

emotion_romance.first_interest
emotion_romance.affection_grow
emotion_romance.ambiguity_increase
emotion_romance.jealousy_triggered
emotion_romance.care_shown
emotion_romance.confession
emotion_romance.rejection
emotion_romance.relationship_confirmed
emotion_romance.relationship_hidden
emotion_romance.breakup
emotion_romance.reunion
emotion_romance.rival_appears

world_rule.rule_introduced
world_rule.rule_confirmed
world_rule.rule_broken
world_rule.prophecy_hint
world_rule.legend_revealed
world_rule.organization_lore
world_rule.realm_lore
world_rule.system_rule_update

transition.travel
transition.training
transition.rest
transition.time_skip
transition.relocation
transition.aftermath
transition.preparation
transition.observation

climax_resolution.turning_point
climax_resolution.payoff
climax_resolution.victory
climax_resolution.defeat
climax_resolution.stalemate
climax_resolution.escape_success
climax_resolution.escape_failure
climax_resolution.sacrifice
climax_resolution.phase_end
climax_resolution.new_arc_hook
```

## High-Value Event Types

Prioritize these in episodic compression:

```text
goal_progress.goal_change
revelation.identity_reveal
revelation.secret_exposed
revelation.traitor_exposed
relationship.alliance_formed
relationship.betrayal
status_shift.faction_change
status_shift.rank_up
status_shift.public_reputation_rise
resource_gain_loss.breakthrough
resource_gain_loss.inheritance_obtained
resource_gain_loss.power_unlocked
scheme_intrigue.scheme_executed
scheme_intrigue.counter_scheme
scheme_intrigue.framed
scheme_intrigue.exonerated
emotion_romance.confession
emotion_romance.relationship_confirmed
emotion_romance.breakup
emotion_romance.rival_appears
climax_resolution.turning_point
climax_resolution.victory
climax_resolution.defeat
climax_resolution.payoff
climax_resolution.new_arc_hook
```

## Usually Low-Value Event Types

Keep only when they materially affect later events:

```text
setup.new_location_entry
setup.background_exposition
transition.travel
transition.rest
transition.preparation
transition.observation
transition.training
conflict.verbal_clash
emotion_romance.care_shown
world_rule.organization_lore
world_rule.realm_lore
```

## Genre-Specific Priorities

### Xianxia / Xuanhuan

```text
resource_gain_loss.breakthrough
resource_gain_loss.technique_obtained
resource_gain_loss.inheritance_obtained
status_shift.rank_up
status_shift.faction_change
revelation.lineage_reveal
conflict.physical_battle
climax_resolution.turning_point
climax_resolution.new_arc_hook
```

### Palace / Intrigue

```text
scheme_intrigue.scheme_started
scheme_intrigue.scheme_executed
scheme_intrigue.counter_scheme
scheme_intrigue.framed
scheme_intrigue.exonerated
scheme_intrigue.evidence_secured
status_shift.political_favor_gain
status_shift.political_favor_loss
relationship.alliance_formed
relationship.betrayal
revelation.traitor_exposed
```

### Romance

```text
emotion_romance.first_interest
emotion_romance.affection_grow
emotion_romance.ambiguity_increase
emotion_romance.jealousy_triggered
emotion_romance.confession
emotion_romance.relationship_confirmed
emotion_romance.breakup
emotion_romance.reunion
emotion_romance.rival_appears
revelation.misunderstanding_formed
revelation.misunderstanding_cleared
```

### Mystery / Investigation

```text
goal_progress.clue_found
revelation.truth_discovered
revelation.secret_exposed
revelation.hidden_motive_revealed
revelation.traitor_exposed
scheme_intrigue.test_probe
scheme_intrigue.evidence_secured
climax_resolution.payoff
climax_resolution.turning_point
```

### Survival / Unlimited Flow

```text
conflict.survival_crisis
goal_progress.goal_set
goal_progress.stage_advance
resource_gain_loss.item_obtained
resource_gain_loss.information_gain
relationship.alliance_formed
relationship.betrayal
world_rule.rule_introduced
world_rule.rule_confirmed
world_rule.rule_broken
climax_resolution.escape_success
climax_resolution.escape_failure
```

## Priority Rule for Multi-Label Candidates

When an event could match multiple labels, choose the one that most changes the story state:

```text
climax_resolution
> revelation
> status_shift
> relationship
> resource_gain_loss
> scheme_intrigue
> goal_progress
> conflict
> emotion_romance
> world_rule
> setup
> transition
```

## Extraction Constraints

Use these rules in prompts:

```text
1. Each event must choose exactly one primary event_type.
2. Prefer the label that captures the state change, not the action process.
3. If the scene mostly plants future payoff, use setup.foreshadowing.
4. If the core result is a relationship change, do not label it as emotion_romance unless the emotional progression itself is the main outcome.
5. If both a reveal and a victory happen, choose the more consequential one for downstream understanding.
```

## Recommended Output Shape

```json
{
  "event_id": "ev_001",
  "event_group": "revelation",
  "event_type": "revelation.identity_reveal",
  "title": "Female lead learns the male lead's true identity",
  "description": "She discovers he is not an ordinary disciple but the hidden heir of the sect.",
  "importance": 5,
  "participants": ["male_lead", "female_lead"],
  "cause": "An assassination forced him to reveal his strength",
  "consequence": "Their relationship and sect alignments both shift",
  "must_keep": true
}
```

## Minimal Subset

If you want a smaller first-pass taxonomy, start with:

```text
setup.foreshadowing
setup.new_character_entry
goal_progress.goal_change
goal_progress.clue_found
conflict.physical_battle
conflict.confrontation
revelation.identity_reveal
revelation.secret_exposed
revelation.truth_discovered
revelation.misunderstanding_formed
revelation.misunderstanding_cleared
relationship.alliance_formed
relationship.betrayal
relationship.reconciliation
status_shift.rank_up
status_shift.faction_change
status_shift.public_reputation_rise
resource_gain_loss.breakthrough
resource_gain_loss.item_obtained
scheme_intrigue.scheme_executed
scheme_intrigue.counter_scheme
emotion_romance.confession
emotion_romance.relationship_confirmed
climax_resolution.turning_point
climax_resolution.victory
climax_resolution.defeat
climax_resolution.new_arc_hook
```
