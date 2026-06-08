# Audio lab reference-tone chase

Use this when the musician asks to match, chase, approximate, or rank against a reference guitar tone.

This is an agent-facilitated workflow. Do not hand the musician a CLI recipe unless they explicitly ask for implementation details.

## Workflow

1. Confirm the isolated reference WAV path and the dry take/session. If no dry take exists, create or record one through the audio lab before running candidates.
2. Ensure USB audio setup is available. If audio dependencies are missing, use `references/skill-audio-setup.md` internally.
3. Build the reference profile from the WAV.
4. Run the bounded candidate loop against the temporary patch only.
5. Restore temporary edits after each render.
6. Report the best few results in musician-facing terms.

## Candidate Verification Rule

Every candidate parameter that is not already live-verified must pass live write/read-back verification before its render can count.

- Verify the exact candidate write before rendering it.
- Skip the candidate if read-back verification fails.
- Report skipped candidates with the failed area/parameter and plain-language reason.
- Do not score or recommend a render from an unverified candidate.

Already live-verified candidate surfaces may be used directly, but default live runs should still verify writes when practical.

## Reporting

Report:

- reference WAV used
- dry take/session used
- baseline rank/score
- top candidate renders available for audition
- what changed musically
- any skipped candidates and why
- whether temporary edits were restored

Make clear that the score is approximate. It is a ranking aid based on rendered audio metrics, not a guarantee of the player's preferred tone.

## Persistence Gate

Do not persist a winning candidate automatically.

Offer to re-apply a winning candidate temporarily for listening, or save it to a named user slot only after explicit approval. If saving during development, stay inside the allowed scratch slot range from the repo instructions unless the user gives a specific broader instruction.

## MVP Boundaries

- Candidate search is intentionally bounded and conservative.
- The runner ranks rendered WAVs by approximate spectral/loudness metrics plus a low-weight space/reverb descriptor.
- Probes and candidate renders are temporary by default.
- The workflow should end with auditionable renders and a clear recommendation, not an automatic save.

## Target Dimensions

Attack targets one at a time and keep the evidence separate.

Use real reference tracks as calibration examples, not as fixed recipes. Extract general matching strategy from each experiment: normalized ratios, active-window gating, asymmetric penalties for musically bad excess, and known analyzer limits. Do not encode artist- or song-specific thresholds unless the user explicitly asks to chase that one reference.

### Space / Reverb

The reference profile includes a `space` section for ambience matching:

- tail level relative to active frames
- tail brightness
- stereo correlation and side-vs-mid width
- tail envelope modulation
- repeat lag/strength as a hint only

Use this to distinguish dry, mono, wide, diffuse, and echo-like candidates. Do not treat repeat lag as confirmed delay time without an audition or a dedicated delay experiment.

### Fizz / Upper-End Rolloff

The reference profile includes a `highEnd` section for upper-end matching:

- presence relative to lead mids
- fizz (`5-8 kHz`) relative to presence and lead mids
- air (`8-12 kHz`) relative to lead mids and presence
- median and high-percentile ratios across active windows

Use this to avoid candidates with excess high-end hash even when the broad spectral score improves. Excess fizz is penalized asymmetrically: being too fizzy hurts more than being slightly too dark. The metric uses lightweight probe frequencies, so narrow synthetic tones can fall between probes; treat `highEnd` as a robust direction signal, not a laboratory spectrum.

### Low-Mid Body / Flub Guard

The reference profile includes a `lowBody` section for body-versus-boom matching:

- sub-bass (`80-160 Hz`) relative to body and mids
- body (`160-320 Hz`) relative to low mids and lead mids
- combined body/low-mid (`160-640 Hz`) relative to `640-2500 Hz`
- asymmetric flub guard for excess sub-bass

Use this to prefer candidates with guitar body and sustain without rewarding boomy lows. Excess `80-160 Hz` hurts more than a slight deficit, because flub is usually more damaging to this target than being a little lean.

### Attack / Sustain Envelope

The reference profile includes an `envelope` section for dynamics matching:

- attack level relative to sustain
- peak-to-sustain level
- attack crest
- sustain drop and sustain slope
- sustain range
- fraction of sustain frames that remain within 12 dB of peak

Use this to distinguish singing sustain from spiky attack or fast decay. This descriptor is most meaningful when comparing renders from the same dry take or otherwise similar phrases. Reverb and delay tails belong primarily to `space`; `envelope` focuses on active/post-attack frames.

### Lead-Mid Focus

The reference profile includes a `leadMid` section for how forward the guitar's singing range is:

- lead-mid energy (`1250-2500 Hz`) relative to low mids, upper low mids, presence, and fizz
- lead focus index across the surrounding guitar bands
- median and P10/P90 active-window ratios for consistency across the phrase

Use this to distinguish focused lead guitar mids from low-mid body or high-end fizz. A candidate should not score well here merely because it is brighter or boomier; it should keep the main lead range present relative to the surrounding bands. The fizz ratio is ignored when both reference and candidate are at the spectral floor for fizz, because that case means "no measurable fizz" rather than a meaningful tonal difference.
