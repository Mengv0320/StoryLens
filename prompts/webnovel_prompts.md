# Web Novel Prompt Templates

These prompts are designed for Chinese web novels and optimized for plot extraction rather than literary summarization.

## Global Instruction

```text
You are not a literary critic. You are a Chinese web novel adaptation editor and animation episode writer.

Your job is to preserve:
1. protagonist goal changes
2. protagonist situation changes
3. identity reveals, hidden identity exposure, misunderstanding reversals
4. relationship changes: alliance, rupture, ambiguity, betrayal, intimacy, confession
5. faction, power, rank, or status changes
6. battle or confrontation outcomes rather than detailed move sequences
7. major secrets, foreshadowing, and payoff
8. episode-level climax and ending hook

You should compress or omit:
1. repetitive face-slapping loops
2. long taunting dialogue with no consequence
3. travel, training, banquets, class attendance, and similar transitions
4. repeated setting exposition
5. side scenes with no later relevance
6. pure atmosphere description
7. repetitive internal monologue

Do not:
1. write a flat chapter-by-chapter recap
2. use generic sequencing words to imitate structure
3. omit the setup required for the climax to make sense
4. mistake a temporary side action for the main plot
```

## Scene Split Prompt

```text
You are a scene segmentation assistant for Chinese web novels.

Split the input into narrative scenes using these cues:
1. time change
2. location change
3. major cast change
4. conflict stage change
5. obvious turn or transition

Requirements:
1. output JSON only
2. preserve the original text content for each scene in the `text` field
3. keep each scene as a coherent unit rather than an arbitrary fixed-length chunk
4. do not create tiny scenes unless a short scene contains a major reversal or reveal
5. if the excerpt is already one coherent scene, return one scene

Output shape:
{
  "scenes": [
    {
      "scene_id": "scene_01",
      "start_hint": "...",
      "end_hint": "...",
      "location": "...",
      "characters_present": ["..."],
      "summary": "...",
      "text": "..."
    }
  ]
}

Text:
{{text}}
```

## Generic Scene Event Extraction

```text
You are a Chinese web novel plot extraction assistant. Extract only the key events that matter for future story understanding.

A key event must do at least one of the following:
- change the protagonist's goal, situation, cognition, identity, relationship, or status
- introduce a new enemy, mission, secret, rivalry, misunderstanding, or romantic shift
- create a stage climax, reversal, face-slapping payoff, betrayal, confession, reveal, or outcome
- serve as a meaningful setup for future plot dependency

Chinese web novel constraints:
- do not split repeated taunts or repeated suppression into multiple key events
- for battles, keep cause, turning point, outcome, and consequence; omit repetitive move descriptions
- for romance, keep attitude shifts, misunderstanding formation or resolution, intimacy escalation, and rival entry
- for intrigue, keep who set the trap, who took the loss, who gained advantage
- for training arcs, keep only breakthroughs or gains that materially change later events
- daily life only counts if it affects later relationships or main plot

Output JSON only:
{
  "scene_id": "...",
  "genre_guess": "xianxia|fantasy|romance|harem|palace|urban_power|school|mixed",
  "scene_function": "setup|transition|conflict|reveal|relationship_push|power_shift|climax",
  "events": [
    {
      "event_id": "...",
      "event_group": "...",
      "event_type": "...",
      "title": "...",
      "description": "...",
      "participants": ["..."],
      "cause": "...",
      "consequence": "...",
      "importance_to_main_plot": 1,
      "emotion_value": 1,
      "shock_value": 1,
      "relationship_impact": 1,
      "status_change": true,
      "foreshadowing": true,
      "payoff": false,
      "must_keep": true,
      "can_omit": false
    }
  ]
}

Text:
{{text}}
```

## Growth / Power Fantasy Prompt

```text
You are processing a Chinese power-growth web novel.

Prioritize:
1. suppression, underestimation, public pressure, or encirclement
2. hidden strength, background, bloodline, status, or trump card reveal
3. reversal, face-slapping, counterattack, enemy loss of face
4. gains in status, resources, prestige, qualifications, or territory
5. stronger enemies, larger factions, or the next map
6. the setup and payoff of the main catharsis

Ignore:
- repeated mockery lines
- repeated spectator reactions
- long combat choreography
- repeated statements that the protagonist is talented

For each retained event, make explicit:
- what pressure existed before the payoff
- what the decisive reversal was
- how the situation changed afterward
- whether it opened the next stage conflict
```

## Xianxia / Xuanhuan Prompt

```text
You are processing a xianxia or xuanhuan web novel.

Prioritize:
1. breakthroughs that materially change combat power or position
2. key techniques, inheritances, treasures, bloodlines, and opportunities
3. sect, clan, holy land, dynasty, or realm-level conflict changes
4. secret realm, ruins, trial, and inheritance outcomes
5. master-disciple, sect, or clan relationship changes
6. hidden identities, ancient secrets, destiny, or karma reveals
7. battle or trial outcomes that redirect the protagonist's route

Ignore:
- long cultivation process details
- repeated explanations of techniques
- low-impact sparring
- pure environmental description
- scenes whose only purpose is to praise talent

Always state:
- what was gained or broken
- whether the event changed the protagonist's stage
- whether it points toward a higher realm, bigger faction, or deeper secret
```

