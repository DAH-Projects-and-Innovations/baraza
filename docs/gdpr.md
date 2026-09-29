# GDPR guide

This guide helps each organization deploying Baraza keep its record of processing activities and,
if needed, carry out a data protection impact assessment (DPIA). It is not legal advice.

> **To be completed** before the v1.0 release.

## What Baraza does by default

- A fully local deployment is possible: transcription and language model on your own servers.
- If an external model provider is configured (`BARAZA_LLM_IS_EXTERNAL=true`), the interface shows
  it to administrators.
- Speakers are identified from meeting metadata, never by voiceprint (biometric data).
- Audio is deleted after transcription (`BARAZA_DELETE_AUDIO_AFTER_TRANSCRIPTION`).
- Configurable retention period (`BARAZA_RETENTION_DAYS`).
- Access log for meeting minutes.

## What remains the organization's responsibility

- Informing participants before each capture.
- Choosing the legal basis for processing and the retention period.
- Adding the processing to the record of processing activities; assessing whether a DPIA is needed.
