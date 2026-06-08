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

- presence relative to vocal mids
- fizz (`5-8 kHz`) relative to presence and vocal mids
- air (`8-12 kHz`) relative to vocal mids and presence
- median and high-percentile ratios across active windows

Use this to avoid candidates with excess high-end hash even when the broad spectral score improves. Excess fizz is penalized asymmetrically: being too fizzy hurts more than being slightly too dark. The metric uses lightweight probe frequencies, so narrow synthetic tones can fall between probes; treat `highEnd` as a robust direction signal, not a laboratory spectrum.
