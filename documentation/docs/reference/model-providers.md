# Connect a model

The [design conversation](../platform/design-conversation.md) needs a language
model. Everything else in StudyLoop works without one: templates, direct entry,
recruitment planning and exports. This page connects Mistral, Ollama or another
OpenAI-compatible provider and lists the settings and common failures.

Edit `.env.local`, then restart the server with the same `--env-file` command. Keep
credentials in that local file, which Git ignores.

## Mistral

In Mistral Studio, open **API Keys**, choose **New key**, and copy it into
`.env.local`. See [Mistral's API key guide](https://docs.mistral.ai/getting-started/quickstarts/studio/activate-and-generate-api-key).
StudyLoop uses `ministral-14b-latest` unless you set `LLM_MODEL` to another model
your account can use.

```dotenv
LLM_API_KEY=your-mistral-key
```

## Ollama on your machine

[Install Ollama](https://ollama.com/download) and start it, or run `ollama serve` in
a separate terminal if you installed only the command-line tool. Then pull a model.
[`qwen2.5:7b`](https://ollama.com/library/qwen2.5:7b) is an example.

```bash
ollama pull qwen2.5:7b
```

```dotenv
LLM_BASE_URL=http://127.0.0.1:11434/v1
LLM_MODEL=qwen2.5:7b
LLM_API_KEY=
```

A local server needs no key.

## Another OpenAI-compatible provider

Set `LLM_BASE_URL` to the provider's HTTPS API base, `LLM_API_KEY` to its key and
`LLM_MODEL` to the exact model ID. Choose a chat model that accepts
`response_format: json_object`. A base URL ending in `/v1` is extended to
`/v1/chat/completions`; you can also give the full chat-completions URL. Use
`LLM_DESIGN_MODEL` if you want a separate model for the design conversation.

## Settings

| Variable | Use |
| --- | --- |
| `LLM_API_KEY` | Turns on the design conversation. On Mistral's API it also lets scheduled paper refreshes screen candidates with `mistral-embed`. Not needed for a local server |
| `LLM_BASE_URL` | Chat-completions API base or full URL; defaults to Mistral's API |
| `LLM_MODEL` | The shared model; defaults to `ministral-14b-latest` |
| `LLM_DESIGN_MODEL` | Optional model for the design conversation only |
| `LLM_TIMEOUT_S` | Request timeout in seconds; default 60, range 1 to 600 |
| `LLM_STREAM_TIMEOUT_S` | Stream timeout in seconds; default 120, range 1 to 1800 |
| `LLM_MAX_RETRIES` | Retries for rate limits, transient server errors and connection failures; default 2, range 0 to 5 |
| `LLM_ALLOW_HTTP` | Set to `1` to allow plain HTTP to a host that is not your own machine |

## What the provider receives

A hosted provider receives the text of the design conversation and the literature
retrieved for it. It does not receive participant event rows. Keep participant
details out of design prompts, and review your provider's data terms before use.
See the
[security notes](https://github.com/idreesshaikh/human-ai-studies-framework/blob/main/SECURITY.md#access-and-capture).

Two other requests do not go to your chat model. When the local library has little
on a topic, a design-conversation turn sends up to eight keywords from your
messages to Semantic Scholar; set `MIDDLEWARE_LIVE_SEARCH=0` to stop that. On
Mistral's API, scheduled paper refreshes send the titles and abstracts of candidate
papers to `mistral-embed`; see
[Keep the literature library current](literature-library.md#queries-and-schedule).

## When it does not work

| Symptom | What to check |
| --- | --- |
| The assistant says no language model is connected | Start the server with `--env-file .env.local` and confirm your key or local endpoint is set |
| The provider rejected the request | Confirm the key is active and has access to the exact `LLM_MODEL` or `LLM_DESIGN_MODEL` you chose |
| Ollama times out or reports an unavailable model | Check that Ollama is running and the model appears in `ollama list`. Allow a longer timeout on slower hardware |
| A model replies without a usable design | Confirm the endpoint and model support JSON output. You can continue from a template or [enter the protocol directly](../platform/manual-entry.md) |

## Next steps

- [Design conversation](../platform/design-conversation.md)
- [Configuration](configuration.md)
