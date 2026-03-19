# Relationship Extraction Prompt

You are analyzing a list of normalized events from a web novel chapter. Extract relationship changes between characters.

For each relationship change detected in the events, extract:
1. **source_character**: The first character in the relationship
2. **target_character**: The second character in the relationship
3. **relation_type**: One of: ally, enemy, master_disciple, lover, rival, family, neutral
4. **description**: Brief description of the relationship or change
5. **established_in**: The event_id where this relationship was established or changed

## Input Format
A JSON array of normalized events, each with: event_id, event_group, event_type, title, description, characters, cause, consequence.

## Output Format
Return strict JSON:
```json
{
  "relationships": [
    {
      "source_character": "角色A",
      "target_character": "角色B",
      "relation_type": "ally",
      "description": "关系描述",
      "established_in": "evt_001"
    }
  ]
}
```

## Relation Type Guide
- **ally**: 盟友、同伴、合作关系
- **enemy**: 敌人、仇人、对立关系
- **master_disciple**: 师徒、师父与弟子
- **lover**: 恋人、情侣、暧昧关系
- **rival**: 竞争对手、宿敌（非生死之敌）
- **family**: 血缘关系、义兄弟、结拜
- **neutral**: 无明确立场的关系

## Rules
- Only extract relationships explicitly shown in events
- Focus on relationship events, emotion_romance events, and status_shift events
- If a relationship changes (e.g., ally becomes enemy), report the NEW state
- Do NOT invent relationships not supported by the events

## Events
{{events}}
