# Source provenance, patch applicability and licensing

## Source base and modifications

The original **laboratory source tree** (`CoAPoverBP-no-proxy-version`) and its modified µD3TN workcopy reported Git commit:

```text
37b968d5742cbd75292b534f3421fac70acc46b7
```

This value identifies the **tested base source tree**, not the GitHub commit of this repository (initial repository commit `539b63d`). The original source **remote URL has not yet been verified**, and must be added here before advertising reproducible clean-clone installation.

The nine-file patch `patches/ud3tn/ipn-three-component-aap2.patch` includes changes to:

- `components/bundle7/bundle7.c` and `components/bundle7/eid.c`
- `components/ud3tn/bundle_processor.c` and `components/ud3tn/eid.c`
- `include/ud3tn/eid.h`
- `python-ud3tn-utils/ud3tn_utils/aap2/aap2_client.py`
- `python-ud3tn-utils/ud3tn_utils/aap2/bin/helpers.py`
- `test/unit/test_bundle7Parser.c`, `test/unit/test_bundle7Serializer.c`

The patch was verified with `git apply --check --reverse` on the modified source and `git apply --cached --check` against the original Git index. These are **patch applicability checks**, not a fresh C compilation or an independent conformance test.

The aiocoap code under `vendor/aiocoap/src` is an exported tracked source snapshot of the local project at the recorded base commit. The active Rover `message.py` was checked with SHA-256 to be byte-identical to the vendored `message.py`. It includes the experimental CoAP Payload-length number **65000** and 24-bit MID handling. Preserve upstream copyright and attribution.

## Licensing

The vendored aiocoap material includes its `doc/LICENSE.rst`, `LICENSES/MIT.txt` and `LICENSES/BSD-3-Clause.txt`. Its license is **not automatically a license for the independent project applications, C patch or Lua decoder**. Confirm a repository-wide license with ENTEL-WNG maintainers. Licensing status should be checked before making the private repository public.

## Reproducibility TODOs (open)

1. Record the exact **original project remote URL** holding commit `37b968d...` and the µD3TN revision/branch it contains.
2. Test the patch in a completely fresh source checkout and run µD3TN C tests.
3. Record `pip freeze`/package versions for all three lab Python environments and test a clean virtual environment.
4. Copy or replace the **Rover GUI image asset** stored outside the current repository and update the GUI asset search path.
5. Test app initialization with a repo-local state directory on new VMs, retaining MID uniqueness across restarts.
6. Review experimental option **65000** against the current CoAP-over-BP draft's option properties, and validate NSTART/congestion behavior.
7. Add unit/integration tests plus **Wireshark captures** for a contact disruption/recovery scenario and keep matching Rover/Earth console evidence from the same run.

Do not call the project a portable, standards-compliant or secure deployment until these steps are verified.
