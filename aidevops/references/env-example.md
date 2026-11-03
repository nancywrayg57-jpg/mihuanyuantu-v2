# Environment Example

Use this reference when documenting local `.env` setup for AidevOps smoke tests, OpenAI-compatible relays, or prototype image requests. Never commit a real `.env` file or paste real secret values into phase files, prompts, reports, screenshots, or generated images.

## Recommended `.env`

Prefer standard OpenAI-compatible names:

```dotenv
OPENAI_BASE_URL=https://your-relay.example.com/v1
OPENAI_API_KEY=sk-your-key-here
```

Optional values when the SDK or provider requires them:

```dotenv
OPENAI_ORG_ID=
OPENAI_PROJECT=
```

## Current Relay Compatibility

The local smoke script also supports the compact relay aliases used by this skill bundle:

```dotenv
baseurl: https://your-relay.example.com
apikey: sk-your-key-here
```

Rules:

- `OPENAI_API_KEY`, `apikey`, and `API_KEY` are treated as API-key aliases.
- `OPENAI_BASE_URL`, `baseurl`, and `BASE_URL` are treated as base-URL aliases.
- `KEY=value` and `KEY: value` formats are both accepted by `scripts/gpt_image_smoke.py`.
- The script normalizes relay base URLs to end in `/v1` when needed.

## Smoke Test Commands

```bash
python3 aidevops/scripts/gpt_image_smoke.py --env aidevops/.env --mode models
python3 aidevops/scripts/gpt_image_smoke.py --env aidevops/.env --mode responses-text --text-model gpt-5.4
python3 aidevops/scripts/gpt_image_smoke.py --env aidevops/.env --mode responses-image-tool --text-model gpt-5.4 --model gpt-image-2 --size 1536x1024 --quality high --strict-size
```

The smoke script also appends the requested size and quality into the prompt so they are present in both the API parameters and the natural-language image brief.

Treat `--strict-size` failures as useful evidence. A relay may successfully return a PNG while normalizing dimensions, quality, or other metadata.
