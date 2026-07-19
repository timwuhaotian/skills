---
name: mimo
description: >-
  Consolidated access to all Xiaomi MiMo v2.5 AI models through one OpenAI-compatible
  endpoint. Use whenever the user asks to call MiMo, generate speech (TTS), design or
  clone a voice, transcribe audio (ASR), chat with mimo-v2.5-pro / mimo-v2.5, do image
  understanding, or anything mentioning "mimo". Triggers on "use mimo", "mimo tts",
  "mimo voice design", "mimo voice clone", "mimo transcribe", "mimo asr", "mimo chat",
  "generate a voice", "design a voice", "用mimo生成语音", "声音设计", "语音克隆",
  "语音识别". Knows the exact request shape, voice list, style-control grammar, and
  the design→reuse voice workflow for each model.
user-invocable: true
argument-hint: "[natural language request, e.g. 'design a male european narrator voice and read this text']"
---

# MiMo

Unified gateway to **Xiaomi MiMo v2.5** models. Six models, one OpenAI-compatible
endpoint, one API key. Covers flagship chat/reasoning, multimodal vision, speech
synthesis (TTS with preset voices / voice design / voice clone), and speech
recognition (ASR).

## Models at a glance

| Model ID                       | What it does                                            | Input → Output        |
| ------------------------------ | ------------------------------------------------------- | --------------------- |
| `mimo-v2.5-pro`                | Flagship reasoning + agentic LLM (text only)            | text → text           |
| `mimo-v2.5`                    | Multimodal LLM — text + image, also general chat        | text/image → text     |
| `mimo-v2.5-asr`                | Speech recognition (zh/en/dialects/code-switch/lyrics)  | audio → text          |
| `mimo-v2.5-tts`                | TTS with **preset** premium voices + singing mode       | text → audio          |
| `mimo-v2.5-tts-voicedesign`    | TTS with a **brand-new voice designed from a text desc**| text + desc → audio   |
| `mimo-v2.5-tts-voiceclone`     | TTS that **clones an arbitrary voice from an audio sample** | text + sample → audio |

All six are reached via the **same** `/v1/chat/completions` endpoint. Differences are
just the `model` field and the payload shape. TTS/ASR/voice design are NOT separate
REST paths — they reuse chat completions with audio fields.

## Credentials

Set these in your shell. The skill reads from env vars — no key is hardcoded here.

```
export MIMO_API_KEY="tp-..."        # your Token-Plan key from platform.xiaomimimo.com
export MIMO_BASE_URL="https://token-plan-cn.xiaomimimo.com/v1"   # China cluster
```

All code blocks below use `${MIMO_API_KEY}` / `${MIMO_BASE_URL}`. The Python
helpers fall back to the env var if set. Never commit a real key to this repo.

Other clusters (same key, same paths): `token-plan-sgp.xiaomimimo.com/v1`
(Singapore), `token-plan-ams.xiaomimimo.com/v1` (Europe). Pay-as-you-go keys
(`sk-…`) use a different host: `api.xiaomimimo.com/v1`.

## How to call (zero-dependency pattern)

This skill calls the API with **curl** and decodes with **python3 stdlib only**
(no `openai` package, no `jq` needed). Reuse this skeleton for every model:

```bash
export MIMO_API_KEY="${MIMO_API_KEY:?set MIMO_API_KEY to your tp-... Token Plan key}"
export MIMO_BASE_URL="${MIMO_BASE_URL:-https://token-plan-cn.xiaomimimo.com/v1}"

curl -s -X POST "$MIMO_BASE_URL/chat/completions" \
  -H "Authorization: Bearer $MIMO_API_KEY" \
  -H "Content-Type: application/json" \
  -d @payload.json | python3 -c "..."   # see each model's decoder below
```

Output files (audio) are written to the current working directory. Always tell the
user the absolute path of any file you create.

---

## 1. Chat — `mimo-v2.5-pro` / `mimo-v2.5`

Standard OpenAI Chat Completions. Use `mimo-v2.5-pro` for hard reasoning, long
agentic workflows, tool use, coding. Use `mimo-v2.5` for general chat AND for
image input (it is the multimodal one; `-pro` is text-only).

### Text chat

