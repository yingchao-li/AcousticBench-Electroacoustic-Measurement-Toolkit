# Data licence and attribution

The measurement data used by AcousticBench is **not** distributed with this
repository. It is downloaded separately by the user (see
`scripts/fetch_data.py`) and remains subject to its original licence.

## Dataset

- **Title**: *Original data for: "On the effect of probe tube presence on
  measured hearing aid transmission behavior"*
- **Authors**: Florian Denk, Lea Hackenberg, Hendrik Husstedt
- **Publisher**: Zenodo
- **DOI**: [10.5281/zenodo.20023285](https://doi.org/10.5281/zenodo.20023285)
- **Licence**: Creative Commons Attribution 4.0 International (CC BY 4.0)
- **Files**: `Data.mat` (MATLAB v5 MAT-file, ~90 MB), `Documentation.pdf`

## Preprint

- **Title**: *On the effect of probe tube presence on measured hearing aid
  transmission behavior*
- **DOI**: [10.5281/zenodo.20023116](https://doi.org/10.5281/zenodo.20023116)
- **Licence**: CC BY 4.0

## Attribution requirement

Any use of the data — including the results produced by AcousticBench and
committed under `results/` and `reports/` — must cite the dataset and the
associated publication:

```bibtex
@misc{denk2026dataset,
  author       = {Denk, Florian and Hackenberg, Lea and Husstedt, Hendrik},
  title        = {Original data for: "On the effect of probe tube presence on
                  measured hearing aid transmission behavior"},
  year         = {2026},
  publisher    = {Zenodo},
  doi          = {10.5281/zenodo.20023285},
  url          = {https://doi.org/10.5281/zenodo.20023285}
}

@misc{denk2026preprint,
  author       = {Denk, Florian and Hackenberg, Lea and Husstedt, Hendrik},
  title        = {On the effect of probe tube presence on measured hearing aid
                  transmission behavior},
  year         = {2026},
  publisher    = {Zenodo},
  doi          = {10.5281/zenodo.20023116},
  url          = {https://doi.org/10.5281/zenodo.20023116}
}
```

## What this repository does and does not claim

- AcousticBench performs **secondary analysis** of an openly published
  research dataset. It does not claim ownership of the data.
- Results in `results/` are derived analysis artefacts and are shared under
  CC BY 4.0 to the extent that they embed the original data.
- The code is licensed under MIT (see `LICENSE`).
- No medical-device certification, clinical validation or regulatory
  approval is claimed or implied. See `docs/limitations.md`.