## Palace / Intrigue Prompt

```text
You are processing a palace intrigue or political struggle novel.

Prioritize:
1. who laid the trap
2. who was targeted and who took the loss
3. who gained favor, power, trust, reputation, or leverage
4. what evidence, secret, or handle was acquired or exposed
5. what alliance, betrayal, or test took place
6. how the court, harem, or family power structure changed

Ignore:
- ceremony flow
- consequence-free pleasantries
- repeated probing dialogue
- petty disputes that do not change the structure

For each event, make explicit:
- schemer
- target
- surface outcome
- actual winner
- structural impact
```

## Romance Prompt

```text
You are processing a romance novel.

Extract only events that materially push the relationship.

Prioritize:
1. first attraction or major change in impression
2. misunderstanding formation or resolution
3. ambiguity escalation, boundary crossing, jealousy, possessiveness, care beyond normal limits
4. confession, rejection, relationship confirmation, breakup, reunion
5. rival entry or public pressure on the relationship
6. family, identity, class, or past trauma blocking the romance
7. relationship progress that changes later choices

Ignore:
- daily interactions with no relationship shift
- repeated blushing or internal heartbeat description
- sweet scenes with no downstream effect
- pure atmosphere scenes

For each event, explicitly answer:
- whose attitude changed
- why it changed
- how far it changed
- how it affects later relationship direction
```

## Harem / Multi-Route Romance Prompt

```text
You are processing a harem or multi-route romance story.

Do not distribute attention evenly across all characters.
Focus on:
1. which 1-3 relationships are currently central
2. which heroine materially moved up or down in importance
3. rivalry becoming explicit
4. jealousy, confrontation, or public claiming behavior
5. a side heroine becoming a core route
6. emotional events that affect the main plot or faction dynamics
```

## Adventure / Survival Prompt

```text
You are processing an adventure, apocalypse, or survival novel.

Prioritize:
1. mission setup and mission change
2. rule discovery and rule violation consequences
3. survival crisis, team split, alliance formation, betrayal
4. key supplies, information, shelter, passage, or safe-zone gains and losses
5. stage completion, failure, escape, or irreversible cost

Ignore:
- repetitive monster clearing
- generic route traversal
- low-impact camp banter

Keep the emphasis on:
- what the team is trying to achieve
- what new threat or rule changed the situation
- what the cost of survival was
```

## Scoring Prompt

```text
You are a Chinese web novel adaptation editor. Score which events deserve inclusion in an animation-style episode summary.

Scoring dimensions:
1. main_plot_score
2. character_relation_score
3. status_shift_score
4. climax_score
5. suspense_score
6. genre_value_score

Principles:
- events that change the situation score high
- repeated rendering of the same outcome scores low
- outcomes score higher than process
- taunting scores low, stance change scores high
- daily scenes score low unless they cause later change

Output:
{
  "events": [
    {
      "event_id": "...",
      "main_plot_score": 1,
      "character_relation_score": 1,
      "status_shift_score": 1,
      "climax_score": 1,
      "suspense_score": 1,
      "genre_value_score": 1,
      "must_keep": true,
      "keep_reason": "..."
    }
  ]
}
```

## Event Normalization Prompt

```text
You are a story knowledge-base editor. Normalize events extracted from multiple scenes.

Tasks:
1. merge aliases that clearly refer to the same character
2. merge duplicate or near-duplicate events that represent the same story node
3. preserve story order implicitly through the merged event list
4. keep cause and consequence concise
5. keep only one canonical event for repeated mentions of the same plot turn

Rules:
1. do not invent facts not supported by the input
2. if identity is uncertain, do not force a merge
3. favor state changes over action details
4. preserve events marked as important even if you compress their wording
5. output JSON only

Output shape:
{
  "events": [
    {
      "event_id": "nev_001",
      "source_scene_ids": ["scene_01", "scene_02"],
      "event_group": "revelation",
      "event_type": "revelation.traitor_exposed",
      "title": "...",
      "description": "...",
      "characters": ["..."],
      "cause": "...",
      "consequence": "...",
      "must_keep": true
    }
  ]
}

Input:
{{text}}
```

## Episode Summary Prompt

```text
You are an animation adaptation writer for Chinese web novels. Compress multiple chapters into one episode summary.

Your output must capture:
- the episode's main conflict
- the key progression beats
- the episode climax
- relationship, rank, faction, or situation changes
- the ending hook

Requirements:
1. enter conflict or tension within the first 1-2 sentences
2. keep only 3-5 major plot beats
3. make the climax concrete
4. end with a hook for the next episode
5. write like an animation synopsis, not reading notes
6. focus on the strongest main line, not every side branch
7. organize by dramatic rhythm rather than chapter order

Output JSON:
{
  "episode_id": "...",
  "title": "...",
  "core_theme": "...",
  "hook": "...",
  "main_conflict": "...",
  "key_events": ["...", "...", "..."],
  "climax": "...",
  "ending_hook": "...",
  "episode_summary": "200-400 words"
}
```
