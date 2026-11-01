# Few-shot reference photos for the vision LLM

Put labelled soybean photos in the folder for their label. The first 3 per folder (sorted by file name,
`VISION_REFS_PER_LABEL` changes the count) are sent with every farmer photo as examples, so pick clear,
typical ones and prefix the best with `01_`, `02_`, ...

| Folder | What it shows |
|---|---|
| `healthy/` | uniform green leaves |
| `yellow_mosaic/` | yellow-green mottle (YMV, whitefly) |
| `uniform_yellowing/` | evenly pale leaf, no mottle (nutrient / waterlogging) |
| `chewing_damage/` | holes, eaten edges (semilooper, tobacco caterpillar) |
| `girdle_beetle/` | ring cuts on stalk, drooping leaves above |
| `fungal/` | rust, frog-eye, blight spots |

jpg, jpeg, png or webp. Never put the exact photo you will show in the demo here; use similar ones.