```bash
curl -s -X POST "$MIMO_BASE_URL/chat/completions" \
  -H "Authorization: Bearer $MIMO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mimo-v2.5-pro",
    "messages": [
      {"role": "system", "content": "You are a concise senior engineer."},
      {"role": "user", "content": "Explain backpressure in 2 sentences."}
    ]
  }' | python3 -c "import sys,json; r=json.load(sys.stdin); print(r['choices'][0]['message']['content'])"
```

The response also carries `usage` (prompt/completion/cached tokens) and, for the
reasoning model, a `reasoning_content` field (chain of thought). Stream with
`"stream": true`.

### Image understanding (`mimo-v2.5` only)

Pass an image as a public URL or a `data:` base64 URI inside `image_url`.

```bash
curl -s -X POST "$MIMO_BASE_URL/chat/completions" \
  -H "Authorization: Bearer $MIMO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mimo-v2.5",
    "messages": [{"role": "user", "content": [
      {"type": "image_url", "image_url": {"url": "https://example-files.cnbj1.mi-fds.com/example-files/image/image_example.png"}},
      {"type": "text", "text": "Describe this image."}
    ]}]
  }' | python3 -c "import sys,json; r=json.load(sys.stdin); print(r['choices'][0]['message']['content'])"
```

For local files, base64-encode and prefix `data:{MIME};base64,…`. Supported image
formats: JPEG, PNG, GIF, WebP, BMP; ≤ 50 MB each. Multiple images per call OK.

---

## 2. Speech recognition — `mimo-v2.5-asr`

Audio → text. Send audio as a base64 `data:` URI in `input_audio`. Supports
zh/en/auto language hint, Chinese dialects (Cantonese, Wu, Hokkien, Sichuanese),
code-switching, lyrics, noisy/multi-speaker audio. Billed by audio hour.

```bash
# Encode a local audio file (wav or mp3), transcribe, print the text.
python3 - <<'PY'
import base64, json, os, urllib.request

api_key = os.environ["MIMO_API_KEY"]   # tp-... Token Plan key, from env
base    = os.environ.get("MIMO_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")

audio_path = "audio_file.wav"          # <-- replace with real path
mime = "audio/wav" if audio_path.endswith(".wav") else "audio/mpeg"
with open(audio_path, "rb") as f:
    b64 = base64.b64encode(f.read()).decode()

body = {
    "model": "mimo-v2.5-asr",
    "messages": [{"role": "user", "content": [
        {"type": "input_audio", "input_audio": {"data": f"data:{mime};base64,{b64}"}}
    ]}],
    "asr_options": {"language": "auto"}    # auto | zh | en
}
req = urllib.request.Request(
    f"{base}/chat/completions",
    data=json.dumps(body).encode(),
    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
)
print(json.load(urllib.request.urlopen(req))["choices"][0]["message"]["content"])
PY
```

---

## 3. TTS with preset voices — `mimo-v2.5-tts`

Premium built-in voices, plus singing mode. **Rules:**

- The **text to synthesize goes in the `assistant` message**, not `user`.
- The `user` message (optional) carries a **style instruction** in natural language
  (see Style Control below).
- `audio.voice` = one of the preset voice IDs.

### Preset voices

| Voice     | Voice ID (use this) | Language | Gender |
| --------- | ------------------- | -------- | ------ |
| 冰糖       | `冰糖`              | Chinese  | Female |
| 茉莉       | `茉莉`              | Chinese  | Female |
| 苏打       | `苏打`              | Chinese  | Male   |
| 白桦       | `白桦`              | Chinese  | Male   |
| Mia       | `Mia`               | English  | Female |
| Chloe     | `Chloe`             | English  | Female |
| Milo       | `Milo`              | English  | Male   |
| Dean       | `Dean`              | English  | Male   |
| MiMo default | `mimo_default`   | cluster default | — |

```bash
curl -s -X POST "$MIMO_BASE_URL/chat/completions" \
  -H "Authorization: Bearer $MIMO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mimo-v2.5-tts",
    "messages": [
      {"role": "user", "content": "Calm, late-night radio tone. Slow, intimate."},
      {"role": "assistant", "content": "夜已经深了，城市还在呼吸。我是今晚陪你的人，欢迎收听《午夜电台》。"}
    ],
    "audio": {"format": "wav", "voice": "苏打"}
  }' | python3 -c "
import sys, json, base64
r = json.load(sys.stdin)
data = r['choices'][0]['message']['audio']['data']
open('tts.wav','wb').write(base64.b64decode(data))
print('saved tts.wav')
"
```

