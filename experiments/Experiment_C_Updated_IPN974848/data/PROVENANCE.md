# Measurement provenance

- `measurements.csv` and `verify_calculations.py` are **unchanged historical data** from the allocator-0 size sweep. They MUST NOT be relabeled as allocator-974848 measurements. Their 50–1,000 B size-dependent byte savings are historically valid only for the previous tested configuration.
- `current_allocator974848_validation.csv` separately documents the latest allocator-974848 Single and Aggregate functionality. The new capture verifies a **212-byte Aggregate with two 50-byte POST payloads**, NOT the historical 202-byte Aggregate at nominally 50 B. No new matched two-Single-vs-one-Aggregate TCP-byte study has been made for allocator 974848.
- The historical 227 B comparison was an earlier live Science workload, not a fully controlled fixed-file replicate, as explained in the archived report.
- Original screenshot evidence is under `evidence/legacy_allocator0/`. Current user-supplied screenshots are under `evidence/current_ipn974848/`; the `detail_crops/` versions are for readability and do not replace original screenshots.
- No original `.pcapng` capture files or raw CSV for the latest full TCP-byte comparison were provided in this archive. Keep empirical claims tied to the supplied screenshots and Rover/Earth application logs.
