/// <reference path="../pb_data/types.d.ts" />

// Intentionally no afterCreate saveRecord — that path returned empty 400 on PB 0.22.
// playback_status is set by upload clients / chunk complete; transcoder worker polls pending.
