# Novel Genre Taxonomy

This taxonomy is optimized for plot extraction, event routing, and episodic summarization of Chinese web novels.

## Primary Genres

### `power_growth`
- Main drive: growth, leveling, power gain, resource competition, map progression.
- Typical works: xianxia, xuanhuan, system novels, urban superpower, academy growth.

Subgenres:
- `xianxia`
- `xuanhuan`
- `system`
- `urban_superpower`
- `academy_growth`
- `revenge_upgrade`

Key extraction focus:
- realm or power changes
- key resources, inheritances, techniques, artifacts
- victories, reversals, face-slapping outcomes
- status rise, qualification gain
- new enemies, new factions, new stages

### `political_intrigue`
- Main drive: power structure shifts and factional struggle.
- Typical works: palace intrigue, family intrigue, court politics, historical hegemony.

Subgenres:
- `palace`
- `family_intrigue`
- `court_politics`
- `historical_hegemony`
- `clan_power`

Key extraction focus:
- who set the trap
- who gained or lost favor
- evidence, leverage, imperial favor, public opinion
- alliances, betrayal, probing, counterplay
- structural power changes

### `romance_relationship`
- Main drive: relationship progression and emotional shifts.
- Typical works: romance, school love, urban love, harem, marriage-first-love-later.

Subgenres:
- `sweet_romance`
- `school_romance`
- `urban_romance`
- `harem`
- `marriage_first_love_later`
- `chasing_wife_crematorium`

Key extraction focus:
- affection shifts
- misunderstanding formed or resolved
- ambiguity escalation
- confession, rejection, confirmation, breakup, reunion
- rival entry
- family, identity, class obstacles

### `adventure_survival`
- Main drive: missions, exploration, survival, stage clearing.
- Typical works: apocalypse, unlimited flow, dungeon raid, fantasy quest.

Subgenres:
- `apocalypse`
- `unlimited_flow`
- `dungeon_raid`
- `fantasy_quest`
- `wilderness_survival`

Key extraction focus:
- mission goals
- survival crisis
- team changes
- rule discovery
- gains and tradeoffs
- stage clear or failure

### `mystery_revelation`
- Main drive: investigation, hidden truth, revelation.
- Typical works: suspense, detective, supernatural investigation, rule horror.

Subgenres:
- `detective`
- `suspense`
- `supernatural_investigation`
- `rule_horror`

Key extraction focus:
- mystery setup
- clue discovery
- false leads
- key deduction
- truth reveal
- twist

### `career_reversal`
- Main drive: realistic status rise and social reversal.
- Typical works: business, workplace, celebrity, wealth growth, urban comeback.

Subgenres:
- `business`
- `workplace`
- `celebrity`
- `wealth_growth`
- `urban_comeback`

Key extraction focus:
- identity and status changes
- project success or failure
- social reputation changes
- network and resource changes
- suppression and counterattack
- career and romance linkage

### `hybrid`
- Main drive: multiple major engines coexist.
- Typical works: xianxia + romance, palace + romance, apocalypse + system.

Use:
- choose one `primary_genre`
- add one or more `secondary_genres`
- route extraction with primary prompt first, then supplement with secondary prompts

## Recommended Classification Output

```json
{
  "primary_genre": "power_growth",
  "subgenre": "xianxia",
  "secondary_genres": ["romance_relationship"],
  "confidence": 0.91,
  "signals": [
    "Frequent realm, sect, inheritance, and secret realm content",
    "Main plot centers on cultivation growth and sect conflict",
    "A parallel romance line is materially advancing"
  ]
}
```

## Routing Rules

```text
if primary_genre == power_growth:
    use growth/xianxia prompts
if primary_genre == political_intrigue:
    use palace/intrigue prompts
if primary_genre == romance_relationship:
    use romance prompts
if primary_genre == adventure_survival:
    use survival/adventure prompts
if primary_genre == mystery_revelation:
    use mystery prompts
if primary_genre == career_reversal:
    use urban/career prompts
if secondary_genres exist:
    run a supplemental extraction pass for relationship or side-axis events
```
