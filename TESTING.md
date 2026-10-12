# Validation

- Frontend dependency installation and Vite production build: passed. Built assets included.
- Eight automated tests: passed. Covers URL restrictions, VTT/SRT parsing including milliseconds, duplicate cue merging, mocked track discovery, token/host protection, service controls, stopped extraction, and frontend serving.
- FastAPI startup on loopback: passed.
- Live YouTube retrieval for Ey1g-imraNs: attempted but blocked by this environment's HTTPS certificate verification failure. Real platform extraction remains unverified here; TLS verification was not disabled.
- Browser automation: attempted but browser binary installation was blocked/truncated. Layout, clipboard and download interactions have not been verified in a real browser here.

Run a public captioned video on your own machine after installation. Platform restrictions can prevent retrieval even when local tests pass.