Singing: prepend `(唱歌)` (or `(sing)` / `(singing)`) to the `assistant` content,
e.g. `(唱歌)原谅我这一生不羁放纵爱自由`.

---

## 4. Voice design — `mimo-v2.5-tts-voicedesign`

**Design a brand-new voice from a text description** — no preset, no audio sample.
This is the model for "male, European narrator", "young female ASMR", etc.

- `user` message = **voice design description** (required).
- `assistant` message = **text to synthesize** in that voice.
  - Tip: the synthesis text should *match* the voice (a gravelly narrator gets a
    documentary line, not a hyper pop ad). If you have no text, set
    `audio.optimize_text_preview: true` and **omit the assistant message** — the
    model writes matching sample text for you.

### How to write a good voice description

Cover several of these dimensions (1–4 sentences, Chinese or English):

| Dimension        | Example                                                   |
| ---------------- | --------------------------------------------------------- |
| Gender & age     | "middle-aged male, early 50s" / "二十多岁的年轻女性"        |
| Timbre / texture | "deep and gravelly" / "丝滑醇厚、带着磁性"                 |
| Emotion / tone   | "warm and confident" / "温柔但带着一丝疲惫"                |
| Pace / rhythm    | "slow and deliberate" / "语速极快，像连珠炮"               |
| (optional) persona / scene / era | "1940s film noir narrator", "nature documentary VO" |

Avoid: conflicting traits ("childlike + CEO authority"), audio-engineering terms
(reverb, EQ, compression), vague words ("normal", "foreign").

### Example: design + synthesize in one call

```bash
curl -s -X POST "$MIMO_BASE_URL/chat/completions" \
  -H "Authorization: Bearer $MIMO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mimo-v2.5-tts-voicedesign",
    "messages": [
      {"role": "user", "content": "Deep, gravelly European male in his 50s. Gruff, matter-of-fact, like a seasoned documentary narrator. Slow, deliberate pace with a slight rasp."},
      {"role": "assistant", "content": "The river has carved this valley over ten thousand years. Every stone you see was once a mountain."}
    ],
    "audio": {"format": "wav"}
  }' | python3 -c "
import sys, json, base64
r = json.load(sys.stdin)
data = r['choices'][0]['message']['audio']['data']
open('designed_voice.wav','wb').write(base64.b64decode(data))
print('saved designed_voice.wav')
"
```

With `optimize_text_preview` (model writes the line itself):

```json
"messages": [
  {"role": "user", "content": "Deep, gravelly European male in his 50s, documentary narrator."}
],
"audio": {"format": "wav", "optimize_text_preview": true}
```

---

## 5. Voice clone — `mimo-v2.5-tts-voiceclone`

**Replicate an arbitrary voice from an audio sample**, then synthesize new text in
that voice. Sample must be `mp3` or `wav`, ≤ 10 MB after base64.

- `audio.voice` = `data:{MIME};base64,{BASE64_OF_SAMPLE}` (the reference voice).
- `assistant` message = text to synthesize.
- `user` message (optional) = style instruction.

```bash
python3 - <<'PY'
import base64, json, os, urllib.request

api_key = os.environ["MIMO_API_KEY"]   # tp-... Token Plan key, from env
base    = os.environ.get("MIMO_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")

sample = "voice.mp3"                    # <-- reference voice sample
mime = "audio/mpeg" if sample.endswith(".mp3") else "audio/wav"
with open(sample, "rb") as f:
    voice = f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"

body = {
    "model": "mimo-v2.5-tts-voiceclone",
    "messages": [
        {"role": "user", "content": ""},
        {"role": "assistant", "content": "Yes, I had a sandwich."}
    ],
    "audio": {"format": "wav", "voice": voice}
}
req = urllib.request.Request(
    f"{base}/chat/completions",
    data=json.dumps(body).encode(),
    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
)
r = json.load(urllib.request.urlopen(req))
audio = base64.b64decode(r["choices"][0]["message"]["audio"]["data"])
open("cloned.wav", "wb").write(audio)
print("saved cloned.wav")
PY
```

