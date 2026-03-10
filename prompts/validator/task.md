## Teacher's System Prompt
The assistant was instructed with the following system prompt:

{teacher_system}

## Sample to Validate
{sample}

## Task
Evaluate this sample against the quality criteria in your system prompt. Compare the assistant's response against its system prompt to verify tone, boundary, and identity compliance.

Return your evaluation as a JSON object with exactly this format:
{{"accepted": true/false, "reason": "your explanation"}}

Be strict. Only accept samples that meet ALL quality criteria. If any single criterion fails, reject the sample and explain which criterion failed and why.

Return ONLY the JSON object. No other text.
