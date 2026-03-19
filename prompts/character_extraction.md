# Character Extraction Prompt

You are analyzing a list of normalized events from a web novel chapter. Extract character information from these events.

For each character mentioned in the events, extract:
1. **canonical_name**: The character's primary name
2. **identity**: Their role/title/position (e.g., "青云宗外门弟子", "魔道至尊")
3. **stance**: Their current alignment or faction allegiance
4. **recent_goals**: What they are currently trying to achieve (from goal_progress events)
5. **known_secrets**: Any secrets revealed about or by them (from revelation events)
6. **status**: Current state - "active", "deceased", "departed", or "unknown"

## Input Format
A JSON array of normalized events, each with: event_id, event_group, event_type, title, description, characters, cause, consequence.

## Output Format
Return strict JSON:
```json
{
  "characters": [
    {
      "canonical_name": "角色名",
      "identity": "身份描述",
      "stance": "立场/阵营",
      "recent_goals": ["目标1"],
      "known_secrets": ["秘密1"],
      "status": "active"
    }
  ]
}
```

## Rules
- Only extract information explicitly stated or strongly implied in the events
- Do NOT invent or speculate about character details
- If a field cannot be determined, use empty string or empty array
- Merge duplicate characters (same person with different names/titles)
- Prioritize the most specific name as canonical_name

## Events
{{events}}