---

## Style control (TTS, all three models)

Two independent mechanisms. **Natural-language control** lives in `role: user`
content. **Audio-tag control** lives inline in `role: assistant` content.

### Natural language (user message)

One sentence or full "director mode" with 角色/场景/指导 sections. Examples:

> 用轻快上扬的语调向领导报喜，语速稍快，带着压抑不住的激动与小骄傲。
>
> Bright, bouncy, slightly sing-song tone — bursting with good news. Fast pace,
> rising pitch at the end.

### Audio tags (assistant message, inline)

Lead with a style tag in parentheses, insert mid-text action tags in brackets:

- **Style prefix**: `(风格1 风格2)文本` — e.g. `(磁性 慵懒)夜深了…`,
  `(东北话)哎呀妈呀…`, `(唱歌)歌词…`.
- Style families: 开心/悲伤/愤怒/温柔/高冷/磁性/御姐音/大叔音/东北话/粤语/孙悟空…
- **Inline action tags** `[ ]`: `[吸气] [深呼吸] [叹气] [颤抖] [轻笑] [抽泣] [哽咽]`,
  `(语速加快)`, `(小声)`.

---

## Workflows

### A. "Design a voice, then reuse it" (the headline use case)

The designed voice is **embodied by its description text** — there is no separate
`voice_id` to save. To reuse the same voice on new text, **send the identical
`user` description again** with the new `assistant` text.

When the user says e.g. *"design a male European narrator voice"*, then later
*"now read this paragraph with that voice"*:

1. **Design call** — craft a rich description, synthesize a short sample so the
   user can hear it. Save the description + sample path.
2. **Reuse calls** — for every subsequent "say X with that voice", resend the
   SAME `user` description verbatim, change only the `assistant` text. Same model
   (`mimo-v2.5-tts-voicedesign`).
3. Keep the description in working memory; if the user tweaks the voice ("make it
   deeper"), edit the description and use the new one for all following calls.

If the user wants a **persistent reusable voice** instead, switch to
`mimo-v2.5-tts-voiceclone` with a sample they provide — but the design model is
the right default when there is no sample.

### B. Transcribe then summarize

1. `mimo-v2.5-asr` → get transcript text.
2. Feed transcript into `mimo-v2.5-pro` (or `mimo-v2.5`) for summary / extract /
   translation.

### C. Multimodal Q&A

Single `mimo-v2.5` call with image(s) + text. For text-only heavy reasoning, use
`mimo-v2.5-pro`.

---

## Limits & gotchas

- **TTS target text always in `assistant`** message — the #1 mistake. Putting it
  in `user` silently breaks synthesis.
- `mimo-v2.5-tts-voicedesign` / `-voiceclone` **do not support singing mode or
  preset voices**. Singing + presets are `mimo-v2.5-tts` only.
- Streaming: only `mimo-v2.5-tts` has true low-latency streaming. The other two
  TTS models return one buffered chunk. For streamed audio use `format: "pcm16"`
  (24 kHz mono LE) and concatenate chunks.
- Voice clone / ASR sample: `mp3`/`wav` only, ≤ 10 MB base64. Image: ≤ 50 MB.
- Token-Plan keys (`tp-…`) **must** use the `token-plan-*.xiaomimimo.com` host,
  not `api.xiaomimimo.com`. Wrong host → `Invalid API Key`.
- Reasoning model returns `reasoning_content` separately from `content`.
- Deprecated: `mimo-v2-pro`, `mimo-v2-omni`, `mimo-v2-tts` are offline — always
  use the `v2.5` IDs above.

## Official docs

- Speech synthesis (TTS): https://mimo.mi.com/docs/usage-guide/speech-synthesis-v2.5
- Speech recognition (ASR): https://mimo.mi.com/docs/zh-CN/quick-start/usage-guide/audio/Speech-Recognition
- Image understanding: https://mimo.mi.com/docs/en-US/quick-start/usage-guide/multimodal-understanding/image-understanding
- Token Plan (models, pricing, base URLs): https://mimo.mi.com/docs/tokenplan/subscription
- Playground / Studio: https://aistudio.xiaomimimo.com/
